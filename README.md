# Intelligent Ecom Agent

Phase 1 scaffold for a Telegram-based fashion e-commerce assistant built with FastAPI, LangGraph, and RAG.

## Current scope

- FastAPI application scaffold
- LangGraph package structure and node placeholders
- Pydantic schemas for catalog and Telegram webhook payloads
- Local project layout for catalog data, tests, and Docker
- Dependency management with `uv`

## Run locally

```bash
uv sync --extra dev
uv run uvicorn ecomm_agent.main:app --reload
```
