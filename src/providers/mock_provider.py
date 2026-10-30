"""Deterministic mock provider for testing and integration.

Implements the BaseProvider contract with zero network, zero API key,
and zero cost ($0 ceiling).
"""

from __future__ import annotations

from typing import Any

from src.providers.base import BaseProvider, ProviderResult
from src.providers.exceptions import ProviderError


class MockProvider(BaseProvider):
    """Deterministic mock provider implementing BaseProvider.

    Suitable for unit testing, integration tests, and validating
    LangGraph execution without calling real external APIs.
    """

    def __init__(
        self,
        name: str = "mock",
        model_name: str = "mock-model-v1",
        is_paid: bool = False,
        available: bool = True,
        custom_response: str | None = None,
        simulate_failure: bool = False,
    ) -> None:
        """Initialize mock provider.

        Args:
            name: Unique provider identifier.
            model_name: Identifier of the mock model.
            is_paid: Flag indicating paid status (default False).
            available: Whether the provider reports as available.
            custom_response: Optional fixed string to return upon generation.
            simulate_failure: If True, generate() raises ProviderError.
        """
        self._name = name
        self._model_name = model_name
        self._is_paid = is_paid
        self._available = available
        self._custom_response = custom_response
        self._simulate_failure = simulate_failure

    @property
    def name(self) -> str:
        """Unique identifier for this provider."""
        return self._name

    @property
    def is_paid(self) -> bool:
        """Whether this provider uses a paid API tier."""
        return self._is_paid

    @property
    def model_name(self) -> str:
        """The model identifier used by this provider."""
        return self._model_name

    async def generate(self, prompt: str, **kwargs: Any) -> ProviderResult:
        """Generate deterministic text response.

        Raises:
            ProviderError: When simulate_failure is True.
        """
        if self._simulate_failure:
            raise ProviderError("Simulated mock provider failure")

        text = self._custom_response or f"MOCK_RESPONSE: {prompt.strip()}"
        prompt_tokens = len(prompt.split())
        completion_tokens = len(text.split())

        return ProviderResult(
            text=text,
            provider_name=self._name,
            model=self._model_name,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            latency_ms=1.0,
            metadata={"mock": True},
        )

    async def check_availability(self) -> bool:
        """Lightweight availability check."""
        return self._available
