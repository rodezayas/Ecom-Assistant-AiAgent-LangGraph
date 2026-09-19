"""Evaluation runner — iterates golden dataset, runs agent, compares, persists.

Links to Phoenix via trace_id extracted from OpenTelemetry context.
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any

from ecomm_agent.core.config import settings
from ecomm_agent.schemas.golden import GoldenQuery
from ecomm_agent.services.golden_dataset import list_golden_queries
from ecomm_agent.services.supabase import get_supabase_client

logger = logging.getLogger(__name__)


def _get_trace_id() -> str | None:
    """Extract current OTEL trace_id as hex (for Phoenix link)."""
    try:
        from opentelemetry import trace

        span = trace.get_current_span()
        ctx = span.get_span_context()
        if ctx.is_valid:
            # trace_id is 128-bit int; format as 32-char hex
            return format(ctx.trace_id, "032x")
    except Exception:
        pass
    return None


def _check_golden(golden: GoldenQuery, actual_intent: str | None, actual_ids: list[str], actual_guardrail_blocked: bool | None, actual_guardrail_reason: str | None, actual_response: str | None) -> tuple[bool, list[str]]:
    """Compare actual vs expected, return (passed, failed_checks)."""
    failed: list[str] = []
    if golden.expected_intent != actual_intent:
        failed.append(f"intent_mismatch: expected {golden.expected_intent} got {actual_intent}")
    if golden.expected_guardrail_blocked != (actual_guardrail_blocked or False):
        failed.append(f"guardrail_blocked_mismatch: expected {golden.expected_guardrail_blocked} got {actual_guardrail_blocked}")
    if golden.expected_guardrail_blocked and golden.expected_guardrail_reason:
        if golden.expected_guardrail_reason != (actual_guardrail_reason or ""):
            failed.append(f"guardrail_reason_mismatch: expected {golden.expected_guardrail_reason} got {actual_guardrail_reason}")
    for pid in golden.expected_product_ids:
        if pid not in actual_ids:
            failed.append(f"missing_product:{pid}")
    # If golden expects specific size/color/category, check that agent extracted them? optional
    for needle in golden.expected_response_contains:
        if not actual_response or needle.lower() not in actual_response.lower():
            failed.append(f"missing_response_contains:{needle}")
    for needle in golden.expected_response_not_contains if hasattr(golden, "expected_response_not_contains") else []:
        if actual_response and needle.lower() in actual_response.lower():
            failed.append(f"unexpected_response_contains:{needle}")
    # also tag retrieval source / expected? skip
    return (len(failed) == 0, failed)


def _persist_run(total: int, passed: int, failed: int, dataset_version: str = "v1") -> str | None:
    """Insert evaluation_runs row, return id or None if table missing/not configured."""
    client = get_supabase_client()
    if client is None:
        return None
    try:
        row = {
            "dataset_version": dataset_version,
            "total_queries": total,
            "passed": passed,
            "failed": failed,
            "model_config": {"anthropic_model": settings.anthropic_model, "groq_model": settings.groq_model},
            "config_snapshot": {"phoenix_project": settings.phoenix_project_name},
        }
        resp = client.table("evaluation_runs").insert(row).select("id").execute()
        data = resp.data or []
        if data:
            return data[0].get("id")
    except Exception as exc:
        # Table missing -> log warning, return local uuid
        logger.warning("persist_run failed (table missing?)", extra={"error": str(exc)})
    return str(uuid.uuid4())


def _persist_result(run_id: str, golden: GoldenQuery, actual_intent: str | None, actual_ids: list[str], actual_response: str | None, passed: bool, failed_checks: list[str], latency_ms: int, trace_id: str | None, thread_id: str | None, actual_guardrail_blocked: bool | None, actual_guardrail_reason: str | None) -> None:
    """Insert evaluation_results row; no-op if table missing."""
    client = get_supabase_client()
    if client is None:
        return
    try:
        row: dict[str, Any] = {
            "run_id": run_id,
            "golden_query_id": golden.id,
            "golden_slug": golden.slug,
            "query_text": golden.query_text,
            "actual_intent": actual_intent,
            "actual_guardrail_blocked": actual_guardrail_blocked,
            "actual_guardrail_reason": actual_guardrail_reason,
            "actual_product_ids": actual_ids,
            "actual_response_text": (actual_response or "")[:4000],
            "passed": passed,
            "failed_checks": failed_checks,
            "latency_ms": latency_ms,
            "phoenix_trace_id": trace_id,
            "thread_id": thread_id,
        }
        if trace_id:
            # Phoenix Cloud trace URL pattern
            row["phoenix_trace_url"] = f"https://app.phoenix.arize.com/projects/{settings.phoenix_project_name}/traces/{trace_id}"
        client.table("evaluation_results").insert(row).execute()
    except Exception as exc:
        logger.warning("persist_result failed (table missing?)", extra={"slug": golden.slug, "error": str(exc)})


def _update_run_counts(run_id: str, total: int, passed: int, failed: int) -> None:
    client = get_supabase_client()
    if client is None:
        return
    try:
        client.table("evaluation_runs").update({"total_queries": total, "passed": passed, "failed": failed}).eq("id", run_id).execute()
    except Exception as exc:
        logger.debug("update_run_counts failed", extra={"error": str(exc)})


def run_golden_evaluation(
    *,
    limit: int | None = None,
    intent: str | None = None,
    dataset_version: str = "v1",
) -> dict[str, Any]:
    """Run full golden evaluation synchronously.

    Args:
        limit: Optional cap on golden queries.
        intent: Optional intent filter.
        dataset_version: Version tag stored in evaluation_runs.

    Returns:
        Summary dict with run_id, total/passed/failed, results.
    """
    from ecomm_agent.observability.tracing import get_tracer

    tracer = get_tracer("evaluation")

    goldens = list_golden_queries(active_only=True, limit=limit or 100, intent=intent)
    if not goldens:
        return {"run_id": None, "total": 0, "passed": 0, "failed": 0, "pass_rate": 0.0, "results": [], "error": "no golden queries (check Supabase configured and seeded)"}

    # Create run row early
    run_id = _persist_run(total=len(goldens), passed=0, failed=0, dataset_version=dataset_version)
    if run_id is None:
        run_id = str(uuid.uuid4())

    results: list[dict[str, Any]] = []
    passed = 0
    failed = 0

    # Import lazily to avoid circular
    from ecomm_agent.services.chatbot import process_user_message

    with tracer.start_as_current_span("evaluation.run") as span:
        try:
            span.set_attribute("evaluation.total", len(goldens))
            span.set_attribute("evaluation.dataset_version", dataset_version)
        except Exception:
            pass
        for golden in goldens:
            thread_id = f"eval-{golden.slug}"
            t0 = time.monotonic()
            trace_id: str | None = None
            with tracer.start_as_current_span(f"evaluation.query:{golden.slug}") as qspan:
                try:
                    qspan.set_attribute("golden.slug", golden.slug)
                    qspan.set_attribute("golden.expected_intent", golden.expected_intent)
                except Exception:
                    pass
                state = process_user_message(thread_id=thread_id, text=golden.query_text)
                latency_ms = int((time.monotonic() - t0) * 1000)
                actual_ids = [p.id for p in state.retrieved_products]
                actual_intent = state.intent
                actual_response = state.response_text
                trace_id = _get_trace_id()
                try:
                    qspan.set_attribute("actual.intent", actual_intent or "")
                    qspan.set_attribute("actual.product_count", len(actual_ids))
                    qspan.set_attribute("evaluation.latency_ms", latency_ms)
                    if trace_id:
                        qspan.set_attribute("phoenix.trace_id", trace_id)
                except Exception:
                    pass
                is_passed, failed_checks = _check_golden(
                    golden, actual_intent, actual_ids, state.guardrail_blocked, state.guardrail_reason, actual_response
                )
            if is_passed:
                passed += 1
            else:
                failed += 1
            # Persist per-query result
            _persist_result(
                run_id=run_id,
                golden=golden,
                actual_intent=actual_intent,
                actual_ids=actual_ids,
                actual_response=actual_response,
                passed=is_passed,
                failed_checks=failed_checks,
                latency_ms=latency_ms,
                trace_id=trace_id,
                thread_id=thread_id,
                actual_guardrail_blocked=state.guardrail_blocked,
                actual_guardrail_reason=state.guardrail_reason,
            )
            results.append(
                {
                    "run_id": run_id,
                    "golden_query_id": golden.id,
                    "golden_slug": golden.slug,
                    "query_text": golden.query_text,
                    "actual_intent": actual_intent,
                    "actual_guardrail_blocked": state.guardrail_blocked,
                    "actual_guardrail_reason": state.guardrail_reason,
                    "actual_product_ids": actual_ids,
                    "actual_response_text": (actual_response or "")[:4000],
                    "passed": is_passed,
                    "failed_checks": failed_checks,
                    "latency_ms": latency_ms,
                    "phoenix_trace_id": trace_id,
                    "phoenix_trace_url": f"https://app.phoenix.arize.com/projects/{settings.phoenix_project_name}/traces/{trace_id}" if trace_id else None,
                    "thread_id": thread_id,
                }
            )
        try:
            span.set_attribute("evaluation.passed", passed)
            span.set_attribute("evaluation.failed", failed)
        except Exception:
            pass

    _update_run_counts(run_id, total=len(goldens), passed=passed, failed=failed)
    pass_rate = (passed / len(goldens) * 100) if goldens else 0.0
    return {
        "run_id": run_id,
        "total": len(goldens),
        "passed": passed,
        "failed": failed,
        "pass_rate": round(pass_rate, 1),
        "results": results,
    }
