# Observability — Arize Phoenix Cloud (OTLP/HTTP)

## 1. Propósito

Este documento describe la capa de observabilidad del asistente basada en **Arize Phoenix Cloud** vía **OpenTelemetry OTLP/HTTP**, con auto-instrumentación de LangGraph y spans manuales de negocio que incluyen contenido de mensajes.

Principios:
- **LangChainInstrumentor** (`openinference-instrumentation-langchain`) traza automáticamente `StateGraph.invoke` y cada nodo como `chain` spans. No se reemplaza el grafo, lo envuelve.
- **Spans manuales** añaden atributos de negocio (`intent`, `guardrail`, `retrieval`, `llm`) y `input.value`/`output.value` (mensajes, prompts y respuestas).
- **Phoenix Cloud** es el único backend por defecto. No se requiere collector local ni servicio `phoenix` en `docker-compose`. Local y producción envían directo a `https://app.phoenix.arize.com/v1/traces` vía HTTP.
- **Fail-safe**: si Phoenix está deshabilitado o la API key falta, la app funciona sin tracing (no rompe el webhook).

## 2. Arquitectura de Trazas

```
POST /webhook/telegram  (span: webhook.telegram, thread_id, input.value=user_message)
 └─ agent.graph  (span: process_user_message, thread_id)
     ├─ [auto] langgraph StateGraph  (chain)
     │   ├─ intent_router  (span manual + auto chain) -> intent
     │   ├─ retrieval  (span manual) -> retrieval.products / retrieval.knowledge
     │   │   └─ retrieval.products / retrieval.knowledge  (service layer spans: source=vector|lexical)
     │   ├─ guardrails  (span manual) -> guardrail.blocked/reason
     │   ├─ response_generator | fallback  (span manual) -> output.value=response_text
     │   └─ (auto) fallback / response_generator end
     ├─ agent.build_reply
     │   └─ llm.generate
     │       ├─ llm.anthropic  (httpx, input.value=prompt, output.value=text)
     │       └─ llm.groq  (fallback)
     └─ telegram.sendMessage  (span manual, telegram.ok)
```

Convenciones: se siguen **OpenInference Semantic Conventions** (`input.value`, `output.value`, `llm.model_name`, `llm.token_count.*`, `retrieval.documents.*`).

## 3. Configuración

Variables en `src/ecomm_agent/core/config.py:14` (`Settings`):

| Variable | Default | Descripción |
|---|---|---|
| `PHOENIX_ENABLED` | `false` | Activa tracing. Si `false`, no-op. |
| `PHOENIX_COLLECTOR_ENDPOINT` | `https://app.phoenix.arize.com/v1/traces` | Endpoint OTLP/HTTP Cloud |
| `PHOENIX_PROJECT_NAME` | `langgraph-ecom-assistant` | Proyecto Phoenix donde se agrupan trazas |
| `PHOENIX_API_KEY` | `None` | API key de Arize Phoenix Cloud (header `api_key`) |
| `OTEL_SERVICE_NAME` | `ecomm-agent-api` | `service.name` OTEL |
| `PHOENIX_RECORD_CONTENT` | `true` | Si `true`, graba `input.value/output.value` con contenido de mensajes y prompts |

Ejemplo `.env` local (apunta a Cloud, no requiere daemon):

```env
PHOENIX_ENABLED=true
PHOENIX_COLLECTOR_ENDPOINT=https://app.phoenix.arize.com/v1/traces
PHOENIX_PROJECT_NAME=langgraph-ecom-assistant
PHOENIX_API_KEY=sk-phoenix-...
OTEL_SERVICE_NAME=ecomm-agent-api
PHOENIX_RECORD_CONTENT=true
```

Obtener `PHOENIX_API_KEY`: https://app.phoenix.arize.com -> Settings -> API Keys.

## 4. Setup

### Código

- `src/ecomm_agent/observability/tracing.py`: `setup_tracing()` usa `phoenix.otel.register(project_name, endpoint, headers={"api_key": ...}, batch=True, auto_instrument=True)` + `LangChainInstrumentor().instrument()`. Gated por `PHOENIX_ENABLED` y con `try/except` para no romper arranque.
- `src/ecomm_agent/observability/__init__.py`: exporta `setup_tracing`, `get_tracer`, `is_content_recording_enabled`.
- `src/ecomm_agent/main.py:26` (`lifespan`): llama `setup_tracing()` antes de `set_webhook`. Loguea `phoenix tracing registered` o `warning` si falla.

### Dependencias

`pyproject.toml:7`:

```
arize-phoenix-otel>=0.8.0
opentelemetry-api, opentelemetry-sdk, opentelemetry-exporter-otlp-proto-http
openinference-instrumentation-langchain>=0.1.0
openinference-semantic-conventions>=0.1.0
```

Instalar: `uv sync`.

## 5. Spans y Atributos

| Span | Archivo | Atributos clave |
|---|---|---|
| `webhook.telegram` | `src/ecomm_agent/api/routes/telegram.py:22` | `thread_id`, `http.route`, `intent`, `guardrail.blocked/reason`, `input.value`, `output.value`, `response.length`, `telegram.sent/message_id` |
| `agent.graph` | `src/ecomm_agent/services/chatbot.py:18` | `thread_id`, `intent`, `guardrail.blocked`, `retrieval.product/knowledge_count`, `input/output.value` |
| `agent.build_reply` | `src/ecomm_agent/services/chatbot.py:35` | `thread_id`, `intent`, `reply.source=llm|deterministic`, `output.value` |
| `intent_router` | `src/ecomm_agent/agents/nodes/intent_router.py:13` | `thread_id`, `intent`, `token_count`, `input/output.value` |
| `retrieval` | `src/ecomm_agent/agents/nodes/retrieval.py:13` | `thread_id`, `intent`, `retrieval.type/count/reason/source`, `input/output.value` |
| `retrieval.products` | `src/ecomm_agent/services/retrieval.py:63` | `retrieval.source=vector+lexical|vector|lexical`, `retrieval.product_count` |
| `retrieval.knowledge` | `src/ecomm_agent/services/retrieval.py:148` | `retrieval.source`, `retrieval.knowledge_count` |
| `guardrails` | `src/ecomm_agent/agents/nodes/guardrails.py:30` | `thread_id`, `guardrail.blocked/reason/blocked_terms`, `intent`, `input/output.value` |
| `response_generator` | `src/ecomm_agent/agents/nodes/response_generator.py:17` | `thread_id`, `intent`, `response.length`, `input/output.value` |
| `fallback` | `src/ecomm_agent/agents/nodes/fallback.py:12` | `thread_id`, `intent`, `fallback.reason`, `input/output.value` |
| `llm.generate` | `src/ecomm_agent/services/llm.py:253` | `thread_id`, `llm.provider_order`, `llm.chosen_provider`, `output.value` |
| `llm.anthropic` | `src/ecomm_agent/services/llm.py:147` | `llm.provider`, `llm.model_name`, `llm.max_tokens`, `llm.token_count.*`, `llm.response_length`, `input/output.value` |
| `llm.groq` | `src/ecomm_agent/services/llm.py:199` | idem Groq |
| `telegram.sendMessage` | `src/ecomm_agent/services/telegram.py:14` | `telegram.chat_id`, `telegram.text_length`, `telegram.ok`, `input.value` |
| `[auto] langgraph` | via `LangChainInstrumentor` | `chain` spans por nodo (complementan los manuales) |

Todos los spans truncan `input/output.value` a `2000/4000` caracteres para limitar cardinalidad.

## 6. Contenido de Mensajes y PII

- Cuando `PHOENIX_RECORD_CONTENT=true` (default), `input.value` contiene `user_message` o prompt completo (`_build_user_prompt` con contexto verificado) y `output.value` contiene respuesta LLM o determinística.
- Esto es **intencional** por requerimiento (debug y golden dataset futuro en Supabase). Phoenix Cloud retiene estos datos.
- Para desactivar en producción sin perder tracing, setear `PHOENIX_RECORD_CONTENT=false` (mantiene métricas/latencias sin contenido).

## 7. Local vs Render

- **Local**: `PHOENIX_ENABLED=true` + `PHOENIX_API_KEY` -> envía directo a Cloud. No se levanta `phoenix` en `docker-compose.yml`.
- **Render**: `render.yaml` define `PHOENIX_ENABLED`, `PHOENIX_COLLECTOR_ENDPOINT`, `PHOENIX_PROJECT_NAME` fijos y `PHOENIX_API_KEY` como `sync: false` (secreto). Si no se configura la key, el log muestra `warning` y la app sigue sin tracing.
- No se usa `/tmp/data/vectorstore` para Phoenix; vector store sigue efímero como está documentado en `README`.

## 8. Verificación

### 1. Habilitar y correr

```bash
uv sync
PHOENIX_ENABLED=true PHOENIX_API_KEY=... uv run uvicorn ecomm_agent.main:app --reload
```

### 2. Disparar webhook de prueba

```bash
curl -X POST http://localhost:8000/webhook/telegram \
  -H 'content-type: application/json' \
  -d '{"update_id":1,"message":{"message_id":99,"chat":{"id":12345},"text":"do you have black running shoes under 1500?"}}'
```

### 3. Ver en Phoenix Cloud

Ir a https://app.phoenix.arize.com -> proyecto `langgraph-ecom-assistant` -> Traces. Debe aparecer `webhook.telegram` con hijos `agent.graph`, `intent_router`, `retrieval`, `guardrails`, `llm.anthropic|groq`, etc., cada uno con `input.value/output.value`.

### Troubleshooting

- `phoenix tracing disabled` -> `PHOENIX_ENABLED=false`.
- `phoenix tracing enabled but PHOENIX_API_KEY is missing` -> trazas no autenticadas, Cloud las rechaza.
- `phoenix register failed` -> ver `endpoint` y `api_key` (formato, región).
- No aparece auto-traza LangGraph -> verificar `openinference-instrumentation-langchain` instalado y `LangChainInstrumentor().instrument()` log `langchain instrumentor enabled`.

## 9. Evaluación y Golden Dataset (Futuro)

Phoenix servirá como backend de evaluación. Próxima fase (Supabase golden dataset):
- Dataset en Supabase con `query`, `expected_product_ids`, `expected_intent`, `guardrail_expected`.
- Job que corre `process_user_message` offline y exporta spans + compara `retrieved_products` vs expected (hallucination check).
- Phoenix Evals: anotaciones y métricas `guardrail_block_rate`, `retrieval_hit_rate`, `llm_fallback_rate`, `p95 latency por nodo`.

## 10. Referencias

- Setup: `src/ecomm_agent/observability/tracing.py`, `src/ecomm_agent/main.py:26`
- Config: `src/ecomm_agent/core/config.py:14`
- Instrumentación: `src/ecomm_agent/api/routes/telegram.py:22`, `src/ecomm_agent/services/chatbot.py:18`, `src/ecomm_agent/services/llm.py:147`, `src/ecomm_agent/services/retrieval.py:63`, `src/ecomm_agent/agents/nodes/*`
- Infra: `render.yaml`, `pyproject.toml:7`
