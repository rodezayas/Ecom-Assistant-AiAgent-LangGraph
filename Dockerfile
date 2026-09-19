FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

WORKDIR /app

# Create non-root user
RUN groupadd -r app && useradd -r -g app -m app

COPY pyproject.toml uv.lock README.md ./
COPY src ./src
COPY data ./data

RUN pip install --no-cache-dir "uv==0.7.13" && uv sync --frozen --no-dev && chown -R app:app /app

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=3).read()" || exit 1

CMD ["uv", "run", "uvicorn", "ecomm_agent.main:app", "--host", "0.0.0.0", "--port", "8000"]
