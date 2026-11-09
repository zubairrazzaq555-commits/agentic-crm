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
from pydantic import Field, field_validator, model_validator
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


class ExecutionMode(str, Enum):
    """Application AI execution mode."""

    LOCAL = "local"
    CLOUD = "cloud"
    HYBRID = "hybrid"


class HardwareProfile(str, Enum):
    """Supported hardware RAM profiles for local SLM execution."""

    AUTO = "auto"
    PROFILE_8GB = "8gb"
    PROFILE_16GB = "16gb"


def detect_system_ram_mb() -> int:
    """Detect total system physical RAM in megabytes using standard library.

    Returns total RAM in MB, or 8192 MB (8GB) if detection fails or is unsupported.
    """
    try:
        import sys
        if sys.platform.startswith("win"):
            import ctypes

            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
                return int(stat.ullTotalPhys / (1024 * 1024))
        elif sys.platform.startswith("linux"):
            if hasattr(os, "sysconf"):
                if "SC_PAGE_SIZE" in os.sysconf_names and "SC_PHYS_PAGES" in os.sysconf_names:
                    page_size = os.sysconf("SC_PAGE_SIZE")
                    phys_pages = os.sysconf("SC_PHYS_PAGES")
                    return int((page_size * phys_pages) / (1024 * 1024))
            if os.path.exists("/proc/meminfo"):
                with open("/proc/meminfo", "r", encoding="utf-8") as f:
                    for line in f:
                        if line.startswith("MemTotal:"):
                            parts = line.split()
                            if len(parts) >= 2:
                                return int(int(parts[1]) / 1024)
        elif sys.platform == "darwin":
            if hasattr(os, "sysconf") and "SC_PAGE_SIZE" in os.sysconf_names and "SC_PHYS_PAGES" in os.sysconf_names:
                page_size = os.sysconf("SC_PAGE_SIZE")
                phys_pages = os.sysconf("SC_PHYS_PAGES")
                return int((page_size * phys_pages) / (1024 * 1024))
            try:
                import ctypes
                libc = ctypes.CDLL("libc.dylib")
                memsize = ctypes.c_uint64(0)
                size = ctypes.c_size_t(ctypes.sizeof(memsize))
                if libc.sysctlbyname(b"hw.memsize", ctypes.byref(memsize), ctypes.byref(size), None, 0) == 0:
                    return int(memsize.value / (1024 * 1024))
            except Exception:
                pass
    except Exception as exc:
        logging.getLogger("agentic_crm.config").debug(
            "Failed to detect system RAM: %s. Defaulting to 8192 MB.", exc
        )
    return 8192


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
    execution_mode: ExecutionMode = Field(
        default=ExecutionMode.HYBRID,
        description="AI execution mode: local, cloud, or hybrid.",
        alias="AGENTIC_CRM_EXECUTION_MODE",
    )

    allow_cloud_fallback: bool = Field(
        default=False,
        description="Whether hybrid mode may fall back to cloud providers. Requires explicit opt-in.",
        alias="AGENTIC_CRM_ALLOW_CLOUD_FALLBACK",
    )

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

    openrouter_base_url: str = Field(
        default="https://openrouter.ai/api/v1",
        description="OpenRouter API base URL.",
        alias="OPENROUTER_BASE_URL",
    )

    openrouter_model: str = Field(
        default="nvidia/nemotron-3.5-lightning:free",
        description="Default model to use via OpenRouter.",
        alias="OPENROUTER_MODEL",
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

    ollama_timeout: float = Field(
        default=30.0,
        ge=1.0,
        le=600.0,
        description="Timeout in seconds for Ollama API requests.",
        alias="OLLAMA_TIMEOUT",
    )

    # -- Hardware profile & local memory budget -----------------------------
    ram_profile: HardwareProfile = Field(
        default=HardwareProfile.AUTO,
        description="Hardware profile for local model execution (auto, 8gb, 16gb).",
        alias="AGENTIC_CRM_RAM_PROFILE",
    )

    model_max_ram_mb: Optional[int] = Field(
        default=None,
        ge=512,
        le=65536,
        description="Explicit ceiling on local model memory in MB. Overrides profile default if set.",
        alias="AGENTIC_CRM_MODEL_MAX_RAM_MB",
    )

    model_keep_alive: str = Field(
        default="0",
        description="Ollama keep_alive duration (e.g. '0' for immediate eviction, '5m' for 5 minutes).",
        alias="AGENTIC_CRM_MODEL_KEEP_ALIVE",
    )

    # -- Validators ---------------------------------------------------------
    @field_validator("ram_profile", mode="before")
    @classmethod
    def normalize_ram_profile(cls, v: object) -> object:
        """Accept ram profile values in any case (e.g. '8GB' → '8gb')."""
        if isinstance(v, str):
            return v.lower()
        return v

    @field_validator("execution_mode", mode="before")
    @classmethod
    def normalize_execution_mode(cls, v: object) -> object:
        """Accept execution mode in any case (e.g. 'LOCAL' → 'local')."""
        if isinstance(v, str):
            return v.lower()
        return v

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

    @model_validator(mode="after")
    def enforce_execution_mode_guards(self) -> Settings:
        """
        Enforce strict isolation rules for execution modes:
        - In LOCAL mode, cloud fallback is strictly forbidden and overridden to False.
        """
        if self.execution_mode == ExecutionMode.LOCAL and self.allow_cloud_fallback:
            logging.getLogger("agentic_crm.config").warning(
                "AGENTIC_CRM_ALLOW_CLOUD_FALLBACK was set to True but execution_mode is LOCAL. "
                "Enforcing local isolation policy: overriding allow_cloud_fallback to False."
            )
            self.allow_cloud_fallback = False
        return self

    # -- Pydantic settings configuration ------------------------------------
    model_config = {
        "env_file": None,  # We load .env manually above for more control
        "case_sensitive": False,
        "extra": "ignore",  # Ignore unknown env vars
        "populate_by_name": True,  # Allow both alias and field name
    }

    # -- Utility methods ----------------------------------------------------
    @property
    def can_use_local(self) -> bool:
        """Whether local model execution is permitted under current settings."""
        return self.execution_mode in (ExecutionMode.LOCAL, ExecutionMode.HYBRID)

    @property
    def can_use_cloud(self) -> bool:
        """
        Whether cloud model execution is permitted under current settings.

        Strictly False in LOCAL mode.
        In HYBRID mode, True only if allow_cloud_fallback is explicitly True.
        In CLOUD mode, True.
        """
        if self.execution_mode == ExecutionMode.LOCAL:
            return False
        if self.execution_mode == ExecutionMode.CLOUD:
            return True
        return self.allow_cloud_fallback

    @property
    def resolved_ram_profile(self) -> HardwareProfile:
        """Resolve AUTO profile to either PROFILE_8GB or PROFILE_16GB based on detected RAM."""
        if self.ram_profile != HardwareProfile.AUTO:
            return self.ram_profile
        detected = detect_system_ram_mb()
        if detected >= 12288:  # 12 GB threshold
            return HardwareProfile.PROFILE_16GB
        return HardwareProfile.PROFILE_8GB

    @property
    def model_ram_budget_mb(self) -> int:
        """Return the effective local model RAM budget in MB."""
        if self.model_max_ram_mb is not None:
            return self.model_max_ram_mb
        if self.resolved_ram_profile == HardwareProfile.PROFILE_16GB:
            return 5500
        return 2200

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
            "execution_mode": self.execution_mode.value,
            "allow_cloud_fallback": str(self.allow_cloud_fallback),
            "can_use_local": str(self.can_use_local),
            "can_use_cloud": str(self.can_use_cloud),
            "max_retries": str(self.max_retries),
            "allow_paid_apis": str(self.allow_paid_apis),
            "gemini_api_key": _mask(self.gemini_api_key),
            "groq_api_key": _mask(self.groq_api_key),
            "openrouter_api_key": _mask(self.openrouter_api_key),
            "huggingface_api_key": _mask(self.huggingface_api_key),
            "ollama_base_url": self.ollama_base_url,
            "ollama_default_model": self.ollama_default_model,
            "ollama_timeout": str(self.ollama_timeout),
            "ram_profile": self.ram_profile.value,
            "resolved_ram_profile": self.resolved_ram_profile.value,
            "model_ram_budget_mb": str(self.model_ram_budget_mb),
            "model_keep_alive": self.model_keep_alive,
            "available_providers": ", ".join(self.get_available_providers()),
        }


__all__ = [
    "Environment",
    "ExecutionMode",
    "HardwareProfile",
    "LogLevel",
    "Settings",
    "detect_system_ram_mb",
    "get_settings",
]


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
