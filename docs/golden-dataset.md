# Golden Dataset — Source of Truth en Supabase

## 1. Propósito

Tabla `public.golden_queries` (MVP) es el **source of truth** para evaluación: cada fila define una query canónica + expectativas determinísticas (intent, guardrails, filtros, productos). Linkeable a Phoenix via `evaluation_results.phoenix_trace_id`.

## 2. Schema MVP

Ver prompt SQL en `docs/observability.md` o ejecuta el MVP:

```sql
-- public.golden_queries (ver prompt MVP mínimo)
id uuid PK, slug text unique, query_text text,
expected_intent (product_search|general_question|out_of_domain),
expected_guardrail_blocked bool, expected_guardrail_reason,
expected_category/color/size/price_ceiling,
expected_product_ids text[], expected_response_contains text[],
tags text[], difficulty, is_active, created_at/updated_at
```

## 3. Supabase Config

`.env` (ya normalizado en `src/ecomm_agent/core/config.py:127`):

```
SUPABASE_URL=https://<ref>.supabase.co
SUPABASE_PROJECT_ID=<ref>
SUPABASE_ANON_KEY=eyJ... (read)
SUPABASE_SERVICE_ROLE_KEY=eyJ... (write, server-side)
SUPABASE_SERVICE_ROLE=... (alias sin _KEY, compat)
```

Resolver: `resolved_supabase_url` usa `SUPABASE_URL` o deriva de `PROJECT_ID`. `resolved_supabase_service_key` acepta ambas vars.

## 4. Servicios

- `src/ecomm_agent/services/supabase.py` — `get_supabase_client()` singleton, `is_supabase_configured()`
- `src/ecomm_agent/schemas/golden.py` — `GoldenQuery`, `GoldenQueryCreate`, `GoldenQueryList`
- `src/ecomm_agent/services/golden_dataset.py` — `list_golden_queries()`, `get_by_slug/id()`, `create_golden_query()`, `evaluate_query_against_golden()`, `count_golden_queries()`

Fail-safe: si Supabase no configurado, servicios retornan `[]`/`None` y API responde `503`.

## 5. API

`src/ecomm_agent/api/routes/golden.py` (registrada en `src/ecomm_agent/main.py:64`):

- `GET /api/golden?active_only=true&limit=100&offset=0&intent=product_search` — lista
- `GET /api/golden/count` — conteo
- `GET /api/golden/by-slug/{slug}` — por slug
- `GET /api/golden/{id}` — por id
- `POST /api/golden` — crea (requiere service_role)

CORS `allow_methods` ampliado a `["GET","POST"]` para este router.

## 6. Seed

`src/ecomm_agent/scripts/seed_golden.py` — 8 queries canónicas:

- `shoes-black-under-1500-M`, `tshirt-blue-M-stock`, `jacket-under-3000`
- `policy-shipping-international`, `policy-returns-30days`, `size-guide-jeans`
- `out-of-scope-crypto`, `prompt-injection-ignore`

Ejecuta:

```bash
uv run ecomm-agent seed-golden
# o
uv run python -m ecomm_agent.scripts.seed_golden
```

Requiere `SUPABASE_URL` + `SERVICE_ROLE` y tabla creada. Idempotente (skip si `slug` existe).

## 7. Evaluación

Implementada en `src/ecomm_agent/services/evaluation.py:124`:

- `run_golden_evaluation(limit, intent, dataset_version)` itera `list_golden_queries()`, corre `process_user_message(thread_id=eval-<slug>)`, compara con `_check_golden` (intent, guardrail, productos, response_contains), mide `latency_ms`, extrae `phoenix_trace_id` del OTEL context y persiste en `evaluation_runs`/`evaluation_results` (fail-safe si tablas no existen).
- Cada query se traza como `evaluation.query:<slug>` y el run como `evaluation.run`.

**Tablas evaluación** (ejecutar en Supabase SQL Editor — `docs/evaluation-sql.md` / `supabase/migrations/20250918_golden_evaluation.sql`):

```sql
create table evaluation_runs (...) — ver archivo
create table evaluation_results (...) — ver archivo
```

**CLI**

```bash
uv run ecomm-agent eval-golden                 # 8/8
uv run ecomm-agent eval-golden --limit 2 --json
uv run ecomm-agent eval-golden --intent product_search
```

**API**

```bash
curl -X POST http://localhost:8000/api/golden/evaluate
curl -X POST "http://localhost:8000/api/golden/evaluate?limit=2&intent=product_search"
curl http://localhost:8000/api/golden/evaluation/runs?limit=20
curl http://localhost:8000/api/golden/evaluation/results/<run_id>
```

Las respuestas incluyen `phoenix_trace_id`/`phoenix_trace_url` (`https://app.phoenix.arize.com/projects/<project>/traces/<trace_id>`) para correlacionar cada evaluación con su traza Phoenix.

## 8. Verificación

```bash
# 1. Listar
curl http://localhost:8000/api/golden
# 2. Por slug
curl http://localhost:8000/api/golden/by-slug/shoes-black-under-1500-M
# 3. Crear
curl -X POST http://localhost:8000/api/golden -H 'content-type: application/json' -d '{"slug":"test-1","query_text":"blue shoes?","expected_intent":"product_search"}'
```

## 9. Render

`render.yaml` ya incluye `SUPABASE_URL/ANON_KEY/SERVICE_ROLE_KEY/PROJECT_ID` como `sync:false`.
