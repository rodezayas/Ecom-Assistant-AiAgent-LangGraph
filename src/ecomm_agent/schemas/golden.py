"""Pydantic schemas for golden dataset (Supabase source of truth).

Mirrors the MVP table public.golden_queries created in Supabase SQL Editor.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


IntentType = Literal["product_search", "general_question", "out_of_domain"]
GuardrailReason = Literal["prompt_injection", "out_of_scope"]
Difficulty = Literal["easy", "medium", "hard", "adversarial"]
SizeType = Literal["S", "M", "L", "XL"]


class GoldenQueryBase(BaseModel):
    """Shared fields for create/update."""

    slug: str = Field(..., description="Unique slug, e.g. shoes-black-under-1500-M")
    query_text: str = Field(..., description="User message to test")
    expected_intent: IntentType
    expected_guardrail_blocked: bool = False
    expected_guardrail_reason: GuardrailReason | None = None
    expected_category: str | None = None
    expected_color: str | None = None
    expected_size: SizeType | None = None
    expected_price_ceiling: float | None = None
    expected_product_ids: list[str] = Field(default_factory=list)
    expected_response_contains: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    difficulty: Difficulty = "medium"
    is_active: bool = True


class GoldenQueryCreate(GoldenQueryBase):
    """Payload for inserting a new golden query."""


class GoldenQuery(GoldenQueryBase):
    """Golden query as stored in Supabase."""

    id: str
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class GoldenQueryList(BaseModel):
    """Paginated list response."""

    items: list[GoldenQuery]
    count: int


class EvaluationRunCreate(BaseModel):
    """Payload for creating an evaluation run."""

    dataset_version: str = "v1"
    git_commit: str | None = None
    model_config_data: dict = Field(default_factory=dict, alias="model_config")
    config_snapshot: dict = Field(default_factory=dict)
    run_by: str | None = None

    model_config = {"populate_by_name": True}


class EvaluationRun(BaseModel):
    """Evaluation run as stored."""

    id: str
    dataset_version: str
    git_commit: str | None = None
    model_config_data: dict | None = Field(default=None, alias="model_config")
    config_snapshot: dict | None = None
    total_queries: int = 0
    passed: int = 0
    failed: int = 0
    run_by: str | None = None
    run_at: datetime | None = None

    model_config = {"populate_by_name": True}


class EvaluationResult(BaseModel):
    """Evaluation result per query."""

    id: str | None = None
    run_id: str
    golden_query_id: str
    golden_slug: str
    query_text: str
    actual_intent: str | None = None
    actual_guardrail_blocked: bool | None = None
    actual_guardrail_reason: str | None = None
    actual_product_ids: list[str] = Field(default_factory=list)
    actual_response_text: str | None = None
    passed: bool
    failed_checks: list[str] = Field(default_factory=list)
    latency_ms: int | None = None
    retrieval_source: str | None = None
    llm_chosen_provider: str | None = None
    phoenix_trace_id: str | None = None
    phoenix_trace_url: str | None = None
    thread_id: str | None = None
    scored_at: datetime | None = None


class EvaluationSummary(BaseModel):
    """Summary returned by evaluation endpoint/CLI."""

    run_id: str | None
    total: int
    passed: int
    failed: int
    pass_rate: float
    results: list[EvaluationResult]
    error: str | None = None
