"""
Agentic CRM — Base provider interface and provider result.

Defines the abstract contract that all future AI providers must
implement (BaseProvider) and a standardized result structure
(ProviderResult) for provider responses.

This module is provider-agnostic: no Gemini-, Groq-, Ollama-,
or OpenAI-specific logic belongs here.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Provider result structure
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ProviderResult:
    """Standardized result from a provider generation call.

    All providers return this structure so that downstream consumers
    can work with a uniform API regardless of which provider was used.

    Required fields:
        text:          The generated text.
        provider_name: Identifier of the provider that produced this result.
        model:         The specific model used for generation.

    Optional fields:
        prompt_tokens:     Number of tokens in the prompt (if reported).
        completion_tokens: Number of tokens in the completion (if reported).
        total_tokens:      Total token count (if reported).
        latency_ms:        Round-trip latency in milliseconds (if measured).
        metadata:          Arbitrary provider-specific metadata.

    Not every provider exposes token usage or latency.  These fields
    default to ``None`` when the provider does not report them.
    """

    text: str
    provider_name: str
    model: str

    # Optional token usage (not all providers report these)
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None

    # Optional timing
    latency_ms: float | None = None

    # Optional provider-specific metadata
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Base provider interface
# ---------------------------------------------------------------------------


class BaseProvider(abc.ABC):
    """Abstract base class for all AI providers.

    Every concrete provider (Gemini, Groq, Ollama, etc.) must subclass
    this and implement all abstract methods.  The interface is intentionally
    minimal — it defines only the contract needed by the ProviderManager
    and future Model Router.

    Provider-specific configuration (API keys, endpoints, model lists)
    belongs in each concrete subclass, NOT here.

    Attributes:
        name:    A unique identifier string for this provider instance.
        is_paid: Whether this provider uses a paid API.  The ProviderManager
                 will refuse to auto-select providers where ``is_paid is True``
                 unless paid providers are explicitly enabled.
    """

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Unique identifier for this provider (e.g. 'gemini', 'ollama')."""

    @property
    @abc.abstractmethod
    def is_paid(self) -> bool:
        """Whether this provider uses a paid API tier.

        Providers returning True here will be rejected by the
        ProviderManager when ``allow_paid=False`` (the default).
        """

    @property
    @abc.abstractmethod
    def model_name(self) -> str:
        """The model identifier used by this provider (e.g. 'phi3:mini')."""

    @abc.abstractmethod
    async def generate(self, prompt: str, **kwargs: Any) -> ProviderResult:
        """Generate text from a prompt.

        This is the core method that every provider must implement.

        Args:
            prompt:  The text prompt to send to the model.
            **kwargs: Provider-specific generation parameters
                      (temperature, max_tokens, etc.).

        Returns:
            A ProviderResult containing the generated text and metadata.

        Raises:
            ProviderError: On any provider-side failure (network, auth,
                           rate-limit, etc.).
        """

    @abc.abstractmethod
    async def check_availability(self) -> bool:
        """Check whether the provider is currently reachable and usable.

        This should be a lightweight check (e.g. a health endpoint,
        a simple ping, or an API key validation).

        Returns:
            True if the provider is available, False otherwise.
        """
