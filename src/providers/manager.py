"""
Agentic CRM — Provider Manager.

The ProviderManager is a registry of provider instances with health
tracking and paid-provider policy enforcement.

Responsibilities:
    - Register / unregister providers.
    - Look up providers by name.
    - List registered providers.
    - Track provider health status.
    - Enforce the NO AUTOMATIC PAID API FALLBACK policy.
    - Provide basic provider selection (by name, first available).
    - Integrate with per-provider CircuitBreakers.

Architecture boundary:
    The ProviderManager manages providers.
    It does NOT implement model routing, task routing, cost optimization,
    token budgeting, or automatic multi-provider fallback.  Those belong
    to the future Model Router / Provider Pool milestones.

Thread-safety:
    This class is designed for use within a single asyncio event loop.
    It is NOT thread-safe.
"""

from __future__ import annotations

import logging
from typing import Any

from src.providers.base import BaseProvider
from src.providers.exceptions import (
    PaidProviderError,
    ProviderError,
    ProviderNotFoundError,
    ProviderUnavailableError,
)
from src.providers.health import CircuitBreaker, CircuitState, HealthStatus

logger = logging.getLogger("agentic_crm.providers.manager")


class ProviderManager:
    """Registry and manager for AI providers.

    Supports:
        - Provider registration with duplicate detection.
        - Provider lookup by name.
        - Listing all registered providers.
        - Removing/unregistering providers.
        - Health status tracking per provider.
        - Circuit breaker per provider.
        - Paid-provider policy enforcement.
        - Selecting an available provider (explicit selection).

    Example::

        manager = ProviderManager(allow_paid=False)

        manager.register(my_free_provider)
        provider = manager.get_provider("ollama")

        available = manager.get_available_provider()
    """

    def __init__(
        self,
        *,
        allow_paid: bool = False,
        circuit_breaker_failure_threshold: int = 5,
        circuit_breaker_cooldown_seconds: float = 60.0,
    ) -> None:
        """Create a ProviderManager.

        Args:
            allow_paid: Whether paid providers are allowed.
                        Defaults to False (strict no-paid policy).
            circuit_breaker_failure_threshold: Number of consecutive failures
                        before a provider's circuit opens.
            circuit_breaker_cooldown_seconds: Seconds a circuit stays open
                        before transitioning to HALF_OPEN.
        """
        self._allow_paid = allow_paid
        self._cb_failure_threshold = circuit_breaker_failure_threshold
        self._cb_cooldown_seconds = circuit_breaker_cooldown_seconds

        # provider name → provider instance
        self._providers: dict[str, BaseProvider] = {}
        # provider name → health status
        self._health: dict[str, HealthStatus] = {}
        # provider name → circuit breaker
        self._circuit_breakers: dict[str, CircuitBreaker] = {}

    # -- Configuration properties -------------------------------------------

    @property
    def allow_paid(self) -> bool:
        """Whether paid providers are currently allowed."""
        return self._allow_paid

    @allow_paid.setter
    def allow_paid(self, value: bool) -> None:
        """Set whether paid providers are allowed.

        Changing this at runtime affects future provider selection
        but does not unregister existing paid providers.
        """
        self._allow_paid = value

    # -- Registration -------------------------------------------------------

    def register(self, provider: BaseProvider) -> None:
        """Register a provider.

        Args:
            provider: A BaseProvider instance to register.

        Raises:
            ValueError: If a provider with the same name is already registered.
            PaidProviderError: If the provider is paid and paid providers
                               are not allowed.
        """
        name = provider.name

        if name in self._providers:
            raise ValueError(
                f"Provider {name!r} is already registered. "
                "Unregister it first if you want to replace it."
            )

        if provider.is_paid and not self._allow_paid:
            raise PaidProviderError(name)

        self._providers[name] = provider
        self._health[name] = HealthStatus.HEALTHY
        self._circuit_breakers[name] = CircuitBreaker(
            failure_threshold=self._cb_failure_threshold,
            cooldown_seconds=self._cb_cooldown_seconds,
        )

        logger.info(
            "Registered provider %r (model=%r, paid=%s)",
            name,
            provider.model_name,
            provider.is_paid,
        )

    def unregister(self, name: str) -> None:
        """Remove a provider from the registry.

        Args:
            name: The provider name to unregister.

        Raises:
            ProviderNotFoundError: If the provider is not registered.
        """
        if name not in self._providers:
            raise ProviderNotFoundError(name)

        del self._providers[name]
        del self._health[name]
        del self._circuit_breakers[name]

        logger.info("Unregistered provider %r", name)

    # -- Lookup -------------------------------------------------------------

    def get_provider(self, name: str) -> BaseProvider:
        """Look up a registered provider by name.

        Args:
            name: The provider name.

        Returns:
            The registered BaseProvider instance.

        Raises:
            ProviderNotFoundError: If the provider is not registered.
        """
        if name not in self._providers:
            raise ProviderNotFoundError(name)
        return self._providers[name]

    def list_providers(self) -> list[str]:
        """Return a sorted list of registered provider names."""
        return sorted(self._providers.keys())

    def has_provider(self, name: str) -> bool:
        """Check if a provider is registered."""
        return name in self._providers

    # -- Health management --------------------------------------------------

    def get_health(self, name: str) -> HealthStatus:
        """Get the health status of a registered provider.

        Args:
            name: The provider name.

        Returns:
            The current HealthStatus.

        Raises:
            ProviderNotFoundError: If the provider is not registered.
        """
        if name not in self._providers:
            raise ProviderNotFoundError(name)
        return self._health[name]

    def mark_healthy(self, name: str) -> None:
        """Mark a provider as healthy and reset its circuit breaker.

        Args:
            name: The provider name.

        Raises:
            ProviderNotFoundError: If the provider is not registered.
        """
        if name not in self._providers:
            raise ProviderNotFoundError(name)

        self._health[name] = HealthStatus.HEALTHY
        self._circuit_breakers[name].reset()
        logger.info("Provider %r marked healthy", name)

    def mark_unavailable(self, name: str) -> None:
        """Mark a provider as unavailable.

        Args:
            name: The provider name.

        Raises:
            ProviderNotFoundError: If the provider is not registered.
        """
        if name not in self._providers:
            raise ProviderNotFoundError(name)

        self._health[name] = HealthStatus.UNAVAILABLE
        logger.warning("Provider %r marked unavailable", name)

    def mark_unhealthy(self, name: str) -> None:
        """Mark a provider as unhealthy (degraded but not fully unavailable).

        Args:
            name: The provider name.

        Raises:
            ProviderNotFoundError: If the provider is not registered.
        """
        if name not in self._providers:
            raise ProviderNotFoundError(name)

        self._health[name] = HealthStatus.UNHEALTHY
        logger.warning("Provider %r marked unhealthy", name)

    # -- Circuit breaker access ---------------------------------------------

    def get_circuit_breaker(self, name: str) -> CircuitBreaker:
        """Get the circuit breaker for a registered provider.

        Args:
            name: The provider name.

        Returns:
            The CircuitBreaker instance for this provider.

        Raises:
            ProviderNotFoundError: If the provider is not registered.
        """
        if name not in self._providers:
            raise ProviderNotFoundError(name)
        return self._circuit_breakers[name]

    def record_success(self, name: str) -> None:
        """Record a successful call to a provider.

        Updates the circuit breaker and health status.

        Args:
            name: The provider name.

        Raises:
            ProviderNotFoundError: If the provider is not registered.
        """
        if name not in self._providers:
            raise ProviderNotFoundError(name)

        self._circuit_breakers[name].record_success()
        self._health[name] = HealthStatus.HEALTHY

    def record_failure(self, name: str) -> None:
        """Record a failed call to a provider.

        Updates the circuit breaker.  If the circuit opens, the provider's
        health status is set to UNHEALTHY.

        Args:
            name: The provider name.

        Raises:
            ProviderNotFoundError: If the provider is not registered.
        """
        if name not in self._providers:
            raise ProviderNotFoundError(name)

        cb = self._circuit_breakers[name]
        cb.record_failure()

        if cb.state == CircuitState.OPEN:
            self._health[name] = HealthStatus.UNHEALTHY
            logger.warning(
                "Provider %r circuit opened after %d consecutive failures",
                name,
                cb.consecutive_failures,
            )

    # -- Availability checks ------------------------------------------------

    def is_available(self, name: str) -> bool:
        """Check whether a provider is currently available for use.

        A provider is available if:
        1. It is registered.
        2. Its health status is HEALTHY or UNHEALTHY (not UNAVAILABLE).
        3. Its circuit breaker allows requests (CLOSED or HALF_OPEN).
        4. If it's paid, paid providers must be allowed.

        Args:
            name: The provider name.

        Returns:
            True if the provider can be used, False otherwise.
        """
        if name not in self._providers:
            return False

        provider = self._providers[name]

        # Paid policy check
        if provider.is_paid and not self._allow_paid:
            return False

        # Health check
        if self._health[name] == HealthStatus.UNAVAILABLE:
            return False

        # Circuit breaker check
        if not self._circuit_breakers[name].is_available:
            return False

        return True

    # -- Selection ----------------------------------------------------------

    def get_available_provider(self) -> BaseProvider:
        """Select the first available provider.

        Iterates through registered providers in registration order
        and returns the first one that is available.

        This is basic explicit selection, NOT intelligent routing.
        The future Model Router will implement cost-aware, capability-aware
        selection.

        Returns:
            An available BaseProvider instance.

        Raises:
            ProviderUnavailableError: If no provider is currently available.
        """
        for name, provider in self._providers.items():
            if self.is_available(name):
                return provider

        raise ProviderUnavailableError(
            provider_name="*",
            reason="No available providers registered",
        )

    def get_available_providers(self) -> list[BaseProvider]:
        """Return all currently available providers.

        Returns:
            A list of available BaseProvider instances (may be empty).
        """
        return [
            provider
            for name, provider in self._providers.items()
            if self.is_available(name)
        ]

    def get_provider_info(self, name: str) -> dict[str, Any]:
        """Get detailed info about a registered provider.

        Args:
            name: The provider name.

        Returns:
            A dict with provider details.

        Raises:
            ProviderNotFoundError: If the provider is not registered.
        """
        if name not in self._providers:
            raise ProviderNotFoundError(name)

        provider = self._providers[name]
        cb = self._circuit_breakers[name]

        return {
            "name": provider.name,
            "model": provider.model_name,
            "is_paid": provider.is_paid,
            "health": self._health[name].value,
            "circuit_state": cb.state.value,
            "consecutive_failures": cb.consecutive_failures,
            "is_available": self.is_available(name),
        }
