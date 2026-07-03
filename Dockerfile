FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
COPY src ./src
COPY data ./data

RUN pip install --no-cache-dir uv && uv sync --frozen --no-dev

EXPOSE 8000

CMD ["sh", "-c", "uv run uvicorn ecomm_agent.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
