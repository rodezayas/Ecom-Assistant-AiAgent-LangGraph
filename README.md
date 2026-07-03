# Intelligent Ecom Agent

Telegram demo for a fashion e-commerce assistant built with FastAPI, LangGraph, deterministic inventory validation, optional local Chroma-backed RAG, and LLM response generation with `Anthropic -> Groq` fallback.

## Current demo scope

- Telegram webhook receiver
- Real reply delivery with `sendMessage`
- Retrieval pipeline ready for local Chroma persistence plus lexical fallback
- Deterministic filtering for price, category, color, size, and stock after retrieval
- LangGraph orchestration for intent, retrieval, guardrails, response, and fallback
- Anthropic primary generation with Groq fallback
- Knowledge-base files for policies, FAQ, and size guide
- Docker and local `uv` workflow

## Current status

- Real Telegram webhook flow has been tested successfully through `ngrok`.
- The app is currently functional even without `data/vectorstore`, because product and knowledge retrieval fall back to lexical matching.
- Full embedding-backed retrieval remains pending until `uv run ecomm-agent index-rag` is executed.

## Project qualities

- Good documentation: this README explains setup, runtime flow, and demo scope.
- Technical decisions with rationale: see [ADR.md](/home/rodezayas/Langraph-Ecomm/ADR.md).
- Agent rules: the agent is constrained to verified Nova Style catalog and knowledge-base data, prompt-injection blocking, and out-of-scope rejection through the graph and guardrail services.
- Tests that protect business rules: the suite covers catalog integrity, guardrails, chatbot behavior, fallback behavior, webhook behavior, app startup, RAG documents, and vector-store indexing.

## Agent rules

- The agent only answers with verified Nova Style data.
- Price, size, color, and stock come from deterministic catalog data, not from the LLM.
- Shipping, returns, payment, and size guidance come from verified knowledge-base documents, not from the LLM.
- Prompt injection attempts are blocked.
- Out-of-domain requests are rejected honestly.
- If Anthropic fails, Groq is used as fallback.
- If both model providers fail, the app returns a deterministic safe response.

## Business rule tests

- [tests/test_guardrails.py](/home/rodezayas/Langraph-Ecomm/tests/test_guardrails.py): prompt injection and out-of-scope blocking.
- [tests/test_chatbot.py](/home/rodezayas/Langraph-Ecomm/tests/test_chatbot.py): verified product matching and honest fallback behavior.
- [tests/test_llm_fallback.py](/home/rodezayas/Langraph-Ecomm/tests/test_llm_fallback.py): provider fallback order `Anthropic -> Groq -> deterministic`.
- [tests/test_telegram_webhook.py](/home/rodezayas/Langraph-Ecomm/tests/test_telegram_webhook.py): webhook reply flow and empty message handling.
- [tests/test_catalog.py](/home/rodezayas/Langraph-Ecomm/tests/test_catalog.py): catalog minimum size and variants presence.
- [tests/test_rag_documents.py](/home/rodezayas/Langraph-Ecomm/tests/test_rag_documents.py): metadata and section chunking for RAG sources.
- [tests/test_vectorstore_indexing.py](/home/rodezayas/Langraph-Ecomm/tests/test_vectorstore_indexing.py): Chroma indexing and similarity search over the combined corpus.

## Required environment

```env
TELEGRAM_BOT_TOKEN=...
TELEGRAM_WEBHOOK_PUBLIC_URL=https://your-public-url
ANTHROPIC_API_KEY=...
ANTHROPIC_MODEL=claude-sonnet-4-20250514
GROQ_API_KEY=...
GROQ_MODEL=llama-3.3-70b-versatile
OPENAI_API_KEY=...
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
VECTOR_STORE_PATH=./data/vectorstore
KNOWLEDGE_BASE_DIR=./data/knowledge
```

`TELEGRAM_WEBHOOK_PUBLIC_URL` should be the public base URL of your app, not the full webhook path. The app registers `https://.../webhook/telegram` automatically on startup when both `TELEGRAM_BOT_TOKEN` and `TELEGRAM_WEBHOOK_PUBLIC_URL` are set.

## Run locally

```bash
uv sync --extra dev
uv run uvicorn ecomm_agent.main:app --reload
```

If you want Chroma-backed retrieval instead of lexical fallback, run:

```bash
uv run ecomm-agent index-rag
```

## Build the vector store

```bash
uv run ecomm-agent index-rag
```

This indexes the catalog plus the markdown knowledge-base files into the local Chroma persist directory configured by `VECTOR_STORE_PATH`. It uses `OPENAI_API_KEY` and `OPENAI_EMBEDDING_MODEL` for embeddings.

## Retrieval model

- Product questions retrieve from Chroma with `source_type=product`.
- Policy, FAQ, and size questions retrieve from Chroma with `source_type=policy`, `faq`, and `size_guide`.
- Product availability is still validated deterministically from the catalog after retrieval.
- If vector retrieval is unavailable, product search falls back to lexical catalog search and knowledge retrieval falls back to lexical markdown matching.

## Run with Docker

```bash
docker compose up --build
```

## Demo flow

1. Expose the API publicly with a tunnel or deployed URL.
2. Set `TELEGRAM_WEBHOOK_PUBLIC_URL` to that public base URL.
3. Optionally run `uv run ecomm-agent index-rag` if you want embedding-backed retrieval.
4. Start the app.
5. Send a message to your bot in Telegram.
6. Telegram posts to `/webhook/telegram`, the app runs the agent, retrieves verified context from Chroma when available or lexical fallback when not, generates text with Anthropic or Groq, and sends the reply back to the same chat.

## Free hosting options

The simplest free path for this repo is:

1. `Render` free web service for FastAPI
2. Telegram webhook pointed at the Render HTTPS URL
3. Chroma kept local only if you are comfortable rebuilding the vector store on each deploy

Tradeoffs:

- `Render` free is the easiest always-public HTTPS option, but free instances can sleep and cause webhook cold starts.
- `Railway` is often smoother operationally, but its free offering changes over time and may rely on credits instead of a permanent free tier.
- `Fly.io` can work, but it is more operationally involved for a portfolio demo than Render.

If you want a zero-cost demo right now, use `Render` for the app and keep lexical fallback enabled until you are ready to externalize the vector store.

## Internal maintenance

See [MAINTENANCE.md](/home/rodezayas/Langraph-Ecomm/MAINTENANCE.md) for internal operating notes, model inventory, and reindexing guidance.
