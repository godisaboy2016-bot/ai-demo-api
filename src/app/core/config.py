from functools import lru_cache
from typing import Self

from pydantic import AliasChoices, Field, model_validator
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
    database_url: str = Field(
        default="postgresql+asyncpg://ai_demo:ai_demo@db:5432/ai_demo",
        validation_alias=AliasChoices("DATABASE_URL", "APP_DATABASE_URL"),
    )
    jwt_secret_key: str = Field(
        default="",
        validation_alias=AliasChoices("JWT_SECRET_KEY", "APP_JWT_SECRET_KEY"),
    )
    jwt_algorithm: str = Field(
        default="HS256",
        validation_alias=AliasChoices("JWT_ALGORITHM", "APP_JWT_ALGORITHM"),
    )
    access_token_expire_minutes: int = Field(
        default=30,
        validation_alias=AliasChoices(
            "ACCESS_TOKEN_EXPIRE_MINUTES", "APP_ACCESS_TOKEN_EXPIRE_MINUTES"
        ),
    )

    @model_validator(mode="after")
    def _validate_jwt_secret(self: Self) -> Self:
        """Fail fast on a missing or weak JWT secret."""

        if not self.jwt_secret_key:
            raise ValueError("JWT_SECRET_KEY must be configured")
        if self.environment == "production" and len(self.jwt_secret_key) < 32:
            raise ValueError("JWT_SECRET_KEY must be at least 32 characters long")
        return self


@lru_cache
def get_settings() -> Settings:
    """Return a cached settings instance."""
    return Settings()
