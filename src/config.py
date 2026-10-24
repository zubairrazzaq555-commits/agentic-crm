"""
Agentic CRM — Configuration Module

Loads application settings from environment variables (with optional .env file support).
Provides sensible defaults for development so the app can start without any API keys.

Usage:
    from src.config import get_settings

    settings = get_settings()
    print(settings.log_level)

Run directly to verify configuration:
    python -m src.config
"""

from __future__ import annotations

import logging
import os
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings

# ---------------------------------------------------------------------------
# Load .env file if present (does NOT override existing env vars)
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_ENV_FILE = _PROJECT_ROOT / ".env"

load_dotenv(_ENV_FILE, override=False)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------
class Environment(str, Enum):
    """Application environment."""

    DEVELOPMENT = "development"
    TESTING = "testing"
    PRODUCTION = "production"


class LogLevel(str, Enum):
    """Supported log levels."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------
class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.

    All cloud API keys are optional — missing keys simply disable the
    corresponding provider. The application starts and runs without any
    external API keys configured.
    """

    # -- Application --------------------------------------------------------
    env: Environment = Field(
        default=Environment.DEVELOPMENT,
        description="Application environment.",
        alias="AGENTIC_CRM_ENV",
    )

    log_level: LogLevel = Field(
        default=LogLevel.INFO,
        description="Logging level.",
        alias="AGENTIC_CRM_LOG_LEVEL",
    )

    # -- Database -----------------------------------------------------------
    db_path: str = Field(
        default="data/agentic_crm.db",
        description="Path to the SQLite database file.",
        alias="AGENTIC_CRM_DB_PATH",
    )

    # -- Provider policy ----------------------------------------------------
    max_retries: int = Field(
        default=3,
        ge=0,
        le=20,
        description="Maximum retry attempts per provider call.",
        alias="AGENTIC_CRM_MAX_RETRIES",
    )

    allow_paid_apis: bool = Field(
        default=False,
        description="Whether paid APIs may be used. Always False in this project.",
        alias="AGENTIC_CRM_ALLOW_PAID_APIS",
    )

    # -- Cloud LLM providers (all optional) ---------------------------------
    gemini_api_key: Optional[str] = Field(
        default=None,
        description="Google Gemini free-tier API key.",
        alias="GEMINI_API_KEY",
    )

    groq_api_key: Optional[str] = Field(
        default=None,
        description="Groq free-tier API key.",
        alias="GROQ_API_KEY",
    )

    openrouter_api_key: Optional[str] = Field(
        default=None,
        description="OpenRouter API key (free models only).",
        alias="OPENROUTER_API_KEY",
    )

    huggingface_api_key: Optional[str] = Field(
        default=None,
        description="HuggingFace Inference API key.",
        alias="HUGGINGFACE_API_KEY",
    )

    # -- Local LLM provider ------------------------------------------------
    ollama_base_url: str = Field(
        default="http://localhost:11434",
        description="Ollama API base URL.",
        alias="OLLAMA_BASE_URL",
    )

    ollama_default_model: str = Field(
        default="phi3:mini",
        description="Default local model to use via Ollama.",
        alias="OLLAMA_DEFAULT_MODEL",
    )

    # -- Validators ---------------------------------------------------------
    @field_validator("log_level", mode="before")
    @classmethod
    def normalize_log_level(cls, v: object) -> object:
        """Accept log level values in any case (e.g. 'warning' → 'WARNING')."""
        if isinstance(v, str):
            return v.upper()
        return v

    @field_validator("env", mode="before")
    @classmethod
    def normalize_env(cls, v: object) -> object:
        """Accept environment values in any case (e.g. 'TESTING' → 'testing')."""
        if isinstance(v, str):
            return v.lower()
        return v

    @field_validator("allow_paid_apis")
    @classmethod
    def enforce_no_paid_apis(cls, v: bool) -> bool:
        """
        Enforce the strict no-paid-fallback policy.

        Even if someone sets AGENTIC_CRM_ALLOW_PAID_APIS=true in the
        environment, this validator overrides it to False and logs a warning.
        """
        if v is True:
            logging.getLogger("agentic_crm.config").warning(
                "AGENTIC_CRM_ALLOW_PAID_APIS was set to True but the "
                "no-paid-fallback policy is enforced. Overriding to False."
            )
            return False
        return v

    # -- Pydantic settings configuration ------------------------------------
    model_config = {
        "env_file": None,  # We load .env manually above for more control
        "case_sensitive": False,
        "extra": "ignore",  # Ignore unknown env vars
        "populate_by_name": True,  # Allow both alias and field name
    }

    # -- Utility methods ----------------------------------------------------
    @property
    def database_url(self) -> str:
        """Build the SQLAlchemy async database URL from db_path."""
        return f"sqlite+aiosqlite:///{self.db_path}"

    def get_available_providers(self) -> list[str]:
        """Return a list of provider names that have API keys configured."""
        providers = []
        if self.gemini_api_key:
            providers.append("gemini")
        if self.groq_api_key:
            providers.append("groq")
        if self.openrouter_api_key:
            providers.append("openrouter")
        if self.huggingface_api_key:
            providers.append("huggingface")
        # Ollama is always "available" as a local provider (may not be running)
        providers.append("ollama")
        return providers

    def safe_summary(self) -> dict[str, str]:
        """
        Return a summary of the configuration with secrets masked.

        This is safe to print in logs or diagnostic output.
        """
        def _mask(value: Optional[str]) -> str:
            if value is None:
                return "(not set)"
            if len(value) <= 8:
                return "****"
            return f"{value[:4]}...{value[-4:]}"

        return {
            "env": self.env.value,
            "log_level": self.log_level.value,
            "db_path": self.db_path,
            "database_url": self.database_url,
            "max_retries": str(self.max_retries),
            "allow_paid_apis": str(self.allow_paid_apis),
            "gemini_api_key": _mask(self.gemini_api_key),
            "groq_api_key": _mask(self.groq_api_key),
            "openrouter_api_key": _mask(self.openrouter_api_key),
            "huggingface_api_key": _mask(self.huggingface_api_key),
            "ollama_base_url": self.ollama_base_url,
            "ollama_default_model": self.ollama_default_model,
            "available_providers": ", ".join(self.get_available_providers()),
        }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Get the application settings (cached singleton).

    Returns a cached Settings instance. Call this instead of constructing
    Settings() directly to ensure a single source of truth.
    """
    return Settings()


# ---------------------------------------------------------------------------
# Allow running directly for verification: python -m src.config
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    settings = get_settings()
    print("Agentic CRM — Configuration Summary")
    print("=" * 50)
    for key, value in settings.safe_summary().items():
        print(f"  {key:.<30s} {value}")
    print("=" * 50)
    print(f"  Available providers: {', '.join(settings.get_available_providers())}")
