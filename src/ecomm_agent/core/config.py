"""Application configuration.

Loads runtime settings from environment variables (and an optional ``.env``
file) using ``pydantic-settings``. All secrets and tunables used across the
agent, the Telegram integration, the vector store, and the LLM providers are
declared here so the rest of the codebase reads them from the single
:data:`ecomm_agent.core.config.settings` instance.
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed application configuration backed by environment variables.

    Every attribute maps to an environment variable of the same name (case
    insensitive). For example ``TELEGRAM_BOT_TOKEN`` populates
    :attr:`telegram_bot_token`. Optional API keys default to ``None``; the
    caller decides how to behave when a key is missing.
    """

    app_name: str = "Intelligent Ecom Agent"
    """Human-readable application name used in the FastAPI docs title."""

    app_version: str = "0.1.0"
    """Application version reported by FastAPI."""

    environment: str = Field(default="dev")
    """Runtime environment label (e.g. ``dev`` or ``production``)."""

    openai_api_key: str | None = Field(default=None)
    """OpenAI API key used only for embeddings (never for answer generation)."""

    openai_embedding_model: str = Field(default="text-embedding-3-small")
    """OpenAI embedding model used to vectorize RAG documents."""

    anthropic_api_key: str | None = Field(default=None)
    """Anthropic API key for the primary response generation provider."""

    anthropic_model: str = Field(default="claude-sonnet-4-20250514")
    """Anthropic model identifier used for generated replies."""

    anthropic_api_base_url: str = Field(default="https://api.anthropic.com")
    """Base URL for the Anthropic Messages API (useful for proxies)."""

    anthropic_api_version: str = Field(default="2023-06-01")
    """Anthropic ``anthropic-version`` request header value."""

    anthropic_max_tokens: int = Field(default=350, ge=64, le=4096)
    """Maximum tokens Anthropic may generate per reply."""

    groq_api_key: str | None = Field(default=None)
    """Groq API key for the fallback response generation provider."""

    groq_model: str = Field(default="llama-3.3-70b-versatile")
    """Groq model identifier used when Anthropic is unavailable."""

    groq_api_base_url: str = Field(default="https://api.groq.com/openai/v1")
    """Base URL for the Groq OpenAI-compatible chat completions endpoint."""

    groq_max_completion_tokens: int = Field(default=350, ge=64, le=4096)
    """Maximum completion tokens Groq may generate per reply."""

    telegram_bot_token: str | None = Field(default=None)
    """Telegram Bot API token; required for webhook registration and replies."""

    telegram_api_base_url: str = Field(default="https://api.telegram.org")
    """Base URL for the Telegram Bot API."""

    telegram_webhook_public_url: str | None = Field(default=None)
    """Public base URL where Telegram must deliver webhook updates.

    The full webhook path ``/webhook/telegram`` is appended automatically at
    startup. Must be set (together with :attr:`telegram_bot_token`) for the
    bot to receive messages.
    """

    frontend_base_url: str | None = Field(default=None)
    """Public base URL of the web frontend.

    When set, product URLs shared by the assistant are derived as
    ``{frontend_base_url}/products/{product_id}``.
    """

    vector_store_path: str = Field(default="./data/vectorstore")
    """Local directory where the Chroma collection is persisted."""

    catalog_path: str = Field(default="./data/catalog/products.json")
    """Filesystem path to the source-of-truth product catalog (JSON)."""

    knowledge_base_dir: str = Field(default="./data/knowledge")
    """Directory containing the Markdown knowledge base (policies/FAQ/sizes)."""

    cors_allowed_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:3000",
            "http://localhost:5173",
            "https://lovable.dev",
        ]
    )
    """Explicit origins allowed to call the catalog API from the browser."""

    cors_allowed_origin_regex: str = Field(default=r"https://.*\.lovable\.app")
    """Regex of extra origins allowed by CORS (e.g. Lovable app subdomains)."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
"""Module-level singleton that all application code reads configuration from."""
