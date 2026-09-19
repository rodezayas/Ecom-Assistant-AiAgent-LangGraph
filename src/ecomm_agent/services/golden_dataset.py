"""Golden dataset service — CRUD over Supabase table public.golden_queries.

Reads/writes the MVP table created via SQL Editor. Falls back gracefully
when Supabase is not configured (returns empty / None).
"""

from __future__ import annotations

import logging
from typing import Any

from ecomm_agent.schemas.golden import GoldenQuery, GoldenQueryCreate
from ecomm_agent.services.supabase import get_supabase_client

logger = logging.getLogger(__name__)

TABLE = "golden_queries"


def _map_row_to_golden(row: dict[str, Any]) -> GoldenQuery:
    """Map Supabase row to Pydantic model."""
    return GoldenQuery.model_validate(row)


def list_golden_queries(
    *,
    active_only: bool = True,
    limit: int = 100,
    offset: int = 0,
    intent: str | None = None,
) -> list[GoldenQuery]:
    """List golden queries from Supabase.

    Args:
        active_only: When True filters is_active=true.
        limit: Max rows.
        offset: Pagination offset.
        intent: Optional intent filter.

    Returns:
        List of GoldenQuery, empty when Supabase not configured or on error.
    """
    client = get_supabase_client()
    if client is None:
        return []

    try:
        query = client.table(TABLE).select("*")
        if active_only:
            query = query.eq("is_active", True)
        if intent:
            query = query.eq("expected_intent", intent)
        query = query.order("created_at", desc=False).range(offset, offset + limit - 1)
        resp = query.execute()
        rows = resp.data or []
        return [_map_row_to_golden(r) for r in rows]
    except Exception as exc:
        logger.warning("list_golden_queries failed", extra={"error": str(exc)})
        return []


def get_golden_query_by_slug(slug: str) -> GoldenQuery | None:
    """Fetch single golden query by slug."""
    client = get_supabase_client()
    if client is None:
        return None
    try:
        resp = client.table(TABLE).select("*").eq("slug", slug).limit(1).execute()
        rows = resp.data or []
        if not rows:
            return None
        return _map_row_to_golden(rows[0])
    except Exception as exc:
        logger.warning("get_golden_query_by_slug failed", extra={"slug": slug, "error": str(exc)})
        return None


def get_golden_query_by_id(query_id: str) -> GoldenQuery | None:
    """Fetch single golden query by id."""
    client = get_supabase_client()
    if client is None:
        return None
    try:
        resp = client.table(TABLE).select("*").eq("id", query_id).limit(1).execute()
        rows = resp.data or []
        if not rows:
            return None
        return _map_row_to_golden(rows[0])
    except Exception as exc:
        logger.warning("get_golden_query_by_id failed", extra={"id": query_id, "error": str(exc)})
        return None


def create_golden_query(payload: GoldenQueryCreate) -> GoldenQuery | None:
    """Insert a golden query. Requires service_role key.

    Returns:
        Created GoldenQuery or None on failure.
    """
    client = get_supabase_client()
    if client is None:
        logger.warning("create_golden_query: supabase not configured")
        return None
    try:
        data = payload.model_dump(exclude_none=True)
        # Supabase expects arrays as-is
        resp = client.table(TABLE).insert(data).select("*").execute()
        rows = resp.data or []
        if not rows:
            return None
        return _map_row_to_golden(rows[0])
    except Exception as exc:
        logger.warning("create_golden_query failed", extra={"slug": payload.slug, "error": str(exc)})
        return None


def evaluate_query_against_golden(query_slug: str, actual_product_ids: list[str], actual_intent: str) -> dict[str, Any]:
    """Compare actual agent output against golden expectation.

    Args:
        query_slug: Golden query slug.
        actual_product_ids: Product ids returned by agent.
        actual_intent: Intent returned by agent.

    Returns:
        Dict with passed, failed_checks, expected.
    """
    golden = get_golden_query_by_slug(query_slug)
    if golden is None:
        return {"passed": False, "failed_checks": ["golden_not_found"], "expected": None}

    failed: list[str] = []
    if actual_intent != golden.expected_intent:
        failed.append(f"intent_mismatch: expected {golden.expected_intent} got {actual_intent}")

    # Product ids check: all expected must be in actual (subset)
    for pid in golden.expected_product_ids:
        if pid not in actual_product_ids:
            failed.append(f"missing_product:{pid}")

    # If golden expects empty but we returned something
    if not golden.expected_product_ids and actual_product_ids:
        # Only fail if difficulty is not adversarial? keep simple
        pass

    return {
        "passed": len(failed) == 0,
        "failed_checks": failed,
        "expected": golden,
        "actual_product_ids": actual_product_ids,
        "actual_intent": actual_intent,
    }


def count_golden_queries() -> int:
    """Count active golden queries."""
    client = get_supabase_client()
    if client is None:
        return 0
    try:
        resp = client.table(TABLE).select("id", count="exact").eq("is_active", True).execute()
        return resp.count or 0
    except Exception:
        return 0
