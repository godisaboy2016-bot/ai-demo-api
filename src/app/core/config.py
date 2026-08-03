from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings, configurable via environment variables.

    All settings can be overridden with the ``APP_`` prefix, e.g.
    ``APP_ENVIRONMENT=production``.
    """

    model_config = SettingsConfigDict(env_prefix="APP_", env_file=".env", extra="ignore")

    app_name: str = "ai-demo-api"
    app_version: str = "0.1.0"
    environment: str = "development"
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    """Return a cached settings instance."""
    return Settings()
