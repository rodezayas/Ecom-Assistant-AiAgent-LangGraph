# Observability — Arize Phoenix Cloud (OTLP/HTTP)

## 1. Purpose

This document describes the observability layer based on **Arize Phoenix Cloud** via **OpenTelemetry OTLP/HTTP**, with LangGraph auto-instrumentation and manual business spans that optionally include message content.

Principles:
- **LangChainInstrumentor** (`openinference-instrumentation-langchain`) automatically traces `StateGraph.invoke` and each node as `chain` spans. It wraps the graph without replacing it.
- **Manual spans** add business attributes (`intent`, `guardrail`, `retrieval`, `llm`) and `input.value`/`output.value` (messages, prompts and responses).
- **Phoenix Cloud** is the default backend. No local collector or `phoenix` service in `docker-compose` is required. Local and production send directly to `https://app.phoenix.arize.com/v1/traces` via HTTP.
- **Fail-safe**: when Phoenix is disabled or the API key is missing, the app runs without tracing (webhook is not broken).

## 2. Trace Architecture

```
POST /webhook/telegram  (span: webhook.telegram, thread_id, input.value=user_message)
 └─ agent.graph  (span: process_user_message, thread_id)
     ├─ [auto] langgraph StateGraph  (chain)
     │   ├─ intent_router  (manual + auto chain) -> intent
     │   ├─ retrieval  (manual) -> retrieval.products / retrieval.knowledge
     │   │   └─ retrieval.products / retrieval.knowledge  (service spans: source=vector|lexical)
     │   ├─ guardrails  (manual) -> guardrail.blocked/reason
     │   ├─ response_generator | fallback  (manual) -> output.value=response_text
     │   └─ (auto) fallback / response_generator end
     ├─ agent.build_reply
     │   └─ llm.generate
     │       ├─ llm.anthropic  (httpx, input.value=prompt, output.value=text)
     │       └─ llm.groq  (fallback, validated by _validate_llm_output)
     └─ telegram.sendMessage  (manual, telegram.ok)
```

Follows **OpenInference Semantic Conventions** (`input.value`, `output.value`, `llm.model_name`, `llm.token_count.*`, `retrieval.documents.*`).

## 3. Configuration

Variables in `src/ecomm_agent/core/config.py:136` (`Settings`):

| Variable | Default | Description |
|---|---|---|
| `PHOENIX_ENABLED` | `false` | Enable tracing. When `false`, no-op. |
| `PHOENIX_COLLECTOR_ENDPOINT` | `https://app.phoenix.arize.com/v1/traces` | Cloud OTLP/HTTP endpoint |
| `PHOENIX_PROJECT_NAME` | `langgraph-ecom-assistant` | Phoenix project name |
| `PHOENIX_API_KEY` | `None` | Arize Phoenix Cloud API key (header `api_key`) |
| `OTEL_SERVICE_NAME` | `ecomm-agent-api` | OTEL `service.name` |
| `PHOENIX_RECORD_CONTENT` | `false` | When `true`, record `input.value/output.value` with message and prompt content — defaults to false to avoid PII export |

Example `.env` (points to Cloud, no daemon required):

```env
PHOENIX_ENABLED=true
PHOENIX_COLLECTOR_ENDPOINT=https://app.phoenix.arize.com/v1/traces
PHOENIX_PROJECT_NAME=langgraph-ecom-assistant
PHOENIX_API_KEY=sk-phoenix-...
OTEL_SERVICE_NAME=ecomm-agent-api
PHOENIX_RECORD_CONTENT=false
```

Get `PHOENIX_API_KEY`: https://app.phoenix.arize.com -> Settings -> API Keys.

## 4. Setup

### Code

- `src/ecomm_agent/observability/tracing.py`: `setup_tracing()` uses `phoenix.otel.register(project_name, endpoint, headers={"api_key": ...}, batch=True, auto_instrument=True)` + `LangChainInstrumentor().instrument()`. Gated by `PHOENIX_ENABLED` and wrapped in `try/except` to avoid breaking startup.
- `src/ecomm_agent/observability/__init__.py`: exports `setup_tracing`, `get_tracer`, `is_content_recording_enabled`.
- `src/ecomm_agent/main.py:39` (`lifespan`): calls `setup_tracing()` before `set_webhook`.

### Dependencies

`pyproject.toml:7`:

```
arize-phoenix-otel>=0.8.0
opentelemetry-api, opentelemetry-sdk, opentelemetry-exporter-otlp-proto-http
openinference-instrumentation-langchain>=0.1.0
openinference-semantic-conventions>=0.1.0
```

Install: `uv sync`.

## 5. Spans and Attributes

| Span | File | Key attributes |
|---|---|---|
| `webhook.telegram` | `src/ecomm_agent/api/routes/telegram.py:24` | `thread_id`, `http.route`, `intent`, `guardrail.blocked/reason`, `input.value` (when `PHOENIX_RECORD_CONTENT=true`), `output.value`, `response.length`, `telegram.sent/message_id` |
| `agent.graph` | `src/ecomm_agent/services/chatbot.py:18` | `thread_id`, `intent`, `guardrail.blocked`, `retrieval.product/knowledge_count`, `input/output.value` |
| `agent.build_reply` | `src/ecomm_agent/services/chatbot.py:35` | `thread_id`, `intent`, `reply.source=llm|deterministic`, `output.value` |
| `intent_router` | `src/ecomm_agent/agents/nodes/intent_router.py:13` | `thread_id`, `intent`, `token_count`, `input/output.value` |
| `retrieval` | `src/ecomm_agent/agents/nodes/retrieval.py:13` | `thread_id`, `intent`, `retrieval.type/count/reason/source`, `input/output.value` |
| `retrieval.products` | `src/ecomm_agent/services/retrieval.py:63` | `retrieval.source=vector+lexical|vector|lexical`, `retrieval.product_count` |
| `retrieval.knowledge` | `src/ecomm_agent/services/retrieval.py:148` | `retrieval.source`, `retrieval.knowledge_count` |
| `guardrails` | `src/ecomm_agent/agents/nodes/guardrails.py:30` | `thread_id`, `guardrail.blocked/reason/blocked_terms`, `intent`, `input/output.value` |
| `response_generator` | `src/ecomm_agent/agents/nodes/response_generator.py:17` | `thread_id`, `intent`, `response.length`, `input/output.value` |
| `fallback` | `src/ecomm_agent/agents/nodes/fallback.py:12` | `thread_id`, `intent`, `fallback.reason`, `input/output.value` |
| `llm.generate` | `src/ecomm_agent/services/llm.py:299` | `thread_id`, `llm.provider_order`, `llm.chosen_provider`, `llm.validation_failed`, `output.value` |
| `llm.anthropic` | `src/ecomm_agent/services/llm.py:150` | `llm.provider`, `llm.model_name`, `llm.token_count.*`, `llm.response_length`, `input/output.value` |
| `llm.groq` | `src/ecomm_agent/services/llm.py:224` | same as Anthropic |
| `telegram.sendMessage` | `src/ecomm_agent/services/telegram.py:17` | `telegram.chat_id`, `telegram.text_length`, `telegram.ok`, `input.value` |
| `[auto] langgraph` | via `LangChainInstrumentor` | `chain` spans per node (complement manual spans) |

All spans truncate `input/output.value` to `2000/4000` chars.

## 6. Message Content and PII

- When `PHOENIX_RECORD_CONTENT=true`, `input.value` contains `user_message` or the full prompt (`_build_user_prompt` with verified context) and `output.value` contains the LLM or deterministic answer.
- This is opt-in. Default is `false` to avoid exporting PII to Phoenix Cloud.
- Enable explicitly for debugging or evaluation: `PHOENIX_RECORD_CONTENT=true` for eval sessions only. Phoenix Cloud retains this data per its retention policy.

## 7. Local vs Render

- **Local**: `PHOENIX_ENABLED=true` + `PHOENIX_API_KEY` → sends directly to Cloud. No `phoenix` in `docker-compose.yml`.
- **Render**: `render.yaml` defines `PHOENIX_ENABLED`, `PHOENIX_COLLECTOR_ENDPOINT`, `PHOENIX_PROJECT_NAME` fixed and `PHOENIX_API_KEY` as `sync: false` (secret). When the key is not configured, startup logs a warning and the app continues without tracing.

## 8. Verification

### 1. Enable and run

```bash
uv sync
PHOENIX_ENABLED=true PHOENIX_API_KEY=... uv run uvicorn ecomm_agent.main:app --reload
```

### 2. Trigger a test webhook

```bash
curl -X POST http://localhost:8000/webhook/telegram \
  -H 'content-type: application/json' \
  -H 'X-Telegram-Bot-Api-Secret-Token: $TELEGRAM_WEBHOOK_SECRET_TOKEN' \
  -d '{"update_id":1,"message":{"message_id":99,"chat":{"id":12345},"text":"do you have black running shoes under 1500?"}}'
```

### 3. View in Phoenix Cloud

Go to https://app.phoenix.arize.com → project `langgraph-ecom-assistant` → Traces. You should see `webhook.telegram` with children `agent.graph`, `intent_router`, `retrieval`, `guardrails`, `llm.anthropic|groq`, etc., each with `input.value/output.value` when recording is enabled.

### Troubleshooting

- `phoenix tracing disabled` → `PHOENIX_ENABLED=false`.
- `phoenix tracing enabled but PHOENIX_API_KEY is missing` → Cloud rejects unauthenticated traces.
- `phoenix register failed` → check `endpoint` and `api_key`.
- No LangGraph auto-trace → verify `openinference-instrumentation-langchain` installed and `LangChainInstrumentor().instrument()` log `langchain instrumentor enabled`.

## 9. Evaluation and Golden Dataset

Phoenix serves as evaluation backend. With the Supabase golden dataset:
- Dataset in Supabase with `query`, `expected_product_ids`, `expected_intent`, `guardrail_expected`.
- Job runs `process_user_message` offline and exports spans + compares `retrieved_products` vs expected.
- Phoenix Evals: annotations and metrics `guardrail_block_rate`, `retrieval_hit_rate`, `llm_fallback_rate`, `p95 latency per node`.

## 10. References

- Setup: `src/ecomm_agent/observability/tracing.py`, `src/ecomm_agent/main.py:39`
- Config: `src/ecomm_agent/core/config.py:136`
- Instrumentation: `src/ecomm_agent/api/routes/telegram.py:24`, `src/ecomm_agent/services/chatbot.py:18`, `src/ecomm_agent/services/llm.py:150`, `src/ecomm_agent/services/retrieval.py:63`, `src/ecomm_agent/agents/nodes/*`
- Infra: `render.yaml`, `pyproject.toml:7`
