# Project: Intelligent Ecom Agent on Telegram + Web Product Pages (RAG)

## Objective

Build a conversational chatbot inside Telegram that simulates the sales assistant of an online clothing/fashion store. The agent answers questions about products (search, availability, price, variants) using RAG over a real catalog, with guardrails to never hallucinate inventory.

The project now also includes a website layer for product pages. Based on `data/catalog/products.json`, each product should be representable as a public web page so the assistant can send a verified product URL when a user asks about a specific item.

This is a portfolio project to demonstrate senior AI Engineering competence: agentic orchestration, RAG, guardrails, production architecture (Docker, FastAPI, Pydantic, monitoring, evaluation).

## Use Case

A user writes in Telegram, for example: _"do you have running shoes under $1500?"_ or _"is the blue t-shirt in size M in stock?"_. The agent understands intent, searches the vectorized catalog, and responds in natural language with real products — never inventing price, size, or stock.

If the query matches a specific product, the response can also include a verified link to that product's web page, generated from the catalog-backed website layer.

## Trigger

Telegram Bot API via webhook.

```
POST /webhook/telegram
{
  "update_id": ...,
  "message": {
    "chat": {"id": 12345},
    "text": "do you have running shoes under $1500?",
    "from": {...}
  }
}
```

Telegram's `chat.id` acts as the `thread_id` for maintaining conversation memory in LangGraph (per-thread checkpointing).

## Agent Architecture (LangGraph nodes)

1. **Intent router** — classifies the message: product search, order status inquiry, general question, or out-of-domain.
2. **RAG retrieval** — searches the vectorized catalog (name, description, category, tags) for semantically relevant products.
3. **Business guardrails** — never invent price/stock/size outside what the source of truth returns; never promise unauthorized shipping or discounts.
4. **Product URL resolver** — when a product is identified, resolve its verified website URL deterministically from catalog-backed product page data.
5. **Response generator** — builds a conversational reply formatted for Telegram (text, optionally inline buttons and product links).
6. **Fallback/handoff** — if no results are found or a guardrail blocks something, respond honestly instead of hallucinating.

## Key Design Principle

The RAG embedding runs over rich text (`name + description + category + tags`). **Size, color, stock, and product URL never come from the LLM** — they are queried deterministically from the source of truth after RAG identifies the product. This separates "what the model generates" (language) from "what is queried directly from the system" (inventory and product links), preventing availability or URL hallucinations.

## Data Model (Pydantic)

```python
class Variant(BaseModel):
    sku: str
    size: str  # S, M, L, XL
    color: str
    stock: int

class Product(BaseModel):
    id: str
    name: str
    category: str  # t-shirts, pants, jackets, shoes, accessories
    description: str
    price: float
    url: str | None = None
    variants: list[Variant]
    tags: list[str]  # casual, formal, athletic, etc.
```

If the catalog remains the single source of truth, product URLs can be stored directly in the catalog or derived deterministically from a stable slug strategy based on `id` or `name`.

## Technical Stack

- **FastAPI** — receives and processes the Telegram webhook
- **Web frontend or product pages** — exposes public catalog-backed product detail pages
- **LangGraph** — orchestrates agent nodes with persistent state per `chat_id`
- **Pydantic** — validates product schema and the agent's structured outputs
- **Vector store** — Chroma or Qdrant (local) for catalog RAG
- **Docker** — fully containerized stack from the start
- **Monitoring** — per-conversation logging: detected intent, retrieved products, whether a guardrail blocked something
- **Evaluation** — test case dataset to measure regression when prompts/models change (e.g., queries with real vs. nonexistent stock, ambiguous questions, guardrail manipulation attempts)

## Test Catalog

Clothing/fashion store. Simulated catalog of ~40-60 products: t-shirts, pants, jackets, shoes, accessories — with realistic size/color/stock variants, in JSON format for loading into the vector store.

The catalog should also support website-level product identity, so each product can map to a stable product page URL that the agent can safely share.

## Why This Project Matters in Interviews

- **LangGraph** is the most-asked-about framework in senior agentic AI roles right now.
- **RAG + guardrails together** demonstrate understanding of why agents fail in production, not just how they work in a demo.
- **LLM vs. source-of-truth separation** is a direct answer to systems design questions like "how do you prevent the agent from inventing data" or "how do you guarantee consistency across systems."
- **Evaluation** is the component almost no portfolio includes — a clear differentiator against other candidates.

## Next Steps

1. Generate test catalog (JSON, ~40-60 products with variants)
2. Define the full LangGraph skeleton (nodes + transitions + state)
3. Implement FastAPI endpoint + Telegram webhook
4. Build the website product page layer from `data/catalog/products.json`
5. Resolve deterministic product URLs from the catalog or slug rules
6. Load vector store with catalog embeddings
7. Implement output validation guardrails
8. Dockerize
9. Build evaluation dataset and monitoring pipeline
