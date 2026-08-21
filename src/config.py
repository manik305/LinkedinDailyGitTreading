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


@lru_cache()
def get_settings() -> Settings:
    """Return a cached instance of application settings."""
    return Settings()
