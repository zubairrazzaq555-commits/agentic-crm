"""
Tests for src.providers.manager — ProviderManager.

Covers:
- Provider registration
- Duplicate provider handling
- Provider lookup
- Provider listing
- Provider removal / unregistering
- Provider availability checks
- Mark provider unavailable
- Restore provider health (mark healthy)
- Mark provider unhealthy
- Paid provider rejection when paid providers are disabled
- Paid provider acceptance when explicitly enabled
- Free provider acceptance
- Unavailable providers are not selected
- Circuit breaker integration (failure tracking, cooldown)
- Provider info retrieval
- Multiple providers selection
- get_available_provider with mixed states
- get_available_providers returns correct list
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest

from src.providers.base import BaseProvider, ProviderResult
from src.providers.exceptions import (
    PaidProviderError,
    ProviderNotFoundError,
    ProviderUnavailableError,
)
from src.providers.health import CircuitState, HealthStatus
from src.providers.manager import ProviderManager


# ==========================================================================
# Fake providers for testing
# ==========================================================================


class FakeProvider(BaseProvider):
    """A configurable fake provider for ProviderManager tests."""

    def __init__(
        self,
        name: str = "fake",
        model: str = "fake-model-1.0",
        is_paid: bool = False,
        available: bool = True,
    ) -> None:
        self._name = name
        self._model = model
        self._is_paid = is_paid
        self._available = available

    @property
    def name(self) -> str:
        return self._name

    @property
    def is_paid(self) -> bool:
        return self._is_paid

    @property
    def model_name(self) -> str:
        return self._model

    async def generate(self, prompt: str, **kwargs: Any) -> ProviderResult:
        return ProviderResult(
            text=f"Response from {self._name}",
            provider_name=self._name,
            model=self._model,
        )

    async def check_availability(self) -> bool:
        return self._available


# ==========================================================================
# Fixtures
# ==========================================================================


@pytest.fixture()
def manager() -> ProviderManager:
    """Create a ProviderManager with paid providers disabled (default)."""
    return ProviderManager(allow_paid=False)


@pytest.fixture()
def manager_paid_allowed() -> ProviderManager:
    """Create a ProviderManager with paid providers enabled."""
    return ProviderManager(allow_paid=True)


@pytest.fixture()
def free_provider() -> FakeProvider:
    """A free fake provider."""
    return FakeProvider(name="free-local", model="phi3:mini", is_paid=False)


@pytest.fixture()
def paid_provider() -> FakeProvider:
    """A paid fake provider."""
    return FakeProvider(name="paid-cloud", model="gpt-4", is_paid=True)


@pytest.fixture()
def second_free_provider() -> FakeProvider:
    """A second free fake provider."""
    return FakeProvider(name="free-cloud", model="gemini-flash", is_paid=False)


# ==========================================================================
# Registration
# ==========================================================================


class TestRegistration:
    """Tests for provider registration."""

    def test_register_provider(
        self, manager: ProviderManager, free_provider: FakeProvider
    ) -> None:
        manager.register(free_provider)
        assert manager.has_provider("free-local")

    def test_register_multiple_providers(
        self,
        manager: ProviderManager,
        free_provider: FakeProvider,
        second_free_provider: FakeProvider,
    ) -> None:
        manager.register(free_provider)
        manager.register(second_free_provider)
        assert manager.has_provider("free-local")
        assert manager.has_provider("free-cloud")

    def test_duplicate_registration_raises(
        self, manager: ProviderManager, free_provider: FakeProvider
    ) -> None:
        manager.register(free_provider)
        with pytest.raises(ValueError, match="already registered"):
            manager.register(free_provider)

    def test_duplicate_name_different_instance_raises(
        self, manager: ProviderManager
    ) -> None:
        p1 = FakeProvider(name="same-name")
        p2 = FakeProvider(name="same-name", model="different-model")
        manager.register(p1)
        with pytest.raises(ValueError, match="already registered"):
            manager.register(p2)

    def test_initial_health_is_healthy(
        self, manager: ProviderManager, free_provider: FakeProvider
    ) -> None:
        manager.register(free_provider)
        assert manager.get_health("free-local") == HealthStatus.HEALTHY

    def test_initial_circuit_is_closed(
        self, manager: ProviderManager, free_provider: FakeProvider
    ) -> None:
        manager.register(free_provider)
        cb = manager.get_circuit_breaker("free-local")
        assert cb.state == CircuitState.CLOSED


# ==========================================================================
# Lookup
# ==========================================================================


class TestLookup:
    """Tests for provider lookup."""

    def test_get_provider_success(
        self, manager: ProviderManager, free_provider: FakeProvider
    ) -> None:
        manager.register(free_provider)
        p = manager.get_provider("free-local")
        assert p is free_provider

    def test_get_provider_not_found(self, manager: ProviderManager) -> None:
        with pytest.raises(ProviderNotFoundError, match="nonexistent"):
            manager.get_provider("nonexistent")

    def test_has_provider_true(
        self, manager: ProviderManager, free_provider: FakeProvider
    ) -> None:
        manager.register(free_provider)
        assert manager.has_provider("free-local") is True

    def test_has_provider_false(self, manager: ProviderManager) -> None:
        assert manager.has_provider("nonexistent") is False


# ==========================================================================
# Listing
# ==========================================================================


class TestListing:
    """Tests for provider listing."""

    def test_list_empty(self, manager: ProviderManager) -> None:
        assert manager.list_providers() == []

    def test_list_single_provider(
        self, manager: ProviderManager, free_provider: FakeProvider
    ) -> None:
        manager.register(free_provider)
        assert manager.list_providers() == ["free-local"]

    def test_list_multiple_sorted(
        self,
        manager: ProviderManager,
        free_provider: FakeProvider,
        second_free_provider: FakeProvider,
    ) -> None:
        manager.register(free_provider)
        manager.register(second_free_provider)
        names = manager.list_providers()
        assert names == sorted(names)
        assert "free-cloud" in names
        assert "free-local" in names


# ==========================================================================
# Removal
# ==========================================================================


class TestRemoval:
    """Tests for provider removal."""

    def test_unregister_provider(
        self, manager: ProviderManager, free_provider: FakeProvider
    ) -> None:
        manager.register(free_provider)
        manager.unregister("free-local")
        assert not manager.has_provider("free-local")

    def test_unregister_not_found(self, manager: ProviderManager) -> None:
        with pytest.raises(ProviderNotFoundError, match="nonexistent"):
            manager.unregister("nonexistent")

    def test_unregister_cleans_up_health(
        self, manager: ProviderManager, free_provider: FakeProvider
    ) -> None:
        manager.register(free_provider)
        manager.unregister("free-local")
        with pytest.raises(ProviderNotFoundError):
            manager.get_health("free-local")

    def test_unregister_cleans_up_circuit_breaker(
        self, manager: ProviderManager, free_provider: FakeProvider
    ) -> None:
        manager.register(free_provider)
        manager.unregister("free-local")
        with pytest.raises(ProviderNotFoundError):
            manager.get_circuit_breaker("free-local")

    def test_can_reregister_after_unregister(
        self, manager: ProviderManager, free_provider: FakeProvider
    ) -> None:
        manager.register(free_provider)
        manager.unregister("free-local")
        manager.register(free_provider)
        assert manager.has_provider("free-local")


# ==========================================================================
# Health management
# ==========================================================================


class TestHealthManagement:
    """Tests for provider health tracking."""

    def test_get_health_not_found(self, manager: ProviderManager) -> None:
        with pytest.raises(ProviderNotFoundError):
            manager.get_health("missing")

    def test_mark_unavailable(
        self, manager: ProviderManager, free_provider: FakeProvider
    ) -> None:
        manager.register(free_provider)
        manager.mark_unavailable("free-local")
        assert manager.get_health("free-local") == HealthStatus.UNAVAILABLE

    def test_mark_unavailable_not_found(self, manager: ProviderManager) -> None:
        with pytest.raises(ProviderNotFoundError):
            manager.mark_unavailable("missing")

    def test_mark_healthy_restores(
        self, manager: ProviderManager, free_provider: FakeProvider
    ) -> None:
        manager.register(free_provider)
        manager.mark_unavailable("free-local")
        assert manager.get_health("free-local") == HealthStatus.UNAVAILABLE

        manager.mark_healthy("free-local")
        assert manager.get_health("free-local") == HealthStatus.HEALTHY

    def test_mark_healthy_resets_circuit(
        self, manager: ProviderManager, free_provider: FakeProvider
    ) -> None:
        manager.register(free_provider)
        # Trigger circuit breaker
        for _ in range(10):
            manager.record_failure("free-local")
        cb = manager.get_circuit_breaker("free-local")
        assert cb.state == CircuitState.OPEN

        manager.mark_healthy("free-local")
        assert cb.state == CircuitState.CLOSED
        assert cb.consecutive_failures == 0

    def test_mark_healthy_not_found(self, manager: ProviderManager) -> None:
        with pytest.raises(ProviderNotFoundError):
            manager.mark_healthy("missing")

    def test_mark_unhealthy(
        self, manager: ProviderManager, free_provider: FakeProvider
    ) -> None:
        manager.register(free_provider)
        manager.mark_unhealthy("free-local")
        assert manager.get_health("free-local") == HealthStatus.UNHEALTHY

    def test_mark_unhealthy_not_found(self, manager: ProviderManager) -> None:
        with pytest.raises(ProviderNotFoundError):
            manager.mark_unhealthy("missing")


# ==========================================================================
# Paid provider policy
# ==========================================================================


class TestPaidProviderPolicy:
    """Tests for paid provider safety — NO AUTOMATIC PAID API FALLBACK."""

    def test_register_paid_rejected_when_disabled(
        self, manager: ProviderManager, paid_provider: FakeProvider
    ) -> None:
        """Paid providers must be rejected when allow_paid=False."""
        with pytest.raises(PaidProviderError, match="not allowed"):
            manager.register(paid_provider)

    def test_register_paid_accepted_when_enabled(
        self, manager_paid_allowed: ProviderManager, paid_provider: FakeProvider
    ) -> None:
        """Paid providers are accepted when allow_paid=True."""
        manager_paid_allowed.register(paid_provider)
        assert manager_paid_allowed.has_provider("paid-cloud")

    def test_free_provider_always_accepted(
        self, manager: ProviderManager, free_provider: FakeProvider
    ) -> None:
        """Free providers are always accepted."""
        manager.register(free_provider)
        assert manager.has_provider("free-local")

    def test_paid_provider_not_available_when_disabled(
        self, manager_paid_allowed: ProviderManager, paid_provider: FakeProvider
    ) -> None:
        """Even if registered, paid providers aren't available when policy changes."""
        manager_paid_allowed.register(paid_provider)
        # Change policy
        manager_paid_allowed.allow_paid = False
        assert manager_paid_allowed.is_available("paid-cloud") is False

    def test_paid_provider_available_when_enabled(
        self, manager_paid_allowed: ProviderManager, paid_provider: FakeProvider
    ) -> None:
        manager_paid_allowed.register(paid_provider)
        assert manager_paid_allowed.is_available("paid-cloud") is True

    def test_no_fallback_to_paid(
        self,
        manager_paid_allowed: ProviderManager,
        free_provider: FakeProvider,
        paid_provider: FakeProvider,
    ) -> None:
        """When free providers are unavailable, paid providers must not be selected
        if paid providers are disabled by policy."""
        manager_paid_allowed.register(free_provider)
        manager_paid_allowed.register(paid_provider)

        # Mark free provider unavailable
        manager_paid_allowed.mark_unavailable("free-local")
        # Disable paid
        manager_paid_allowed.allow_paid = False

        # Should raise — only paid is left but it's not allowed
        with pytest.raises(ProviderUnavailableError):
            manager_paid_allowed.get_available_provider()

    def test_allow_paid_property(self, manager: ProviderManager) -> None:
        assert manager.allow_paid is False
        manager.allow_paid = True
        assert manager.allow_paid is True


# ==========================================================================
# Availability checks
# ==========================================================================


class TestAvailability:
    """Tests for provider availability checks."""

    def test_available_when_healthy(
        self, manager: ProviderManager, free_provider: FakeProvider
    ) -> None:
        manager.register(free_provider)
        assert manager.is_available("free-local") is True

    def test_not_available_when_unavailable(
        self, manager: ProviderManager, free_provider: FakeProvider
    ) -> None:
        manager.register(free_provider)
        manager.mark_unavailable("free-local")
        assert manager.is_available("free-local") is False

    def test_available_when_unhealthy_and_circuit_closed(
        self, manager: ProviderManager, free_provider: FakeProvider
    ) -> None:
        """UNHEALTHY but with circuit closed = still available (degraded)."""
        manager.register(free_provider)
        manager.mark_unhealthy("free-local")
        assert manager.is_available("free-local") is True

    def test_not_available_when_circuit_open(
        self, manager: ProviderManager, free_provider: FakeProvider
    ) -> None:
        manager.register(free_provider)
        for _ in range(5):
            manager.record_failure("free-local")
        assert manager.is_available("free-local") is False

    def test_not_available_when_not_registered(
        self, manager: ProviderManager
    ) -> None:
        assert manager.is_available("nonexistent") is False

    def test_unavailable_provider_not_selected(
        self,
        manager: ProviderManager,
        free_provider: FakeProvider,
        second_free_provider: FakeProvider,
    ) -> None:
        """Unavailable providers should be skipped during selection."""
        manager.register(free_provider)
        manager.register(second_free_provider)
        manager.mark_unavailable("free-local")

        selected = manager.get_available_provider()
        assert selected.name == "free-cloud"

    def test_no_available_providers_raises(self, manager: ProviderManager) -> None:
        with pytest.raises(ProviderUnavailableError, match="No available"):
            manager.get_available_provider()

    def test_all_unavailable_raises(
        self, manager: ProviderManager, free_provider: FakeProvider
    ) -> None:
        manager.register(free_provider)
        manager.mark_unavailable("free-local")
        with pytest.raises(ProviderUnavailableError):
            manager.get_available_provider()


# ==========================================================================
# Circuit breaker integration with manager
# ==========================================================================


class TestCircuitBreakerIntegration:
    """Tests for circuit breaker integration with the ProviderManager."""

    def test_record_success_resets_circuit(
        self, manager: ProviderManager, free_provider: FakeProvider
    ) -> None:
        manager.register(free_provider)
        manager.record_failure("free-local")
        manager.record_failure("free-local")
        manager.record_success("free-local")
        cb = manager.get_circuit_breaker("free-local")
        assert cb.consecutive_failures == 0
        assert cb.state == CircuitState.CLOSED

    def test_record_success_restores_health(
        self, manager: ProviderManager, free_provider: FakeProvider
    ) -> None:
        manager.register(free_provider)
        manager.record_failure("free-local")
        manager.record_success("free-local")
        assert manager.get_health("free-local") == HealthStatus.HEALTHY

    def test_record_failure_opens_circuit(
        self, manager: ProviderManager, free_provider: FakeProvider
    ) -> None:
        manager.register(free_provider)
        for _ in range(5):
            manager.record_failure("free-local")
        cb = manager.get_circuit_breaker("free-local")
        assert cb.state == CircuitState.OPEN

    def test_record_failure_sets_unhealthy(
        self, manager: ProviderManager, free_provider: FakeProvider
    ) -> None:
        manager.register(free_provider)
        for _ in range(5):
            manager.record_failure("free-local")
        assert manager.get_health("free-local") == HealthStatus.UNHEALTHY

    def test_record_success_not_found(self, manager: ProviderManager) -> None:
        with pytest.raises(ProviderNotFoundError):
            manager.record_success("missing")

    def test_record_failure_not_found(self, manager: ProviderManager) -> None:
        with pytest.raises(ProviderNotFoundError):
            manager.record_failure("missing")

    def test_circuit_cooldown_restores_availability(
        self, manager: ProviderManager, free_provider: FakeProvider
    ) -> None:
        """After cooldown, the circuit should transition to HALF_OPEN and
        the provider should be available again."""
        manager.register(free_provider)

        with patch("src.providers.health.time.monotonic") as mock_time:
            mock_time.return_value = 100.0
            for _ in range(5):
                manager.record_failure("free-local")
            assert manager.is_available("free-local") is False

            # Advance past cooldown (default 60s)
            mock_time.return_value = 300.0
            assert manager.is_available("free-local") is True

    def test_custom_circuit_breaker_config(self) -> None:
        """ProviderManager should use custom circuit breaker settings."""
        mgr = ProviderManager(
            circuit_breaker_failure_threshold=2,
            circuit_breaker_cooldown_seconds=30.0,
        )
        p = FakeProvider(name="test")
        mgr.register(p)

        cb = mgr.get_circuit_breaker("test")
        assert cb.failure_threshold == 2
        assert cb.cooldown_seconds == 30.0

        # Should open after 2 failures
        mgr.record_failure("test")
        mgr.record_failure("test")
        assert cb.state == CircuitState.OPEN


# ==========================================================================
# get_available_providers
# ==========================================================================


class TestGetAvailableProviders:
    """Tests for getting all available providers."""

    def test_empty_manager(self, manager: ProviderManager) -> None:
        assert manager.get_available_providers() == []

    def test_all_available(
        self,
        manager: ProviderManager,
        free_provider: FakeProvider,
        second_free_provider: FakeProvider,
    ) -> None:
        manager.register(free_provider)
        manager.register(second_free_provider)
        available = manager.get_available_providers()
        assert len(available) == 2

    def test_some_unavailable(
        self,
        manager: ProviderManager,
        free_provider: FakeProvider,
        second_free_provider: FakeProvider,
    ) -> None:
        manager.register(free_provider)
        manager.register(second_free_provider)
        manager.mark_unavailable("free-local")
        available = manager.get_available_providers()
        assert len(available) == 1
        assert available[0].name == "free-cloud"

    def test_excludes_paid_when_disabled(
        self, manager_paid_allowed: ProviderManager, paid_provider: FakeProvider
    ) -> None:
        manager_paid_allowed.register(paid_provider)
        manager_paid_allowed.allow_paid = False
        available = manager_paid_allowed.get_available_providers()
        assert len(available) == 0


# ==========================================================================
# Provider info
# ==========================================================================


class TestProviderInfo:
    """Tests for provider info retrieval."""

    def test_get_provider_info(
        self, manager: ProviderManager, free_provider: FakeProvider
    ) -> None:
        manager.register(free_provider)
        info = manager.get_provider_info("free-local")
        assert info["name"] == "free-local"
        assert info["model"] == "phi3:mini"
        assert info["is_paid"] is False
        assert info["health"] == "healthy"
        assert info["circuit_state"] == "closed"
        assert info["consecutive_failures"] == 0
        assert info["is_available"] is True

    def test_get_provider_info_not_found(self, manager: ProviderManager) -> None:
        with pytest.raises(ProviderNotFoundError):
            manager.get_provider_info("missing")

    def test_get_provider_info_after_failures(
        self, manager: ProviderManager, free_provider: FakeProvider
    ) -> None:
        manager.register(free_provider)
        manager.record_failure("free-local")
        manager.record_failure("free-local")
        info = manager.get_provider_info("free-local")
        assert info["consecutive_failures"] == 2
        assert info["health"] == "healthy"  # Not enough to open circuit

    def test_get_provider_info_circuit_open(
        self, manager: ProviderManager, free_provider: FakeProvider
    ) -> None:
        manager.register(free_provider)
        for _ in range(5):
            manager.record_failure("free-local")
        info = manager.get_provider_info("free-local")
        assert info["circuit_state"] == "open"
        assert info["health"] == "unhealthy"
        assert info["is_available"] is False


# ==========================================================================
# Async generation via manager
# ==========================================================================


class TestAsyncGenerationViaManager:
    """Test that providers registered in the manager can generate."""

    async def test_generate_via_registered_provider(
        self, manager: ProviderManager, free_provider: FakeProvider
    ) -> None:
        manager.register(free_provider)
        provider = manager.get_provider("free-local")
        result = await provider.generate("Test prompt")
        assert result.text == "Response from free-local"
        assert result.provider_name == "free-local"

    async def test_generate_via_selected_provider(
        self, manager: ProviderManager, free_provider: FakeProvider
    ) -> None:
        manager.register(free_provider)
        provider = manager.get_available_provider()
        result = await provider.generate("Hello")
        assert isinstance(result, ProviderResult)
