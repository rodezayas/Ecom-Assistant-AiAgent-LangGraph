FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
COPY src ./src
COPY data ./data

RUN pip install --no-cache-dir uv && uv sync --frozen

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "ecomm_agent.main:app", "--host", "0.0.0.0", "--port", "8000"]
