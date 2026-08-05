from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings, configurable via environment variables.

    All settings can be overridden with the ``APP_`` prefix, e.g.
    ``APP_ENVIRONMENT=production``.
    """

    model_config = SettingsConfigDict(
        env_prefix="APP_", env_file=".env", extra="ignore", populate_by_name=True
    )

    app_name: str = "ai-demo-api"
    app_version: str = "0.1.0"
    environment: str = "development"
    log_level: str = "INFO"
    deepseek_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("DEEPSEEK_API_KEY", "APP_DEEPSEEK_API_KEY"),
    )
    deepseek_base_url: str = Field(
        default="https://api.deepseek.com",
        validation_alias=AliasChoices("DEEPSEEK_BASE_URL", "APP_DEEPSEEK_BASE_URL"),
    )
    deepseek_model: str = Field(
        default="deepseek-chat",
        validation_alias=AliasChoices("DEEPSEEK_MODEL", "APP_DEEPSEEK_MODEL"),
    )
    deepseek_timeout_seconds: float = Field(
        default=60.0,
        validation_alias=AliasChoices(
            "DEEPSEEK_TIMEOUT_SECONDS", "APP_DEEPSEEK_TIMEOUT_SECONDS"
        ),
    )


@lru_cache
def get_settings() -> Settings:
    """Return a cached settings instance."""
    return Settings()
