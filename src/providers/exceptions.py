"""
Agentic CRM — Provider exceptions.

Custom exception hierarchy for provider-related errors.
Keeps error handling clean and specific without relying on
generic exceptions.
"""

from __future__ import annotations


class ProviderError(Exception):
    """Base exception for all provider-related errors."""


class ProviderNotFoundError(ProviderError):
    """Raised when a requested provider is not registered."""

    def __init__(self, provider_name: str) -> None:
        self.provider_name = provider_name
        super().__init__(f"Provider not found: {provider_name!r}")


class ProviderUnavailableError(ProviderError):
    """Raised when a provider exists but is not currently available."""

    def __init__(self, provider_name: str, reason: str = "") -> None:
        self.provider_name = provider_name
        self.reason = reason
        msg = f"Provider unavailable: {provider_name!r}"
        if reason:
            msg += f" ({reason})"
        super().__init__(msg)


class PaidProviderError(ProviderError):
    """Raised when a paid provider is used while paid providers are disabled.

    This enforces the strict NO AUTOMATIC PAID API FALLBACK policy.
    """

    def __init__(self, provider_name: str) -> None:
        self.provider_name = provider_name
        super().__init__(
            f"Paid provider {provider_name!r} is not allowed. "
            "Paid providers are disabled by policy."
        )
