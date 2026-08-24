"""Application configuration management using Pydantic Settings."""

from functools import lru_cache
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration for the autonomous spotlight agent."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # EURI LLM API Configuration
    EURI_API_KEY: str = "YOUR_EURI_API_KEY"
    EURI_BASE_URL: str = "https://api.euron.one/api/v1/euri"
    EURI_MODEL: str = "gpt-4.1-mini"
    EURI_MAX_TOKENS: int = 1500
    EURI_TEMPERATURE: float = 0.55

    # GitHub API Configuration
    GITHUB_TOKEN: Optional[str] = None
    MIN_GITHUB_STARS: int = 5000

    # Telegram Bot Configuration
    TELEGRAM_BOT_TOKEN: Optional[str] = None
    TELEGRAM_CHAT_ID: Optional[str] = None

    # LinkedIn REST API Configuration
    LINKEDIN_ACCESS_TOKEN: Optional[str] = None
    LINKEDIN_PERSON_URN: Optional[str] = None

    # Storage & Persistence
    DATABASE_PATH: str = "data/history.db"

    # Server Configuration
    SERVER_HOST: str = "0.0.0.0"
    SERVER_PORT: int = 8000

    # LangSmith Real-Time Tracing Configuration
    LANGSMITH_TRACING: str = "true"
    LANGSMITH_API_KEY: Optional[str] = None
    LANGSMITH_PROJECT: str = "github-linkedin-spotlight"
    LANGSMITH_ENDPOINT: str = "https://api.smith.langchain.com"
    # Fallback aliases
    LANGCHAIN_TRACING_V2: Optional[str] = None
    LANGCHAIN_API_KEY: Optional[str] = None
    LANGCHAIN_PROJECT: Optional[str] = None
    LANGCHAIN_ENDPOINT: Optional[str] = None

    @property
    def effective_langsmith_api_key(self) -> Optional[str]:
        """Return the effective LangSmith API key."""
        return self.LANGSMITH_API_KEY or self.LANGCHAIN_API_KEY

    @property
    def effective_langsmith_project(self) -> str:
        """Return the effective LangSmith project name."""
        return self.LANGSMITH_PROJECT or self.LANGCHAIN_PROJECT or "github-linkedin-spotlight"

    @property
    def effective_langsmith_endpoint(self) -> str:
        """Return the effective LangSmith endpoint URL."""
        return self.LANGSMITH_ENDPOINT or self.LANGCHAIN_ENDPOINT or "https://api.smith.langchain.com"

    @property
    def is_langsmith_enabled(self) -> bool:
        """Check whether LangSmith tracing is active."""
        tracing_flag = (self.LANGSMITH_TRACING or self.LANGCHAIN_TRACING_V2 or "true").strip().lower()
        has_key = bool(self.effective_langsmith_api_key and self.effective_langsmith_api_key.strip())
        return has_key and tracing_flag in ("true", "1", "yes", "on")


def setup_langsmith_tracing(settings: Optional[Settings] = None) -> bool:
    """Synchronize LangSmith configuration into os.environ for LangGraph and LangChain tracers."""
    import os
    cfg = settings or get_settings()
    if cfg.is_langsmith_enabled:
        api_key = cfg.effective_langsmith_api_key.strip()
        project = cfg.effective_langsmith_project.strip()
        endpoint = cfg.effective_langsmith_endpoint.strip()

        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGSMITH_TRACING"] = "true"
        os.environ["LANGCHAIN_API_KEY"] = api_key
        os.environ["LANGSMITH_API_KEY"] = api_key
        os.environ["LANGCHAIN_PROJECT"] = project
        os.environ["LANGSMITH_PROJECT"] = project
        os.environ["LANGCHAIN_ENDPOINT"] = endpoint
        os.environ["LANGSMITH_ENDPOINT"] = endpoint
        return True
    return False


@lru_cache()
def get_settings() -> Settings:
    """Return a cached instance of application settings."""
    return Settings()
