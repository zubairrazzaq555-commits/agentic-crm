"""Agentic CRM — Provider abstraction layer.

Provides the base provider interface, provider result structure,
health tracking, circuit breaker, and provider manager.
"""

from src.providers.base import (
    BaseProvider,
    ModelDescriptor,
    ModelTier,
    ProviderResult,
    TaskComplexity,
)
from src.providers.exceptions import (
    PaidProviderError,
    ProviderError,
    ProviderNotFoundError,
    ProviderUnavailableError,
)
from src.providers.health import CircuitBreaker, CircuitState, HealthStatus
from src.providers.manager import ProviderManager
from src.providers.mock_provider import MockProvider
from src.providers.ollama import OllamaProvider
from src.providers.openrouter import OpenRouterProvider

__all__ = [
    "BaseProvider",
    "CircuitBreaker",
    "CircuitState",
    "HealthStatus",
    "MockProvider",
    "ModelDescriptor",
    "ModelTier",
    "OllamaProvider",
    "OpenRouterProvider",
    "PaidProviderError",
    "ProviderError",
    "ProviderManager",
    "ProviderNotFoundError",
    "ProviderResult",
    "ProviderUnavailableError",
    "TaskComplexity",
]
