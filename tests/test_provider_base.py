"""
Tests for src.providers.base and src.providers.health — Provider interface,
result structure, health tracking, and circuit breaker.

Covers:
- ProviderResult creation with required fields
- ProviderResult creation with all optional fields
- ProviderResult immutability (frozen)
- ProviderResult default values
- BaseProvider cannot be instantiated directly
- BaseProvider contract enforcement (subclass must implement abstract methods)
- HealthStatus enum values
- CircuitState enum values
- CircuitBreaker initial state
- CircuitBreaker failure tracking
- CircuitBreaker opens after threshold
- CircuitBreaker cooldown / HALF_OPEN recovery
- CircuitBreaker success resets state
- CircuitBreaker failure in HALF_OPEN reopens
- CircuitBreaker manual reset
- CircuitBreaker validation of constructor args
- Async provider generation using a fake provider
- Fake provider check_availability
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest

from src.providers.base import BaseProvider, ProviderResult
from src.providers.health import CircuitBreaker, CircuitState, HealthStatus


# ==========================================================================
# Fake provider for testing
# ==========================================================================


class FakeProvider(BaseProvider):
    """A minimal concrete provider for testing the abstract interface."""

    def __init__(
        self,
        name: str = "fake",
        model: str = "fake-model-1.0",
        is_paid: bool = False,
        available: bool = True,
        response_text: str = "Hello from fake provider",
    ) -> None:
        self._name = name
        self._model = model
        self._is_paid = is_paid
        self._available = available
        self._response_text = response_text

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
            text=self._response_text,
            provider_name=self._name,
            model=self._model,
            prompt_tokens=len(prompt.split()),
            completion_tokens=len(self._response_text.split()),
            total_tokens=len(prompt.split()) + len(self._response_text.split()),
            latency_ms=1.5,
            metadata={"test": True},
        )

    async def check_availability(self) -> bool:
        return self._available


# ==========================================================================
# ProviderResult
# ==========================================================================


class TestProviderResult:
    """Tests for the ProviderResult dataclass."""

    def test_required_fields(self) -> None:
        result = ProviderResult(
            text="Hello world",
            provider_name="test",
            model="test-model",
        )
        assert result.text == "Hello world"
        assert result.provider_name == "test"
        assert result.model == "test-model"

    def test_optional_fields_default_to_none(self) -> None:
        result = ProviderResult(
            text="Hello",
            provider_name="test",
            model="test-model",
        )
        assert result.prompt_tokens is None
        assert result.completion_tokens is None
        assert result.total_tokens is None
        assert result.latency_ms is None

    def test_optional_metadata_defaults_to_empty_dict(self) -> None:
        result = ProviderResult(
            text="Hello",
            provider_name="test",
            model="test-model",
        )
        assert result.metadata == {}

    def test_all_fields(self) -> None:
        result = ProviderResult(
            text="Generated text",
            provider_name="gemini",
            model="gemini-pro",
            prompt_tokens=10,
            completion_tokens=20,
            total_tokens=30,
            latency_ms=150.5,
            metadata={"finish_reason": "stop"},
        )
        assert result.text == "Generated text"
        assert result.provider_name == "gemini"
        assert result.model == "gemini-pro"
        assert result.prompt_tokens == 10
        assert result.completion_tokens == 20
        assert result.total_tokens == 30
        assert result.latency_ms == 150.5
        assert result.metadata == {"finish_reason": "stop"}

    def test_frozen_immutability(self) -> None:
        """ProviderResult should be immutable (frozen dataclass)."""
        result = ProviderResult(
            text="Hello",
            provider_name="test",
            model="test-model",
        )
        with pytest.raises(AttributeError):
            result.text = "modified"  # type: ignore[misc]

    def test_metadata_isolation_between_instances(self) -> None:
        """Default metadata dicts should be independent across instances."""
        r1 = ProviderResult(text="a", provider_name="p", model="m")
        r2 = ProviderResult(text="b", provider_name="p", model="m")
        # They should be equal but not the same object
        assert r1.metadata == r2.metadata
        assert r1.metadata is not r2.metadata


# ==========================================================================
# BaseProvider interface contract
# ==========================================================================


class TestBaseProviderContract:
    """Tests that BaseProvider enforces the abstract contract."""

    def test_cannot_instantiate_base_provider(self) -> None:
        """BaseProvider is abstract and cannot be instantiated directly."""
        with pytest.raises(TypeError):
            BaseProvider()  # type: ignore[abstract]

    def test_subclass_must_implement_name(self) -> None:
        """A subclass missing 'name' cannot be instantiated."""

        class BadProvider(BaseProvider):
            @property
            def is_paid(self) -> bool:
                return False

            @property
            def model_name(self) -> str:
                return "m"

            async def generate(self, prompt: str, **kwargs: Any) -> ProviderResult:
                return ProviderResult(text="", provider_name="", model="")

            async def check_availability(self) -> bool:
                return True

        with pytest.raises(TypeError):
            BadProvider()  # type: ignore[abstract]

    def test_subclass_must_implement_is_paid(self) -> None:
        """A subclass missing 'is_paid' cannot be instantiated."""

        class BadProvider(BaseProvider):
            @property
            def name(self) -> str:
                return "bad"

            @property
            def model_name(self) -> str:
                return "m"

            async def generate(self, prompt: str, **kwargs: Any) -> ProviderResult:
                return ProviderResult(text="", provider_name="", model="")

            async def check_availability(self) -> bool:
                return True

        with pytest.raises(TypeError):
            BadProvider()  # type: ignore[abstract]

    def test_subclass_must_implement_generate(self) -> None:
        """A subclass missing 'generate' cannot be instantiated."""

        class BadProvider(BaseProvider):
            @property
            def name(self) -> str:
                return "bad"

            @property
            def is_paid(self) -> bool:
                return False

            @property
            def model_name(self) -> str:
                return "m"

            async def check_availability(self) -> bool:
                return True

        with pytest.raises(TypeError):
            BadProvider()  # type: ignore[abstract]

    def test_subclass_must_implement_check_availability(self) -> None:
        """A subclass missing 'check_availability' cannot be instantiated."""

        class BadProvider(BaseProvider):
            @property
            def name(self) -> str:
                return "bad"

            @property
            def is_paid(self) -> bool:
                return False

            @property
            def model_name(self) -> str:
                return "m"

            async def generate(self, prompt: str, **kwargs: Any) -> ProviderResult:
                return ProviderResult(text="", provider_name="", model="")

        with pytest.raises(TypeError):
            BadProvider()  # type: ignore[abstract]

    def test_complete_subclass_instantiates(self) -> None:
        """A fully implemented subclass can be instantiated."""
        provider = FakeProvider()
        assert provider.name == "fake"
        assert provider.is_paid is False
        assert provider.model_name == "fake-model-1.0"


# ==========================================================================
# Async provider generation
# ==========================================================================


class TestAsyncGeneration:
    """Tests for async provider generation using a fake provider."""

    async def test_generate_returns_provider_result(self) -> None:
        provider = FakeProvider()
        result = await provider.generate("Hello world")
        assert isinstance(result, ProviderResult)

    async def test_generate_text_content(self) -> None:
        provider = FakeProvider(response_text="Test response")
        result = await provider.generate("What is the meaning of life?")
        assert result.text == "Test response"

    async def test_generate_includes_provider_name(self) -> None:
        provider = FakeProvider(name="my-provider")
        result = await provider.generate("prompt")
        assert result.provider_name == "my-provider"

    async def test_generate_includes_model(self) -> None:
        provider = FakeProvider(model="test-llm-v2")
        result = await provider.generate("prompt")
        assert result.model == "test-llm-v2"

    async def test_generate_includes_token_usage(self) -> None:
        provider = FakeProvider()
        result = await provider.generate("hello world")
        assert result.prompt_tokens is not None
        assert result.completion_tokens is not None
        assert result.total_tokens is not None

    async def test_generate_includes_latency(self) -> None:
        provider = FakeProvider()
        result = await provider.generate("hello")
        assert result.latency_ms is not None
        assert result.latency_ms > 0

    async def test_generate_includes_metadata(self) -> None:
        provider = FakeProvider()
        result = await provider.generate("hello")
        assert result.metadata == {"test": True}

    async def test_check_availability_true(self) -> None:
        provider = FakeProvider(available=True)
        assert await provider.check_availability() is True

    async def test_check_availability_false(self) -> None:
        provider = FakeProvider(available=False)
        assert await provider.check_availability() is False


# ==========================================================================
# HealthStatus enum
# ==========================================================================


class TestHealthStatus:
    """Tests for the HealthStatus enum."""

    def test_healthy_value(self) -> None:
        assert HealthStatus.HEALTHY.value == "healthy"

    def test_unhealthy_value(self) -> None:
        assert HealthStatus.UNHEALTHY.value == "unhealthy"

    def test_unavailable_value(self) -> None:
        assert HealthStatus.UNAVAILABLE.value == "unavailable"

    def test_all_statuses_exist(self) -> None:
        statuses = {s.value for s in HealthStatus}
        assert statuses == {"healthy", "unhealthy", "unavailable"}


# ==========================================================================
# CircuitState enum
# ==========================================================================


class TestCircuitState:
    """Tests for the CircuitState enum."""

    def test_closed_value(self) -> None:
        assert CircuitState.CLOSED.value == "closed"

    def test_open_value(self) -> None:
        assert CircuitState.OPEN.value == "open"

    def test_half_open_value(self) -> None:
        assert CircuitState.HALF_OPEN.value == "half_open"


# ==========================================================================
# CircuitBreaker
# ==========================================================================


class TestCircuitBreaker:
    """Tests for the CircuitBreaker."""

    def test_initial_state_is_closed(self) -> None:
        cb = CircuitBreaker(failure_threshold=3, cooldown_seconds=10.0)
        assert cb.state == CircuitState.CLOSED

    def test_initial_is_available(self) -> None:
        cb = CircuitBreaker(failure_threshold=3, cooldown_seconds=10.0)
        assert cb.is_available is True

    def test_initial_zero_failures(self) -> None:
        cb = CircuitBreaker(failure_threshold=3, cooldown_seconds=10.0)
        assert cb.consecutive_failures == 0

    def test_properties_reflect_config(self) -> None:
        cb = CircuitBreaker(failure_threshold=7, cooldown_seconds=30.0)
        assert cb.failure_threshold == 7
        assert cb.cooldown_seconds == 30.0

    def test_failure_below_threshold_stays_closed(self) -> None:
        cb = CircuitBreaker(failure_threshold=3, cooldown_seconds=10.0)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.CLOSED
        assert cb.is_available is True
        assert cb.consecutive_failures == 2

    def test_failure_at_threshold_opens_circuit(self) -> None:
        cb = CircuitBreaker(failure_threshold=3, cooldown_seconds=10.0)
        cb.record_failure()
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        assert cb.is_available is False
        assert cb.consecutive_failures == 3

    def test_open_circuit_not_available(self) -> None:
        cb = CircuitBreaker(failure_threshold=2, cooldown_seconds=999.0)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        assert cb.is_available is False

    def test_cooldown_transitions_to_half_open(self) -> None:
        """After cooldown, circuit should transition to HALF_OPEN."""
        cb = CircuitBreaker(failure_threshold=2, cooldown_seconds=10.0)

        # Control time: failures at t=100, check at t=200 (well past 10s cooldown)
        with patch("src.providers.health.time.monotonic") as mock_time:
            mock_time.return_value = 100.0
            cb.record_failure()
            cb.record_failure()
            assert cb.state == CircuitState.OPEN

            # Advance past cooldown
            mock_time.return_value = 200.0
            assert cb.state == CircuitState.HALF_OPEN
            assert cb.is_available is True

    def test_success_in_half_open_closes_circuit(self) -> None:
        cb = CircuitBreaker(failure_threshold=2, cooldown_seconds=10.0)

        with patch("src.providers.health.time.monotonic") as mock_time:
            mock_time.return_value = 100.0
            cb.record_failure()
            cb.record_failure()

            # Advance past cooldown
            mock_time.return_value = 200.0
            assert cb.state == CircuitState.HALF_OPEN

            cb.record_success()
            assert cb.state == CircuitState.CLOSED
            assert cb.consecutive_failures == 0
            assert cb.is_available is True

    def test_failure_in_half_open_reopens_circuit(self) -> None:
        cb = CircuitBreaker(failure_threshold=2, cooldown_seconds=10.0)

        with patch("src.providers.health.time.monotonic") as mock_time:
            mock_time.return_value = 100.0
            cb.record_failure()
            cb.record_failure()

            # Advance past cooldown to reach HALF_OPEN
            mock_time.return_value = 200.0
            assert cb.state == CircuitState.HALF_OPEN

            # Record another failure in HALF_OPEN — should reopen
            cb.record_failure()
            assert cb.state == CircuitState.OPEN
            assert cb.is_available is False

    def test_success_resets_failure_count(self) -> None:
        cb = CircuitBreaker(failure_threshold=5, cooldown_seconds=10.0)
        cb.record_failure()
        cb.record_failure()
        assert cb.consecutive_failures == 2

        cb.record_success()
        assert cb.consecutive_failures == 0
        assert cb.state == CircuitState.CLOSED

    def test_manual_reset(self) -> None:
        cb = CircuitBreaker(failure_threshold=2, cooldown_seconds=10.0)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

        cb.reset()
        assert cb.state == CircuitState.CLOSED
        assert cb.consecutive_failures == 0
        assert cb.is_available is True

    def test_invalid_failure_threshold(self) -> None:
        with pytest.raises(ValueError, match="failure_threshold"):
            CircuitBreaker(failure_threshold=0, cooldown_seconds=10.0)

    def test_invalid_cooldown_seconds(self) -> None:
        with pytest.raises(ValueError, match="cooldown_seconds"):
            CircuitBreaker(failure_threshold=3, cooldown_seconds=0)

    def test_negative_cooldown_seconds(self) -> None:
        with pytest.raises(ValueError, match="cooldown_seconds"):
            CircuitBreaker(failure_threshold=3, cooldown_seconds=-5.0)

    def test_single_failure_threshold(self) -> None:
        """A threshold of 1 should open on the first failure."""
        cb = CircuitBreaker(failure_threshold=1, cooldown_seconds=10.0)
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        assert cb.is_available is False

    def test_multiple_successes_keep_circuit_closed(self) -> None:
        cb = CircuitBreaker(failure_threshold=3, cooldown_seconds=10.0)
        for _ in range(10):
            cb.record_success()
        assert cb.state == CircuitState.CLOSED
        assert cb.consecutive_failures == 0

    def test_interleaved_failures_and_successes(self) -> None:
        """A success should reset the counter, preventing opening."""
        cb = CircuitBreaker(failure_threshold=3, cooldown_seconds=10.0)
        cb.record_failure()
        cb.record_failure()
        cb.record_success()  # resets counter
        cb.record_failure()
        cb.record_failure()
        # Only 2 consecutive failures, not 3
        assert cb.state == CircuitState.CLOSED
        assert cb.consecutive_failures == 2
