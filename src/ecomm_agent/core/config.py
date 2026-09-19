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

    telegram_webhook_secret_token: str | None = Field(default=None)
    """Secret token used to authenticate Telegram webhook calls.

    When set, the app sends it as ``secret_token`` to ``setWebhook`` and
    verifies incoming requests via the ``X-Telegram-Bot-Api-Secret-Token``
    header. Generate with ``openssl rand -hex 32``.
    """

    admin_api_key: str | None = Field(default=None)
    """Admin API key required for golden dataset write/evaluate endpoints.

    When set, callers must send ``Authorization: Bearer <key>``. In
    development the endpoints are more permissive only if this is unset.
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
        ]
    )
    """Explicit origins allowed to call the catalog API from the browser."""

    cors_allowed_origin_regex: str = Field(default=r"https://.*\.lovable\.app")
    """Regex of extra origins allowed by CORS (e.g. Lovable app subdomains)."""

    cors_allow_credentials: bool = Field(default=False)
    """Whether to send credentials (cookies/auth) cross-origin; false for read-only catalog."""

    rate_limit_webhook_per_minute: int = Field(default=60, ge=10, le=600)
    """Rate limit for webhook endpoint (requests per minute per IP)."""

    rate_limit_catalog_per_minute: int = Field(default=100, ge=10, le=1000)
    """Rate limit for catalog endpoints."""

    rate_limit_golden_per_minute: int = Field(default=60, ge=10, le=600)
    """Rate limit for golden read endpoints."""

    max_telegram_text_length: int = Field(default=4000, ge=500, le=10000)
    """Maximum length for Telegram message text; longer messages are truncated/rejected."""

    phoenix_enabled: bool = Field(default=False)
    """Whether Arize Phoenix tracing is enabled."""

    phoenix_collector_endpoint: str = Field(
        default="https://app.phoenix.arize.com/v1/traces"
    )
    """OTLP/HTTP endpoint for Phoenix Cloud traces."""

    phoenix_project_name: str = Field(default="langgraph-ecom-assistant")
    """Phoenix project name where traces are grouped."""

    phoenix_api_key: str | None = Field(default=None)
    """Arize Phoenix Cloud API key (sent as api_key header)."""

    otel_service_name: str = Field(default="ecomm-agent-api")
    """OpenTelemetry service name reported to Phoenix."""

    phoenix_record_content: bool = Field(default=False)
    """Whether to record input.value/output.value (user messages) in traces.

    Defaults to false to avoid exporting PII to Phoenix Cloud. Enable only
    for explicit evaluation or debugging sessions.
    """

    # Supabase — golden dataset source of truth
    supabase_url: str | None = Field(default=None)
    """Supabase project URL (https://<ref>.supabase.co)."""

    supabase_anon_key: str | None = Field(default=None)
    """Supabase anon public key (read-only)."""

    supabase_service_role_key: str | None = Field(default=None)
    """Supabase service_role key (server-side, bypasses RLS). Alias: SUPABASE_SERVICE_ROLE_KEY."""

    supabase_service_role: str | None = Field(default=None)
    """Alias for SUPABASE_SERVICE_ROLE (without _KEY suffix) for .env compat."""

    supabase_project_id: str | None = Field(default=None)
    """Supabase project reference id."""

    phoenix_arize_api_key: str | None = Field(default=None)
    """Alias for PHOENIX_ARIZE_API_KEY (compat with current .env)."""

    @property
    def resolved_supabase_url(self) -> str | None:
        """Resolve Supabase URL from SUPABASE_URL or SUPABASE_PROJECT_ID."""
        if self.supabase_url:
            return self.supabase_url
        if self.supabase_project_id:
            return f"https://{self.supabase_project_id}.supabase.co"
        return None

    @property
    def resolved_supabase_service_key(self) -> str | None:
        """Resolve service_role key from either SUPABASE_SERVICE_ROLE_KEY or SUPABASE_SERVICE_ROLE."""
        return self.supabase_service_role_key or self.supabase_service_role

    @property
    def resolved_phoenix_api_key(self) -> str | None:
        """Resolve Phoenix API key from PHOENIX_API_KEY or PHOENIX_ARIZE_API_KEY."""
        return self.phoenix_api_key or self.phoenix_arize_api_key

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
"""Module-level singleton that all application code reads configuration from."""
