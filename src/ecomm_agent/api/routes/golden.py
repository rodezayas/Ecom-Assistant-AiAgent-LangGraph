"""Golden dataset API — read (public) + write (service_role).

Exposes the Supabase source of truth for evaluation. List/get are public-ish
(anon key), create requires service_role (server-side).
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from ecomm_agent.api.security import check_rate_limit, verify_admin_key
from ecomm_agent.core.config import settings
from ecomm_agent.schemas.golden import EvaluationSummary, GoldenQuery, GoldenQueryCreate
from ecomm_agent.services.golden_dataset import (
    count_golden_queries,
    create_golden_query,
    get_golden_query_by_id,
    get_golden_query_by_slug,
    list_golden_queries,
)
from ecomm_agent.services.supabase import is_supabase_configured

router = APIRouter(prefix="/api/golden", tags=["golden"])
logger = logging.getLogger(__name__)


@router.get("", response_model=list[GoldenQuery])
def list_golden(
    request: Request,
    active_only: bool = Query(default=True),
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    intent: str | None = None,
) -> list[GoldenQuery]:
    """List golden queries (MVP table). 503 when Supabase not configured."""
    check_rate_limit(request, settings.rate_limit_golden_per_minute)
    if not is_supabase_configured():
        raise HTTPException(status_code=503, detail="Supabase not configured")
    return list_golden_queries(active_only=active_only, limit=limit, offset=offset, intent=intent)


@router.get("/count")
def golden_count(request: Request) -> dict[str, int]:
    """Count active golden queries."""
    check_rate_limit(request, settings.rate_limit_golden_per_minute)
    if not is_supabase_configured():
        raise HTTPException(status_code=503, detail="Supabase not configured")
    return {"count": count_golden_queries()}


@router.get("/by-slug/{slug}", response_model=GoldenQuery)
def get_by_slug(slug: str, request: Request) -> GoldenQuery:
    """Get golden query by slug."""
    check_rate_limit(request, settings.rate_limit_golden_per_minute)
    if not is_supabase_configured():
        raise HTTPException(status_code=503, detail="Supabase not configured")
    item = get_golden_query_by_slug(slug)
    if item is None:
        raise HTTPException(status_code=404, detail="golden query not found")
    return item


@router.get("/{query_id}", response_model=GoldenQuery)
def get_by_id(query_id: str, request: Request) -> GoldenQuery:
    """Get golden query by id."""
    check_rate_limit(request, settings.rate_limit_golden_per_minute)
    if not is_supabase_configured():
        raise HTTPException(status_code=503, detail="Supabase not configured")
    item = get_golden_query_by_id(query_id)
    if item is None:
        raise HTTPException(status_code=404, detail="golden query not found")
    return item


@router.post("", response_model=GoldenQuery, status_code=201)
def create_golden(payload: GoldenQueryCreate, request: Request, _auth: None = Depends(verify_admin_key)) -> GoldenQuery:
    """Create a golden query (requires admin key)."""
    check_rate_limit(request, settings.rate_limit_golden_per_minute)
    if not is_supabase_configured():
        raise HTTPException(status_code=503, detail="Supabase not configured")
    created = create_golden_query(payload)
    if created is None:
        raise HTTPException(status_code=500, detail="Failed to create golden query (check service_role key)")
    return created


@router.post("/evaluate", response_model=EvaluationSummary)
def evaluate_golden(
    request: Request,
    limit: int | None = Query(default=None, ge=1, le=200),
    intent: str | None = Query(default=None),
    dataset_version: str = Query(default="v1"),
    _auth: None = Depends(verify_admin_key),
) -> EvaluationSummary:
    """Run golden evaluation synchronously (iterates Supabase golden_queries).

    Traces each query with Phoenix (evaluation.query:<slug>) and persists
    results to evaluation_runs/results when those tables exist.
    """
    check_rate_limit(request, settings.rate_limit_golden_per_minute)
    if not is_supabase_configured():
        raise HTTPException(status_code=503, detail="Supabase not configured")
    from ecomm_agent.services.evaluation import run_golden_evaluation

    summary = run_golden_evaluation(limit=limit, intent=intent, dataset_version=dataset_version)
    if summary.get("error"):
        raise HTTPException(status_code=404, detail=summary["error"])
    return EvaluationSummary.model_validate(summary)


@router.get("/evaluation/runs")
def list_evaluation_runs(request: Request, limit: int = Query(default=20, ge=1, le=100)) -> list[dict]:
    """List recent evaluation runs (requires table)."""
    check_rate_limit(request, settings.rate_limit_golden_per_minute)
    if not is_supabase_configured():
        raise HTTPException(status_code=503, detail="Supabase not configured")
    from ecomm_agent.services.supabase import get_supabase_client

    client = get_supabase_client()
    if client is None:
        raise HTTPException(status_code=503, detail="Supabase not configured")
    try:
        resp = client.table("evaluation_runs").select("*").order("run_at", desc=True).limit(limit).execute()
        return resp.data or []
    except Exception as exc:
        logger.warning("list_evaluation_runs failed", extra={"error": str(exc)})
        raise HTTPException(status_code=500, detail="evaluation storage unavailable")


@router.get("/evaluation/results/{run_id}")
def list_evaluation_results(run_id: str, request: Request) -> list[dict]:
    """List results for a run."""
    check_rate_limit(request, settings.rate_limit_golden_per_minute)
    if not is_supabase_configured():
        raise HTTPException(status_code=503, detail="Supabase not configured")
    from ecomm_agent.services.supabase import get_supabase_client

    client = get_supabase_client()
    if client is None:
        raise HTTPException(status_code=503, detail="Supabase not configured")
    try:
        resp = client.table("evaluation_results").select("*").eq("run_id", run_id).order("golden_slug").execute()
        return resp.data or []
    except Exception as exc:
        logger.warning("list_evaluation_results failed", extra={"error": str(exc)})
        raise HTTPException(status_code=500, detail="evaluation storage unavailable")
