# Golden Dataset — Source of Truth in Supabase

## 1. Purpose

Table `public.golden_queries` (MVP) is the **source of truth** for evaluation: each row defines a canonical query + deterministic expectations (intent, guardrails, filters, products). Linkable to Phoenix via `evaluation_results.phoenix_trace_id`.

## 2. MVP Schema

See migration or create with:

```sql
-- public.golden_queries (see MVP prompt for full DDL)
id uuid PK, slug text unique, query_text text,
expected_intent (product_search|general_question|out_of_domain),
expected_guardrail_blocked bool, expected_guardrail_reason,
expected_category/color/size/price_ceiling,
expected_product_ids text[], expected_response_contains text[],
tags text[], difficulty, is_active, created_at/updated_at
```

## 3. Supabase Config

`.env` (normalized in `src/ecomm_agent/core/config.py:127`):

```
SUPABASE_URL=https://<ref>.supabase.co
SUPABASE_PROJECT_ID=<ref>
SUPABASE_ANON_KEY=eyJ... (read)
SUPABASE_SERVICE_ROLE_KEY=eyJ... (write, server-side, short-lived)
SUPABASE_SERVICE_ROLE=... (alias without _KEY, compat)
```

Resolver: `resolved_supabase_url` uses `SUPABASE_URL` or derives from `PROJECT_ID`. `resolved_supabase_service_key` accepts both vars. RLS policies in `supabase/migrations/20250919_002_rls.sql` allow anon read of active queries, service_role all.

## 4. Services

- `src/ecomm_agent/services/supabase.py` — `get_supabase_client()` singleton, `is_supabase_configured()`
- `src/ecomm_agent/schemas/golden.py` — `GoldenQuery`, `GoldenQueryCreate`, `GoldenQueryList`
- `src/ecomm_agent/services/golden_dataset.py` — `list_golden_queries()`, `get_by_slug/id()`, `create_golden_query()`, `count_golden_queries()`

Fail-safe: when Supabase is not configured, services return `[]`/`None` and the API returns `503`.

## 5. API

`src/ecomm_agent/api/routes/golden.py` (registered in `src/ecomm_agent/main.py:65`):

- `GET /api/golden?active_only=true&limit=100&offset=0&intent=product_search` — list (rate-limited)
- `GET /api/golden/count` — count
- `GET /api/golden/by-slug/{slug}` — by slug
- `GET /api/golden/{id}` — by id
- `POST /api/golden` — create (requires `Authorization: Bearer $ADMIN_API_KEY`)
- `POST /api/golden/evaluate` — run evaluation (requires admin key)
- `GET /api/golden/evaluation/runs` — recent runs
- `GET /api/golden/evaluation/results/{run_id}` — results for a run

Rate-limited per IP `src/ecomm_agent/api/security.py:56`; verbose DB errors are sanitized.

## 6. Seed

`src/ecomm_agent/scripts/seed_golden.py` — 8 canonical queries:

- `shoes-black-under-1500-M`, `tshirt-blue-M-stock`, `jacket-under-3000`
- `policy-shipping-international`, `policy-returns-30days`, `size-guide-jeans`
- `out-of-scope-crypto`, `prompt-injection-ignore`

Run:

```bash
uv run ecomm-agent seed-golden
# or
uv run python -m ecomm_agent.scripts.seed_golden
```

Requires `SUPABASE_URL` + `SERVICE_ROLE` and tables created. Idempotent (skips if `slug` exists).

## 7. Evaluation

Implemented in `src/ecomm_agent/services/evaluation.py:124`:

- `run_golden_evaluation(limit, intent, dataset_version)` iterates `list_golden_queries()`, runs `process_user_message(thread_id=eval-<slug>)`, compares via `_check_golden` (intent, guardrail, products, response_contains), measures `latency_ms`, extracts `phoenix_trace_id` from OTEL context and persists in `evaluation_runs`/`evaluation_results` (fail-safe if tables are missing).
- Each query is traced as `evaluation.query:<slug>` and the run as `evaluation.run`.

**Evaluation tables** (`supabase/migrations/20250918_golden_evaluation.sql` + RLS `20250919_002_rls.sql`):

```sql
create table evaluation_runs (...)  -- see file
create table evaluation_results (...)  -- see file
```

**CLI**

```bash
uv run ecomm-agent eval-golden                 # 8/8 when seeded
uv run ecomm-agent eval-golden --limit 2 --json
uv run ecomm-agent eval-golden --intent product_search
```

**API**

```bash
curl -X POST http://localhost:8000/api/golden/evaluate -H "Authorization: Bearer $ADMIN_API_KEY"
curl -X POST "http://localhost:8000/api/golden/evaluate?limit=2&intent=product_search" -H "Authorization: Bearer $ADMIN_API_KEY"
curl http://localhost:8000/api/golden/evaluation/runs?limit=20
curl http://localhost:8000/api/golden/evaluation/results/<run_id>
```

Responses include `phoenix_trace_id`/`phoenix_trace_url` (`https://app.phoenix.arize.com/projects/<project>/traces/<trace_id>`) to correlate each evaluation with its Phoenix trace.

## 8. Verification

```bash
# 1. List
curl http://localhost:8000/api/golden
# 2. By slug
curl http://localhost:8000/api/golden/by-slug/shoes-black-under-1500-M
# 3. Create (requires admin key)
curl -X POST http://localhost:8000/api/golden -H 'content-type: application/json' -H "Authorization: Bearer $ADMIN_API_KEY" -d '{"slug":"test-1","query_text":"blue shoes?","expected_intent":"product_search"}'
```

## 9. Render

`render.yaml` includes `SUPABASE_URL/ANON_KEY/SERVICE_ROLE_KEY/PROJECT_ID` as `sync:false` plus `ADMIN_API_KEY` and `TELEGRAM_WEBHOOK_SECRET_TOKEN`.
