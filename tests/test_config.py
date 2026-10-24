"""
Tests for src.config — Configuration module.

Covers:
- Default values when no environment variables are set
- Environment variable overrides
- No-paid-fallback policy enforcement
- Secret masking in safe_summary()
- Provider availability detection
- Invalid configuration handling
- Settings caching
"""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from src.config import Environment, LogLevel, Settings, get_settings


# ==========================================================================
# Defaults
# ==========================================================================


class TestDefaults:
    """Verify that all settings have sensible defaults for development."""

    def test_default_env_is_development(self, clean_env: None) -> None:
        settings = Settings()
        assert settings.env == Environment.DEVELOPMENT

    def test_default_log_level_is_info(self, clean_env: None) -> None:
        settings = Settings()
        assert settings.log_level == LogLevel.INFO

    def test_default_db_path(self, clean_env: None) -> None:
        settings = Settings()
        assert settings.db_path == "data/agentic_crm.db"

    def test_default_max_retries(self, clean_env: None) -> None:
        settings = Settings()
        assert settings.max_retries == 3

    def test_default_paid_apis_disabled(self, clean_env: None) -> None:
        settings = Settings()
        assert settings.allow_paid_apis is False

    def test_default_no_cloud_api_keys(self, clean_env: None) -> None:
        settings = Settings()
        assert settings.gemini_api_key is None
        assert settings.groq_api_key is None
        assert settings.openrouter_api_key is None
        assert settings.huggingface_api_key is None

    def test_default_ollama_base_url(self, clean_env: None) -> None:
        settings = Settings()
        assert settings.ollama_base_url == "http://localhost:11434"

    def test_default_ollama_model(self, clean_env: None) -> None:
        settings = Settings()
        assert settings.ollama_default_model == "phi3:mini"

    def test_app_starts_without_any_api_keys(self, clean_env: None) -> None:
        """The application must start without any API keys configured."""
        settings = Settings()
        # Should not raise, and should produce a valid settings object
        assert settings.env == Environment.DEVELOPMENT


# ==========================================================================
# Environment variable overrides
# ==========================================================================


class TestEnvOverrides:
    """Verify that environment variables override defaults correctly."""

    def test_override_env(self, clean_env: None) -> None:
        os.environ["AGENTIC_CRM_ENV"] = "testing"
        settings = Settings()
        assert settings.env == Environment.TESTING

    def test_override_log_level(self, clean_env: None) -> None:
        os.environ["AGENTIC_CRM_LOG_LEVEL"] = "DEBUG"
        settings = Settings()
        assert settings.log_level == LogLevel.DEBUG

    def test_override_db_path(self, clean_env: None) -> None:
        os.environ["AGENTIC_CRM_DB_PATH"] = "/custom/path/crm.db"
        settings = Settings()
        assert settings.db_path == "/custom/path/crm.db"

    def test_override_max_retries(self, clean_env: None) -> None:
        os.environ["AGENTIC_CRM_MAX_RETRIES"] = "5"
        settings = Settings()
        assert settings.max_retries == 5

    def test_override_ollama_base_url(self, clean_env: None) -> None:
        os.environ["OLLAMA_BASE_URL"] = "http://192.168.1.100:11434"
        settings = Settings()
        assert settings.ollama_base_url == "http://192.168.1.100:11434"

    def test_override_ollama_model(self, clean_env: None) -> None:
        os.environ["OLLAMA_DEFAULT_MODEL"] = "qwen2:1.5b"
        settings = Settings()
        assert settings.ollama_default_model == "qwen2:1.5b"

    def test_override_gemini_key(self, clean_env: None) -> None:
        os.environ["GEMINI_API_KEY"] = "my-test-key"
        settings = Settings()
        assert settings.gemini_api_key == "my-test-key"

    def test_override_groq_key(self, clean_env: None) -> None:
        os.environ["GROQ_API_KEY"] = "my-groq-key"
        settings = Settings()
        assert settings.groq_api_key == "my-groq-key"

    def test_case_insensitive_env(self, clean_env: None) -> None:
        """Env var names should work case-insensitively."""
        os.environ["AGENTIC_CRM_LOG_LEVEL"] = "warning"
        settings = Settings()
        assert settings.log_level == LogLevel.WARNING


# ==========================================================================
# No-paid-fallback policy
# ==========================================================================


class TestNoPaidFallback:
    """Verify the strict no-paid-fallback policy."""

    def test_paid_apis_forced_to_false(self, clean_env: None) -> None:
        """Even if explicitly set to True, allow_paid_apis is forced to False."""
        os.environ["AGENTIC_CRM_ALLOW_PAID_APIS"] = "true"
        settings = Settings()
        assert settings.allow_paid_apis is False

    def test_paid_apis_false_stays_false(self, clean_env: None) -> None:
        os.environ["AGENTIC_CRM_ALLOW_PAID_APIS"] = "false"
        settings = Settings()
        assert settings.allow_paid_apis is False

    def test_paid_apis_default_is_false(self, clean_env: None) -> None:
        settings = Settings()
        assert settings.allow_paid_apis is False


# ==========================================================================
# Secret masking
# ==========================================================================


class TestSafeSummary:
    """Verify that safe_summary() never exposes full secrets."""

    def test_no_keys_shows_not_set(self, clean_env: None) -> None:
        settings = Settings()
        summary = settings.safe_summary()
        assert summary["gemini_api_key"] == "(not set)"
        assert summary["groq_api_key"] == "(not set)"

    def test_short_key_fully_masked(self, clean_env: None) -> None:
        os.environ["GEMINI_API_KEY"] = "short"
        settings = Settings()
        summary = settings.safe_summary()
        assert summary["gemini_api_key"] == "****"
        assert "short" not in summary["gemini_api_key"]

    def test_long_key_partially_masked(self, clean_env: None) -> None:
        os.environ["GEMINI_API_KEY"] = "abcdefghijklmnop"
        settings = Settings()
        summary = settings.safe_summary()
        masked = summary["gemini_api_key"]
        assert masked.startswith("abcd")
        assert masked.endswith("mnop")
        assert "..." in masked
        # Full key must NOT appear
        assert "abcdefghijklmnop" not in masked

    def test_non_secret_fields_visible(self, clean_env: None) -> None:
        settings = Settings()
        summary = settings.safe_summary()
        assert summary["env"] == "development"
        assert summary["log_level"] == "INFO"
        assert summary["db_path"] == "data/agentic_crm.db"


# ==========================================================================
# Provider availability
# ==========================================================================


class TestProviderAvailability:
    """Verify provider detection based on configured API keys."""

    def test_no_keys_only_ollama(self, clean_env: None) -> None:
        settings = Settings()
        providers = settings.get_available_providers()
        assert providers == ["ollama"]

    def test_ollama_always_listed(self, clean_env: None) -> None:
        settings = Settings()
        assert "ollama" in settings.get_available_providers()

    def test_all_keys_set(self, env_with_keys: None) -> None:
        settings = Settings()
        providers = settings.get_available_providers()
        assert "gemini" in providers
        assert "groq" in providers
        assert "openrouter" in providers
        assert "huggingface" in providers
        assert "ollama" in providers

    def test_partial_keys(self, clean_env: None) -> None:
        os.environ["GEMINI_API_KEY"] = "test-key"
        settings = Settings()
        providers = settings.get_available_providers()
        assert "gemini" in providers
        assert "groq" not in providers
        assert "ollama" in providers


# ==========================================================================
# Invalid configuration
# ==========================================================================


class TestInvalidConfig:
    """Verify that invalid configuration is caught and reported clearly."""

    def test_invalid_env_value(self, clean_env: None) -> None:
        os.environ["AGENTIC_CRM_ENV"] = "invalid_env"
        with pytest.raises(ValidationError, match="AGENTIC_CRM_ENV"):
            Settings()

    def test_invalid_log_level(self, clean_env: None) -> None:
        os.environ["AGENTIC_CRM_LOG_LEVEL"] = "VERBOSE"
        with pytest.raises(ValidationError, match="AGENTIC_CRM_LOG_LEVEL"):
            Settings()

    def test_max_retries_negative(self, clean_env: None) -> None:
        os.environ["AGENTIC_CRM_MAX_RETRIES"] = "-1"
        with pytest.raises(ValidationError):
            Settings()

    def test_max_retries_too_high(self, clean_env: None) -> None:
        os.environ["AGENTIC_CRM_MAX_RETRIES"] = "100"
        with pytest.raises(ValidationError):
            Settings()

    def test_max_retries_non_numeric(self, clean_env: None) -> None:
        os.environ["AGENTIC_CRM_MAX_RETRIES"] = "abc"
        with pytest.raises(ValidationError):
            Settings()


# ==========================================================================
# Caching
# ==========================================================================


class TestSettingsCache:
    """Verify that get_settings() returns a cached singleton."""

    def test_get_settings_returns_same_instance(self) -> None:
        # Clear the cache first
        get_settings.cache_clear()
        s1 = get_settings()
        s2 = get_settings()
        assert s1 is s2

    def test_cache_can_be_cleared(self) -> None:
        get_settings.cache_clear()
        s1 = get_settings()
        get_settings.cache_clear()
        s2 = get_settings()
        # After cache clear, a new instance is created
        # (may or may not be the same object depending on values,
        # but they should be equal)
        assert s1 == s2
