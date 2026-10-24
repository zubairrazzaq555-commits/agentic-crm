"""Shared test fixtures for the Agentic CRM test suite."""

from __future__ import annotations

import os
from collections.abc import Generator
from unittest.mock import patch

import pytest


@pytest.fixture()
def clean_env() -> Generator[None, None, None]:
    """
    Fixture that clears all AGENTIC_CRM_* and provider env vars before a test,
    then restores the original environment after.

    This ensures tests are isolated from the host's real environment.
    """
    # Env var prefixes and exact names to clear
    prefixes = ("AGENTIC_CRM_", "GEMINI_", "GROQ_", "OPENROUTER_", "HUGGINGFACE_", "OLLAMA_")
    keys_to_clear = [k for k in os.environ if any(k.startswith(p) for p in prefixes)]

    with patch.dict(os.environ, {}, clear=False):
        # Remove all matching keys
        for key in keys_to_clear:
            os.environ.pop(key, None)
        yield


@pytest.fixture()
def env_with_keys(clean_env: None) -> Generator[None, None, None]:
    """
    Fixture that sets dummy API keys for all providers.
    Depends on clean_env to start from a clean state.
    """
    os.environ["GEMINI_API_KEY"] = "test-gemini-key-1234567890"
    os.environ["GROQ_API_KEY"] = "test-groq-key-1234567890"
    os.environ["OPENROUTER_API_KEY"] = "test-openrouter-key-1234567890"
    os.environ["HUGGINGFACE_API_KEY"] = "test-huggingface-key-1234567890"
    yield
