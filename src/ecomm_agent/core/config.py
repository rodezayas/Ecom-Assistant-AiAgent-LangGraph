from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Intelligent Ecom Agent"
    app_version: str = "0.1.0"
    environment: str = Field(default="dev")
    openai_api_key: str | None = Field(default=None)
    openai_embedding_model: str = Field(default="text-embedding-3-small")
    anthropic_api_key: str | None = Field(default=None)
    anthropic_model: str = Field(default="claude-sonnet-4-20250514")
    anthropic_api_base_url: str = Field(default="https://api.anthropic.com")
    anthropic_api_version: str = Field(default="2023-06-01")
    anthropic_max_tokens: int = Field(default=350, ge=64, le=4096)
    groq_api_key: str | None = Field(default=None)
    groq_model: str = Field(default="llama-3.3-70b-versatile")
    groq_api_base_url: str = Field(default="https://api.groq.com/openai/v1")
    groq_max_completion_tokens: int = Field(default=350, ge=64, le=4096)
    telegram_bot_token: str | None = Field(default=None)
    telegram_api_base_url: str = Field(default="https://api.telegram.org")
    telegram_webhook_public_url: str | None = Field(default=None)
    frontend_base_url: str | None = Field(default=None)
    vector_store_path: str = Field(default="./data/vectorstore")
    catalog_path: str = Field(default="./data/catalog/products.json")
    knowledge_base_dir: str = Field(default="./data/knowledge")
    cors_allowed_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:3000",
            "http://localhost:5173",
            "https://lovable.dev",
        ]
    )
    cors_allowed_origin_regex: str = Field(default=r"https://.*\.lovable\.app")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
