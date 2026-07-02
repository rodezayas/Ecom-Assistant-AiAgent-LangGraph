from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Intelligent Ecom Agent"
    app_version: str = "0.1.0"
    environment: str = Field(default="dev")
    openai_api_key: str | None = Field(default=None)
    telegram_bot_token: str | None = Field(default=None)
    vector_store_path: str = Field(default="./data/vectorstore")
    catalog_path: str = Field(default="./data/catalog/products.json")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
