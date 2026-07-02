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
  the store brand name `Nova Style`
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
