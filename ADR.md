# Architecture Decision Record

## ADR-001: Phase 1 project structure

- Decision: Create a `src/ecomm_agent` package with separated modules for `api`, `agents`, `schemas`, `services`, `rag`, `observability`, `tests`, `data`, and Docker assets.
- Why: The project objective explicitly targets FastAPI, LangGraph, RAG, guardrails, monitoring, evaluation, and Docker. A modular structure avoids collapsing transport, agent logic, schemas, and retrieval into one file.
- Source: User instruction.
  The initial request was to read `AGENTS.md`, generate the project structure, and install dependencies as phase 1.

## ADR-002: Use `uv` as the dependency and environment workflow

- Decision: Keep dependency management in `pyproject.toml` and install with `uv sync --extra dev`.
- Why: The repository already contained `pyproject.toml` and `uv.lock`, so extending the existing workflow was lower risk than introducing Poetry or plain `pip`.
- Source: Assistant assumption based on repository state.
  The user asked for dependencies to be installed, but did not prescribe the package manager. The repo already used `uv`, so I continued with that.

## ADR-003: Seed the project with a deterministic local catalog

- Decision: Add `data/catalog/products.json` with 30 clothing, shoes, jacket, pants, and accessories products, each including variants and stock.
- Why: The project requirements call for a real catalog-backed assistant and explicitly state that price, size, color, and stock must come from source-of-truth data instead of the LLM. A local JSON catalog is the simplest deterministic source for early phases.
- Source: User instruction.
  The project brief in `AGENTS.md` requires a simulated catalog with realistic variants, and the latest user message asked to build the catalog next.

## ADR-004: Implement deterministic pre-retrieval guardrails

- Decision: Add a lexical guardrail layer in `src/ecomm_agent/services/guardrails.py` that blocks two cases before retrieval:
  `prompt_injection`
  `out_of_scope`
- Why: The user explicitly asked for the chatbot to detect words that are not product-related or are not relevant to the brand context, and to create guardrails against prompt injection. Deterministic checks are appropriate here because they run before any model call and are easier to test.
- Source: User instruction.
  The user requested detection of non-product / non-brand-context words and prompt injection guardrails.

## ADR-005: Define brand context as a bounded vocabulary

- Decision: Model brand context as the union of:
  catalog-derived words from product names, categories, descriptions, tags, colors, and sizes
  fixed commerce terms
  the store brand name `Alta Norma Fashion`
- Why: This keeps scope detection tied to the actual store inventory and avoids relying on a model to decide whether a message belongs to the catalog domain.
- Source: Assistant assumption constrained by user instruction.
  The user required context filtering around the brand, but did not define a method. I chose catalog-derived vocabulary because it aligns with the source-of-truth design in `AGENTS.md`.

## ADR-006: Use English as the agent language

- Decision: Normalize chatbot responses, guardrail trigger phrases, and allowed context words to English.
- Why: The user explicitly clarified that the agent context is English and requested all strings and words in English.
- Source: User instruction.
  The user explicitly requested that the agent context, strings, and vocabulary be fully in English.

## ADR-007: Keep webhook behavior transparent during early phases

- Decision: Return guardrail evaluation details from the Telegram webhook handler:
  `guardrail_blocked`
  `guardrail_reason`
  `blocked_terms`
  `response_text`
- Why: The project goals include monitoring and guardrail visibility. Exposing these fields in the early scaffold makes debugging and evaluation easier before the real Telegram send-response flow is added.
- Source: Assistant assumption.
  The user did not ask for this exact response contract, but it supports the stated monitoring and evaluation goals in `AGENTS.md`.

## ADR-008: Use local embedded Chroma persistence instead of a standalone Chroma service

- Decision: Keep vector retrieval implemented with `langchain-chroma` using a local persist directory at `VECTOR_STORE_PATH`, instead of running Chroma as a separate container or hosted service in the current phase.
- Why: This keeps the demo operational with fewer moving parts, fits the local `uv` and Docker workflow already present in the repo, and lets the agent fall back to deterministic lexical retrieval when the persisted vector store has not been indexed yet.
- Source: Assistant implementation based on repository code.
  The current code in `src/ecomm_agent/rag/vectorstore.py` creates and loads a local persisted Chroma collection, and `docker-compose.yml` only defines the API service.

## ADR-009: Validate Telegram webhook delivery first with `ngrok` before choosing long-term hosting

- Decision: Use `ngrok` as the first public ingress path to validate the real Telegram webhook flow before committing to a deployment platform.
- Why: Telegram webhook validation is the highest-signal integration checkpoint for this portfolio project. `ngrok` gives a fast path to confirm FastAPI routing, Telegram delivery, and reply latency before spending time on infrastructure decisions.
- Source: User instruction and implementation outcome.
  The user confirmed `ngrok` was installed and asked to test the real flow. The webhook was successfully registered and Telegram message delivery was validated through the public `ngrok` URL.

## ADR-010: Expose a read-only catalog API for the website layer

- Decision: Add public read-only FastAPI endpoints for catalog access:
  `GET /api/catalog`
  `GET /api/catalog/{product_id}`
- Why: the project now includes a website layer that must render product pages from the same source of truth used by the agent. Reusing the existing catalog service and `Product` schema avoids data duplication and keeps Telegram, the agent, and the website aligned.
- Source: User instruction.
  The user requested a website flow where the assistant can share product URLs and asked for a read-only endpoint that a Lovable page can consume.

## ADR-011: Keep the website integration constrained to catalog data only

- Decision: expose only catalog read endpoints to the web frontend and do not expose guardrails, LangGraph internals, or RAG internals.
- Why: the website needs product data, not agent internals. Limiting the public API surface reduces accidental coupling, lowers security risk, and keeps the architecture clean.
- Source: User instruction.
  The user explicitly asked not to expose guardrails, RAG internals, or any agent-related internal endpoints.

## ADR-012: Enable CORS specifically for Lovable-origin frontend access

- Decision: configure FastAPI CORS to allow Lovable origins for read-only catalog fetches.
- Why: browser-based frontend requests require CORS even when the endpoint itself is correct. This keeps the backend usable from the Lovable-hosted website without widening the API surface beyond the web use case.
- Source: User instruction.
  The user explicitly requested that the Lovable domain be added to CORS so the website can call the catalog API from the browser.

## ADR-013: Use Render as the first production deployment target

- Decision: prepare the project for deployment on `Render` using a repo-level `render.yaml` and Docker runtime.
- Why: Render provides stable public HTTPS for the Telegram webhook, works well with GitHub-based deploys, and removes the operational fragility of depending on a local machine plus `ngrok`.
- Source: User instruction.
  The user stated they were already in Render and wanted the project prepared for production deployment from GitHub.

## ADR-014: Respect platform-assigned ports and production-only dependencies in Docker

- Decision: update the Docker runtime to bind Uvicorn to `${PORT}` and install only production dependencies with `uv sync --frozen --no-dev`.
- Why: platforms like Render inject the runtime port dynamically, and production images should avoid carrying development-only dependencies when they are not required to serve the app.
- Source: Assistant implementation for production readiness.
  The existing Dockerfile bound the app to a fixed port and installed the full dependency set; those defaults are fine locally but weaker for hosted deployment.

## ADR-015: Treat local vector persistence as ephemeral in Render

- Decision: configure `VECTOR_STORE_PATH` for Render under `/tmp/data/vectorstore` and document that local vector persistence is ephemeral in this hosting model.
- Why: Render web services do not provide durable local filesystem guarantees in the same way a managed vector database does. Until the project moves to external vector storage, lexical fallback and optional rebuilds remain the safest production behavior.
- Source: Assistant implementation constrained by current architecture.
  The project still uses local embedded Chroma and has not yet been migrated to durable external vector storage.

## ADR-016: Use Arize Phoenix Cloud for observability via OTLP/HTTP

- Decision: export traces to Arize Phoenix Cloud via OTLP/HTTP using `arize-phoenix-otel` (`phoenix.otel.register` with `project_name`, `endpoint=https://app.phoenix.arize.com/v1/traces`, `headers={api_key}`, `batch=True`) and auto-instrument LangGraph with `openinference-instrumentation-langchain` (`LangChainInstrumentor`). Add manual business spans (`webhook.telegram`, `agent.graph`, `intent_router`, `retrieval`, `guardrails`, `response_generator`, `fallback`, `llm.anthropic`, `llm.groq`) with OpenInference conventions (`input.value`/`output.value` truncated to 2k/4k, `llm.model_name`, `retrieval.source`). Gate everything behind `PHOENIX_ENABLED` with fail-safe no-op when disabled or key missing.
- Why: Phoenix is OTLP-native and Cloud-hosted (no local collector needed for dev or Render), renders LangGraph traces as `chain` spans out of the box, and supports `input.value` retention required for golden dataset debugging; LangSmith is vendor-locked and heavier for this portfolio. The `PHOENIX_RECORD_CONTENT` flag allows PII to be disabled without losing latency metrics.
- Source: User instruction — "Arize Phoenix Cloud, http, en local necesitaría estar escuchando eventos siempre. Añade dependencias y que incluya contenido de mensajes en traces" — plus `LangChainInstrumentor` retention and Spanish headline in `README.md:5`.
- Consequence: new dependencies in `pyproject.toml:7`, new settings in `src/ecomm_agent/core/config.py:107`, new module `src/ecomm_agent/observability/tracing.py`, lifespan hook in `src/ecomm_agent/main.py:34`, `render.yaml` vars `PHOENIX_ENABLED/COLLECTOR_ENDPOINT/PROJECT_NAME/API_KEY`, docs in `docs/observability.md`.

## ADR-017: Use Supabase as source of truth for the golden dataset

- Decision: store the golden dataset in Supabase `public.golden_queries` (MVP, single table, denormalized `text[]` for `expected_product_ids`/`tags`, `slug` unique, `GIN` indexes on `tags`/`expected_product_ids`, `is_active`/`difficulty` enums). Resolve `SUPABASE_URL` from `SUPABASE_URL` or `SUPABASE_PROJECT_ID` and service key from `SUPABASE_SERVICE_ROLE_KEY` or `SUPABASE_SERVICE_ROLE` for `.env` compat. Expose via `supabase>=2.15.0` with `src/ecomm_agent/services/supabase.py` singleton and `src/ecomm_agent/services/golden_dataset.py` CRUD.
- Why: Supabase gives RLS, SQL Editor familiarity, and a REST API without a new service; a local file would not provide history or concurrent evaluation writes. The denormalized `text[]` keeps the MVP simple (`supabase-js`/`postgrest` friendly) and can migrate to a junction table when queries exceed ~100.
- Source: User instruction — "Posterior a esto agregaremos source of truth - golden dataset con supabase" and MVP SQL prompt executed in Supabase SQL Editor.
- Consequence: `supabase`/`postgrest` in `pyproject.toml:7`, 4 vars in `render.yaml:34` (`SUPABASE_URL/ANON_KEY/SERVICE_ROLE_KEY/PROJECT_ID` as `sync:false`), idempotent seed `src/ecomm_agent/scripts/seed_golden.py` (8 rows), docs in `docs/golden-dataset.md`.

## ADR-018: Link evaluation runs to Phoenix traces

- Decision: implement `run_golden_evaluation(limit/intent/dataset_version)` in `src/ecomm_agent/services/evaluation.py:124` that iterates `list_golden_queries`, runs `process_user_message(thread_id=eval-<slug>)` inside `evaluation.query:<slug>` spans, compares via `_check_golden` (`intent`, `guardrail_blocked/reason`, `expected_product_ids ⊆ actual`, `response_contains`), measures `latency_ms`, extracts `phoenix_trace_id` from `opentelemetry.trace.get_current_span().get_span_context().trace_id`, and persists to `public.evaluation_runs`/`public.evaluation_results` (migration `supabase/migrations/20250918_golden_evaluation.sql`) with `phoenix_trace_url=https://app.phoenix.arize.com/projects/<project>/traces/<id>`. Expose via `POST /api/golden/evaluate` and CLI `uv run ecomm-agent eval-golden`.
- Why: separates "what should happen" (Supabase) from "what happened" (trace); every evaluation is replayable and linkable to its Phoenix waterfall. The `8/8` pass rate today proves no regression after guardrail and retrieval changes.
- Source: User instruction — "Ok hagamoslo" and seed fixes (`TSH-002→TSH-005`, `prompt-injection` `out_of_domain→general_question`, `size-guide-jeans` `general_question→product_search+PNT-006`).
- Consequence: `src/ecomm_agent/schemas/golden.py:60` `EvaluationRun/Result/Summary`, `src/ecomm_agent/api/routes/golden.py:75` evaluation endpoints, `uv run ecomm-agent eval-golden` 8/8, docs updated in `README.md:411`.
