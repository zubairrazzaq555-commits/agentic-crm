"""Agentic CRM — Provider abstraction layer.

Provides the base provider interface, provider result structure,
health tracking, circuit breaker, and provider manager.
"""

from src.config import HardwareProfile
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
from src.providers.lifecycle import (
    MemoryBudgetExceededError,
    ModelLifecycleError,
    ModelLifecycleManager,
    ModelLoadState,
)
from src.providers.manager import ProviderManager
from src.providers.mock_provider import MockProvider
from src.providers.ollama import OllamaProvider
from src.providers.openrouter import OpenRouterProvider

__all__ = [
    "BaseProvider",
    "CircuitBreaker",
    "CircuitState",
    "HardwareProfile",
    "HealthStatus",
    "MemoryBudgetExceededError",
    "MockProvider",
    "ModelDescriptor",
    "ModelLifecycleError",
    "ModelLifecycleManager",
    "ModelLoadState",
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
