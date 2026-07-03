# Agent Maintenance Guide

## Purpose

This file is the internal maintenance reference for the Alta Norma Fashion Telegram agent.

## AI models in use

- Response generation primary: `Anthropic` via `ANTHROPIC_API_KEY`
- Response generation fallback: `Groq` via `GROQ_API_KEY`
- Embeddings for RAG indexing and retrieval: `OpenAIEmbeddings` via `OPENAI_API_KEY`

## Main runtime paths

- API app: `src/ecomm_agent/main.py`
- Telegram webhook route: `src/ecomm_agent/api/routes/telegram.py`
- LangGraph flow: `src/ecomm_agent/agents/graph.py`
- Guardrails: `src/ecomm_agent/services/guardrails.py`
- Vector store and indexing: `src/ecomm_agent/rag/vectorstore.py`
- Retrieval service: `src/ecomm_agent/services/retrieval.py`

## RAG knowledge sources

- Catalog JSON: `data/catalog/products.json`
- Policies: `data/knowledge/policies.md`
- FAQ: `data/knowledge/faq.md`
- Size guide: `data/knowledge/size_guide.md`

## Current runtime status

- Telegram webhook flow has been validated end to end with a real bot, FastAPI, and `ngrok`.
- The app can still answer product and policy questions without an indexed vector store because retrieval falls back to lexical matching.
- Local Chroma persistence is implemented, but `data/vectorstore` must exist and be populated with `uv run ecomm-agent index-rag` before retrieval is actually backed by embeddings.

## How to reindex RAG documents

Run:

```bash
uv run ecomm-agent index-rag
```

This rebuilds the local Chroma collection in `VECTOR_STORE_PATH`.

Reindex after:

- editing the catalog
- editing policies, FAQ, or size guide
- changing metadata rules or document builders
- changing the embedding model

## Environment variables

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_WEBHOOK_PUBLIC_URL`
- `ANTHROPIC_API_KEY`
- `ANTHROPIC_MODEL`
- `GROQ_API_KEY`
- `GROQ_MODEL`
- `OPENAI_API_KEY`
- `OPENAI_EMBEDDING_MODEL`
- `VECTOR_STORE_PATH`
- `KNOWLEDGE_BASE_DIR`

## Retrieval behavior

- Product queries query Chroma with `source_type=product`.
- General questions query Chroma with `source_type=policy`, `faq`, and `size_guide`.
- Product filtering still applies deterministic checks for category, color, size, and price after vector retrieval.
- If Chroma retrieval is unavailable, product search falls back to lexical catalog search and knowledge retrieval falls back to lexical markdown matching.

## Rules that must not be broken

- Never invent price, stock, color, or size.
- Never invent discounts or shipping promises.
- Keep prompt-injection blocking active.
- Keep out-of-scope blocking active.
- Keep deterministic fallback behavior if Anthropic and Groq both fail.

## Test commands

Lint:

```bash
uv run ruff check src tests
```

Tests:

```bash
uv run pytest
```

## Recommended maintenance workflow

1. Edit source data or agent logic.
2. Reindex with `uv run ecomm-agent index-rag` if RAG sources changed.
3. Run lint.
4. Run tests.
5. Validate one product query and one policy/FAQ query through the webhook.

## Free hosting recommendation

- Best free-first deployment target for this repo: `Railway`, if a trial or hobby credit is available.
- Best fully free always-on path with the least friction: `Render` free web service, understanding that free instances may sleep and cause cold starts.
- Lowest-cost architecture for production-like behavior: host the FastAPI app on a free web service and keep local embedded Chroma only after running `index-rag` during build or release.

For this specific codebase:

1. Deploy the FastAPI container or repo as a web service.
2. Set `TELEGRAM_WEBHOOK_PUBLIC_URL` to the deployed base URL.
3. Keep `VECTOR_STORE_PATH` on the service filesystem only if the platform preserves it across restarts.
4. If the platform filesystem is ephemeral, either re-run `uv run ecomm-agent index-rag` on each deploy or move later to an external vector database.
5. Re-register the Telegram webhook after each hostname change.
