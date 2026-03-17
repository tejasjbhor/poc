"""utils/config.py — centralised settings via pydantic-settings."""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-20250514"

    tavily_api_key: str = ""
    ieee_api_key: str = ""

    redis_url: str = "redis://localhost:6379/0"
    session_ttl_seconds: int = 14400

    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "INFO"

    max_pdf_size_mb: int = 50
    research_batch_size: int = 5      # requirements per agent invocation
    max_agent_iterations: int = 20


@lru_cache()
def get_settings() -> Settings:
    return Settings()
