# Intelligent Ecom Agent — Alta Norma Fashion

Telegram sales assistant that never hallucinates price, size, color, stock, or product URLs — all facts come from the verified catalog and deterministic resolvers.

## Overview

- **What:** FastAPI + LangGraph assistant on Telegram with a read-only catalog API for a Lovable-hosted storefront, backed by a JSON catalog, Markdown knowledge base, optional Chroma retrieval, and Supabase + Phoenix evaluation.
- **Who:** Shoppers via `t.me/AltaNormaFashion_bot`; developers/product teams via `GET /api/catalog` for website product pages.
- **What it does:** Routes intent → retrieves verified products/knowledge (vector + lexical) → enforces deterministic guardrails → generates a Telegram reply with verified URLs → traces every turn → evaluates against a Supabase golden dataset.
- **Why:** Demonstrates production-minded AI engineering: the LLM is used only for language, while inventory, pricing, and URLs are queried deterministically.

## What Problem Does It Solve?

- **Current problem:** Retail chatbots sound fluent but invent prices, availability, shipping promises, and product links.
- **Existing workflow:** A customer asks in Telegram ("do you have blue t-shirt in M?" or "shipping to Argentina?"); a single-prompt bot hallucinates or gives a generic answer.
- **Pain point:** No separation between what the model generates and what the system knows; no guardrails; no observability; no regression testing.
- **Consequence:** False availability claims, wrong pricing, brand distrust, and no way to measure degradation when prompts or models change.
- **How this system improves it:** Verified catalog is the source of truth; Markdown KB for policies; deterministic guardrails blocked before generation; provider fallback; every turn traced in Phoenix; every golden query evaluated in Supabase. Conditional result: `8/8` on the seeded golden dataset when `index-rag` and Supabase are configured.

## Business Rules

| Rule | Description | Enforcement |
|------|-------------|-------------|
| BR-001 | Prices, sizes, colors, stock, and product variants come from deterministic catalog data, never from the LLM | `src/ecomm_agent/services/catalog.py:36,72,176`, `src/ecomm_agent/services/inventory.py:11`, `src/ecomm_agent/rag/vectorstore.py:48` embeds only name/description/category/tags; `src/ecomm_agent/services/llm.py:131` system prompt; `tests/test_catalog.py` |
| BR-002 | Catalog is the single source of truth for products; website and agent read the same file | `src/ecomm_agent/services/catalog.py:72` `load_catalog`, `src/ecomm_agent/api/routes/catalog.py:18`, `src/ecomm_agent/core/config.py:89` `CATALOG_PATH` |
| BR-003 | Policy, FAQ, and size guidance come only from the verified Markdown knowledge base | `src/ecomm_agent/rag/vectorstore.py:171`, `src/ecomm_agent/services/retrieval.py:148` filtered by `source_type`; `src/ecomm_agent/agents/nodes/response_generator.py:81` |
| BR-004 | Prompt injection attempts are blocked deterministically | `src/ecomm_agent/core/domain.py:117` 30 patterns, `src/ecomm_agent/services/guardrails.py:93` substring check, `src/ecomm_agent/agents/nodes/guardrails.py:33`; `tests/test_guardrails.py:27` |
| BR-005 | Out-of-scope requests are rejected when ≥2 unknown meaningful terms and unknown ≥ known signals | `src/ecomm_agent/services/guardrails.py:108,147` `build_allowed_vocabulary` vs token counts; budget signal requires an in-domain token `guardrails.py:139` |
| BR-006 | Intent is deterministic via `COMMERCE_TERMS` → `product_search`, else `general_question` (guardrail can force `out_of_domain`) | `src/ecomm_agent/agents/nodes/intent_router.py:32`, `src/ecomm_agent/core/domain.py:15` |
| BR-007 | Retrieval is filtered deterministically by category synonym, color, size normalization, and price ceiling | `src/ecomm_agent/services/catalog.py:46,176` `CATEGORY_SYNONYMS`, `SIZE_NORMALIZATION`, `PRICE_PATTERN`; `src/ecomm_agent/services/retrieval.py:63` |
| BR-008 | Product page URL is deterministic `{FRONTEND_BASE_URL}/products/{id}` or `None` when not configured; never from LLM | `src/ecomm_agent/services/urls.py:11` `build_product_page_url`; validated in `src/ecomm_agent/services/llm.py:299` `_validate_llm_output` |
| BR-009 | Provider failover is Anthropic → Groq → deterministic fallback | `src/ecomm_agent/services/llm.py:299` `generate_response_text`, `src/ecomm_agent/services/chatbot.py:80` `build_reply_text`; `tests/test_llm_fallback.py` |
| BR-010 | Public web access is limited to read-only catalog and golden dataset reads; writes require admin auth | `src/ecomm_agent/api/routes/catalog.py:27` GET only (405 on POST, 400 on bad id), `src/ecomm_agent/api/routes/golden.py:65,76` `verify_admin_key` `src/ecomm_agent/api/security.py:38` |
| BR-011 | Every turn emits a Phoenix trace with `thread_id`; `input.value`/`output.value` only when `PHOENIX_RECORD_CONTENT=true` | `src/ecomm_agent/observability/tracing.py:34`, `src/ecomm_agent/api/routes/telegram.py:37`, `src/ecomm_agent/core/config.py:136` default `false` |
| BR-012 | Golden evaluation passes only when `intent`, `guardrail_blocked`, `guardrail_reason`, and all `expected_product_ids` match and `expected_response_contains` is present | `src/ecomm_agent/services/evaluation.py:36` `_check_golden`; `supabase/migrations/20250918_golden_evaluation.sql:3` |
| BR-013 | Telegram webhook is authenticated via secret token and rate-limited; duplicate updates are deduplicated | `src/ecomm_agent/api/security.py:12` `verify_telegram_secret`, `src/ecomm_agent/api/routes/telegram.py:24` `check_rate_limit`, `src/ecomm_agent/services/telegram.py:62` `secret_token` |

TBD where deterministic enforcement is incomplete: discount/shipping promise hallucination is constrained by prompt only and validated by URL/price checks in `llm.py:299`.

## System Design

### Components

| Component | Responsibility | Inputs | Outputs | Dependencies |
|-----------|---------------|--------|---------|--------------|
| FastAPI App | Receives webhooks, exposes health/catalog/golden, applies CORS + security headers | HTTP JSON (`TelegramUpdate`, query params) | JSON responses, 202/4xx/5xx | `src/ecomm_agent/main.py:65`, `src/ecomm_agent/api/security.py`, `pydantic-settings` |
| Telegram Adapter | Sends `sendMessage`, registers webhook with secret token | `chat_id`, `text`, `webhook_url` | Telegram API JSON | `src/ecomm_agent/services/telegram.py:17`, `httpx`, `TELEGRAM_BOT_TOKEN` `core/config.py:65` |
| LangGraph Orchestrator | Runs `intent_router → retrieval → guardrails → response_generator|fallback` | `AgentState(thread_id, user_message)` | `AgentState(intent, retrieved_products, guardrail_blocked, response_text)` | `src/ecomm_agent/agents/graph.py:68`, `src/ecomm_agent/services/chatbot.py:20` |
| Intent Router | Deterministic intent via `COMMERCE_TERMS` | `user_message` | `intent` | `src/ecomm_agent/agents/nodes/intent_router.py:13` |
| Retriever | Semantic (Chroma) → lexical fallback with deterministic filters; knowledge RAG for policies | `user_message`, `catalog`, `KB docs`, `vector_store` | `retrieved_products`, `retrieved_knowledge`, `requested_*`, `filters` | `src/ecomm_agent/services/retrieval.py:63`, `src/ecomm_agent/rag/vectorstore.py:268`, `src/ecomm_agent/services/catalog.py:176` |
| Guardrails | Prompt injection (30 patterns) + out-of-scope vocabulary check | `user_message`, `allowed_vocabulary` | `guardrail_blocked`, `guardrail_reason=prompt_injection|out_of_scope` | `src/ecomm_agent/services/guardrails.py:158`, `src/ecomm_agent/core/domain.py:117` |
| Catalog Source of Truth | JSON file, validated by Pydantic, canonicalized path | `CATALOG_PATH` | `list[Product]` | `src/ecomm_agent/schemas/catalog.py`, `data/catalog/products.json` |
| Knowledge Base | Markdown policies/FAQ/size guide → RAG documents | `KNOWLEDGE_BASE_DIR` | `list[KnowledgeDoc]` | `src/ecomm_agent/rag/vectorstore.py:144` |
| URL Resolver | Deterministic product page URL or None | `product.id`, `FRONTEND_BASE_URL` | `url` | `src/ecomm_agent/services/urls.py:11` |
| LLM Coupler | Builds system+user prompt from verified state, calls Anthropic→Groq, validates output for hallucinated URLs/prices | `AgentState` | `response_text | None` (validated) | `src/ecomm_agent/services/llm.py:150,224,299` |
| Observability | OTLP/HTTP to Phoenix Cloud via `arize-phoenix-otel` + `LangChainInstrumentor` | spans from every node | traces in Phoenix | `src/ecomm_agent/observability/tracing.py:65`, `src/ecomm_agent/main.py:39` |
| Golden Dataset | Supabase CRUD + evaluation runner persisting `evaluation_runs/results` | `golden_queries` | `EvaluationSummary` with `phoenix_trace_id` | `src/ecomm_agent/services/supabase.py`, `src/ecomm_agent/services/evaluation.py:124` |

### Architecture

```mermaid
flowchart TD
    TG[Telegram User] --> WH[FastAPI POST /webhook/telegram<br/>api/routes/telegram.py:24<br/>verify_telegram_secret + rate_limit + dedup]
    WH --> CB[chatbot.process_user_message<br/>services/chatbot.py:20<br/>StateGraph]
    CB --> IR[intent_router<br/>agents/nodes/intent_router.py:32<br/>COMMERCE_TERMS]
    IR -->|product_search / general_question| RT[retrieval<br/>agents/nodes/retrieval.py<br/>retrieve_products / retrieve_knowledge]
    IR -->|out_of_domain| GR[guardrails<br/>agents/nodes/guardrails.py]
    RT --> GR
    GR -->|blocked or no_results| FB[fallback<br/>agents/nodes/fallback.py<br/>honest deterministic reply]
    GR -->|allowed and has results| RG[response_generator<br/>agents/nodes/response_generator.py<br/>verified context rendering]
    RG --> LLM{build_reply_text<br/>services/llm.py:299<br/>_validate_llm_output}
    FB --> LLM
    LLM -->|Anthropic OK| TGReply[Telegram sendMessage<br/>services/telegram.py:17]
    LLM -->|Anthropic fail| GQ[Groq<br/>services/llm.py:224]
    GQ -->|Groq OK| TGReply
    GQ -->|both fail| DET[Deterministic state.response_text<br/>services/chatbot.py:80]
    DET --> TGReply
    RT -->|vector| CH[(Chroma persistent<br/>rag/vectorstore.py:268<br/>VECTOR_STORE_PATH)]
    RT -->|lexical fallback| CAT[(Catalog JSON<br/>data/catalog/products.json<br/>services/catalog.py:72)]
    RT --> KB[(Markdown KB<br/>data/knowledge<br/>rag/vectorstore.py:144)]
    CAT --> RG
    KB --> RG
    CAT --> API1[GET /api/catalog<br/>api/routes/catalog.py:27]
    CAT --> API2[GET /api/catalog/{id}<br/>400/404]
    WH -.-> PH1[Phoenix span webhook.telegram]
    CB -.-> PH2[Phoenix span agent.graph]
    IR & RT & GR & RG & FB & LLM -.-> PH3[Phoenix spans intent / retrieval / guardrails / llm.*]
    EV[Evaluation Runner<br/>services/evaluation.py:124] -->|list| SUP[(Supabase public.golden_queries)]
    EV -->|invoke| CB
    EV -.-> PH4[Phoenix evaluation.run / evaluation.query:slug]
    EV -->|persist| SUP2[(evaluation_runs / evaluation_results<br/>supabase/migrations/20250918_golden_evaluation.sql)]
    SUP --> API3[GET /api/golden* / POST with ADMIN_API_KEY]
    API1 & API2 --> FE[Lovable Frontend<br/>FRONTEND_BASE_URL/products/{id}<br/>services/urls.py:11]
```

Correct order is `intent_router → retrieval → guardrails → response_generator|fallback → llm`, matching `src/ecomm_agent/agents/graph.py:99`.

## Tech Stack

| Layer | Technology | Version / Path | Purpose |
|-------|------------|----------------|---------|
| Language | Python | 3.11-slim (`Dockerfile:1`) | Runtime |
| Web | FastAPI, Uvicorn[standard], httpx | `fastapi>=0.139.0`, `uvicorn>=0.35.0`, `httpx>=0.28.1` `pyproject.toml:7` | Webhook + external calls |
| Security | slowapi (rate limit), CORSMiddleware, security headers | `slowapi>=0.1.9` | Rate limiting, CORS, hardening |
| Agent | LangGraph, LangChain, langchain-chroma, openai | `langgraph>=1.2.7`, `langchain>=0.3.27`, `langchain-chroma>=0.2.5`, `openai>=1.95.1`, `chromadb>=1.0.15` | Orchestration + RAG |
| Validation | Pydantic, pydantic-settings | `pydantic-settings>=2.10.1` | Schemas + env |
| Embeddings | OpenAI Embeddings | `text-embedding-3-small` `core/config.py:35` | Vector indexing only |
| Generation | Anthropic (primary) + Groq (fallback) | `claude-sonnet-4-20250514`, `llama-3.3-70b-versatile` `core/config.py:41,56` | Reply generation + validation `llm.py:299` |
| Catalog | JSON file + Pydantic `Product` | `data/catalog/products.json` | Source of truth |
| Knowledge | Markdown files | `data/knowledge/` | Policy/FAQ/size |
| Observability | Arize Phoenix Cloud + OpenTelemetry | `arize-phoenix-otel>=0.8.0`, `opentelemetry-*>=1.27.0`, `openinference-*` | Tracing `observability/tracing.py:65` |
| Evaluation | Supabase + PostgREST | `supabase>=2.15.0` | Golden dataset + history |
| Infra | Docker, docker-compose, Render | `Dockerfile`, `docker-compose.yml`, `render.yaml` | Container + deploy |
| Tooling | uv, hatchling, pytest, ruff | `uv.lock` `--frozen` | Build/test/lint |

## Data Flow

1. Telegram posts JSON to `POST /webhook/telegram` `src/ecomm_agent/api/routes/telegram.py:24`: validated as `TelegramUpdate` `src/ecomm_agent/schemas/telegram.py:49` (`text` `max_length=4000`), `chat.id` becomes `thread_id`. Header `X-Telegram-Bot-Api-Secret-Token` verified against `TELEGRAM_WEBHOOK_SECRET_TOKEN` `src/ecomm_agent/api/security.py:12`; per-IP rate limit checked; duplicate `update_id` dedup window 600s.
2. `process_user_message(thread_id, text)` `src/ecomm_agent/services/chatbot.py:20` does `GRAPH.invoke(AgentState)` → `intent_router` (`COMMERCE_TERMS` check) → `retrieval` (tries `retrieve_products` vector+lexical `services/retrieval.py:63` with filters `services/catalog.py:176`; `retrieve_knowledge` `retrieval.py:148`) → `guardrails` (injection then out-of-scope `services/guardrails.py:158`) forces `intent=out_of_domain` when `out_of_scope` → `response_generator` or `fallback` writes `response_text`.
3. `build_reply_text(state)` `src/ecomm_agent/services/chatbot.py:80` calls `generate_response_text(state)` `src/ecomm_agent/services/llm.py:299`: builds `_build_product_context` deterministically from `filter_available_variants` `services/inventory.py:11` and `build_product_page_url` `services/urls.py:11`; `_build_user_prompt` + `_build_system_prompt` → Anthropic `services/llm.py:150`; on failure Groq `llm.py:224`; both outputs validated by `_validate_llm_output` (hallucinated URLs/prices fall back to `state.response_text`).
4. `send_text_message(chat_id, response_text)` `src/ecomm_agent/services/telegram.py:17` posts to `https://api.telegram.org/bot{token}/sendMessage`; webhook returns `202` (verbose in dev, minimized in production `src/ecomm_agent/api/routes/telegram.py:115`). `PHOENIX_ENABLED` spans `webhook.telegram → agent.graph → intent_router/retrieval/guardrails/llm.* → telegram.sendMessage` `src/ecomm_agent/observability/tracing.py:65`.

## Decisions

See `ADR.md` for historical log. Current highlights:

1. **LangGraph over single prompt chain** — explicit nodes for intent, retrieval, guardrails, response, fallback enable inspection and safer extensions.
2. **Deterministic catalog over LLM facts** — highest hallucination risk fields come from `load_catalog` and `filter_available_variants`, never from generation.
3. **Guardrails before generation, after retrieval** — graph order `intent_router → retrieval → guardrails` `agents/graph.py:99` preserves cheap blocking while allowing retrieval context for fallback honesty.
4. **Chroma as optional with lexical fallback** — works when `data/vectorstore` not indexed; full semantic indexing via `uv run ecomm-agent index-rag`.
5. **Anthropic primary with Groq fallback + LLM output validation** — `llm.py:299` validates URLs and price hallucinations deterministically after generation.
6. **OpenAI only for embeddings** — `OpenAIEmbeddings` `rag/vectorstore.py:240` isolated to retrieval.
7. **Read-only catalog API** — `GET /api/catalog*` `api/routes/catalog.py:27` shares the same source-of-truth as the agent.
8. **Phoenix Cloud OTLP/HTTP** — `arize-phoenix-otel` + `LangChainInstrumentor`, no local collector; `PHOENIX_RECORD_CONTENT=false` by default `core/config.py:136`.
9. **Supabase as golden source** — `public.golden_queries` + `evaluation_runs/results` `supabase/migrations/20250918_golden_evaluation.sql:3`; RLS in `20250919_002_rls.sql`.
10. **Hardened deployment** — non-root Docker `Dockerfile:7`, healthcheck, webhook secret `services/telegram.py:62`, admin key on golden writes, tight CORS `main.py:81`, rate limits `api/security.py:38`, security headers, `.env.example`.

## Reliability

- **Provider failover:** `Anthropic→Groq→deterministic` with swallowed exceptions `src/ecomm_agent/services/llm.py:318`.
- **Retrieval degraded mode:** When Chroma not indexed, `load_vector_store()` returns `None` `src/ecomm_agent/rag/vectorstore.py:335` and lexical `search_catalog` serves requests.
- **Tracing fail-safe:** `PHOENIX_ENABLED=false` or missing key is no-op `src/ecomm_agent/observability/tracing.py:46`.
- **Supabase fail-safe:** `is_supabase_configured()` `src/ecomm_agent/services/supabase.py:12` → `503` for golden endpoints, `GET /api/catalog` still works.
- **Ephemeral storage:** Render `VECTOR_STORE_PATH=/tmp/data/vectorstore` `render.yaml:33` is rebuildable cache; re-run `uv run ecomm-agent index-rag`.
- **Webhook resilience:** Empty-message guard `api/routes/telegram.py:47`, 20s `httpx` timeout `services/telegram.py:47`, `X-Content-Type-Options: nosniff` etc. `main.py:81`, rate limits per IP `api/security.py:56`.

## Testing

```bash
uv sync --extra dev
uv run pytest
uv run ruff check src tests
```

| Suite | File | Protects |
|-------|------|----------|
| Guardrails | `tests/test_guardrails.py` | prompt injection bypass, out-of-scope drift, false blocking of valid queries |
| Chatbot behavior | `tests/test_chatbot.py` | verified catalog match, honest fallback, injection not leaking, knowledge answering |
| LLM fallback | `tests/test_llm_fallback.py` | provider outage → fallback order, validation fallback |
| Telegram webhook | `tests/test_telegram_webhook.py` | reply delivery, empty message handling, send failure, auth/rate-limit (with env) |
| Catalog API | `tests/test_catalog_api.py` | payload shape, 400/404, 405 on POST, CORS |
| Data & retrieval | `tests/test_catalog.py`, `tests/test_rag_documents.py`, `tests/test_vectorstore_indexing.py` | variant integrity, RAG document shape, Chroma indexing |

**Golden dataset regression:**

```bash
uv run ecomm-agent seed-golden        # idempotent 8 canonical queries
uv run ecomm-agent eval-golden        # 8/8 when RAG/guardrails intact; fails on missing_product / intent_mismatch
curl -X POST http://localhost:8000/api/golden/evaluate -H "Authorization: Bearer $ADMIN_API_KEY" | jq .pass_rate
```

`Supabase public.golden_queries (8 seeds) + evaluation_runs/results + POST /api/golden/evaluate → EvaluationSummary with phoenix_trace_id` `docs/golden-dataset.md`.

## Limitations

- Vector store ephemeral on Render `render.yaml:33` until external DB (Qdrant/pgvector); requires rebuild per deploy.
- No persistent per-thread checkpointing (`graph.py:112` `compile()` without `checkpointer`); conversation memory is per-turn only.
- Intent taxonomy is `product_search | general_question | out_of_domain` (guardrail-forced); `order status` from `AGENTS.md` not implemented — `TBD — requires confirmation` for future.
- Size `OS` (one-size) accessories not filterable via `SIZE_NORMALIZATION` `services/catalog.py:24` (`S/M/L/XL` only).
- Price extraction regex `PRICE_PATTERN` `catalog.py:46` narrow: `under/below/less than/up to $X` or `$X or less/max`; phrases like `cheaper than 500` may be missed.
- Budget bypass now requires an in-domain token `services/guardrails.py:139` — adversarial `crypto under 1500` with a commerce term could still misclassify, `TBD — requires confirmation`.
- `PHOENIX_RECORD_CONTENT=true` exports PII to Phoenix Cloud — default is `false` `core/config.py:136`; enable only for eval sessions.
- `POST /api/golden/evaluate` runs synchronously and can be slow; no queue or background job yet.
- Catalog 30 products, 3 variants each; no pagination beyond `limit`/`offset` on golden endpoints.
- Throughput/cost numbers not measured — `TBD — requires confirmation`.

## Local Setup

### Required environment

See `.env.example` for full list.

```env
TELEGRAM_BOT_TOKEN=...
TELEGRAM_WEBHOOK_PUBLIC_URL=https://your-public-url
TELEGRAM_WEBHOOK_SECRET_TOKEN= # openssl rand -hex 32
FRONTEND_BASE_URL=https://alta-norma-fashion.lovable.app
ADMIN_API_KEY= # openssl rand -hex 32 for golden writes
ANTHROPIC_API_KEY=...
ANTHROPIC_MODEL=claude-sonnet-4-20250514
GROQ_API_KEY=...
GROQ_MODEL=llama-3.3-70b-versatile
OPENAI_API_KEY=...
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
VECTOR_STORE_PATH=./data/vectorstore
KNOWLEDGE_BASE_DIR=./data/knowledge
PHOENIX_ENABLED=false
PHOENIX_API_KEY=ak-...
PHOENIX_COLLECTOR_ENDPOINT=https://app.phoenix.arize.com/v1/traces
PHOENIX_PROJECT_NAME=langgraph-ecom-assistant
PHOENIX_RECORD_CONTENT=false
SUPABASE_URL=https://<ref>.supabase.co
SUPABASE_PROJECT_ID=<ref>
SUPABASE_ANON_KEY=eyJ...
SUPABASE_SERVICE_ROLE_KEY=eyJ...
```

`TELEGRAM_WEBHOOK_PUBLIC_URL` is the base URL, not the full path; `/webhook/telegram` appended. `OPENAI_API_KEY` only for embeddings. `FRONTEND_BASE_URL` yields `https://alta-norma-fashion.lovable.app/products/TSH-001`. `SUPABASE_SERVICE_ROLE_KEY` is server-side only.

### Run locally

```bash
uv sync --extra dev
uv run uvicorn ecomm_agent.main:app --reload
```

### Index the vector store

```bash
uv run ecomm-agent index-rag
```

### Seed and evaluate golden dataset

```bash
uv run ecomm-agent seed-golden
uv run ecomm-agent eval-golden
uv run ecomm-agent eval-golden --limit 2 --json
```

Requires `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY` and tables from `supabase/migrations/20250918_golden_evaluation.sql` + `20250919_002_rls.sql`.

## Render Deployment

See `render.yaml` (`runtime: docker`, `healthCheckPath: /health`). Set `TELEGRAM_WEBHOOK_PUBLIC_URL` to the Render URL, rotate `TELEGRAM_WEBHOOK_SECRET_TOKEN` and `ADMIN_API_KEY` via `sync:false`. Lovable `VITE_API_BASE_URL` points to the same Render URL. `VECTOR_STORE_PATH=/tmp/data/vectorstore` ephemeral, `PHOENIX_RECORD_CONTENT=false` by default.

## Demo Notes

- Webhook: `POST /webhook/telegram` with `X-Telegram-Bot-Api-Secret-Token` when `TELEGRAM_WEBHOOK_SECRET_TOKEN` is set.
- Catalog: `GET /api/catalog`, `GET /api/catalog/{product_id}` (400 on bad id, 404 on missing).
- Golden: `GET /api/golden`, `GET /api/golden/count`, `GET /api/golden/by-slug/{slug}`, `POST /api/golden` (Bearer `ADMIN_API_KEY`), `POST /api/golden/evaluate` (Bearer), `GET /api/golden/evaluation/runs`.

## Catalog API

Same source-of-truth as the agent (`data/catalog/products.json`), read-only `GET`, CORS `allow_origin_regex=https://alta-norma-fashion\.lovable\.app` + `X-Content-Type-Options: nosniff` etc.

## Observability

Phoenix Cloud via OTLP/HTTP with `LangChainInstrumentor` + manual spans `intent_router`, `retrieval`, `guardrails`, `llm.anthropic|groq` including `input.value`/`output.value` only when `PHOENIX_RECORD_CONTENT=true` — see `docs/observability.md`.

## Golden Dataset

Supabase `public.golden_queries` (8 seeds) + `evaluation_runs/results`; see `docs/golden-dataset.md` and `supabase/migrations/20250919_002_rls.sql` for RLS.

## Maintenance

See `MAINTENANCE.md`.
