"""OpenRouter AI provider implementation.

Integrates with OpenRouter's OpenAI-compatible completions API, supporting
configurable model selection, health checks, and secure credential handling.
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Dict, Optional

import httpx

from src.config import get_settings
from src.providers.base import BaseProvider, ProviderResult
from src.providers.exceptions import (
    ProviderError,
    ProviderUnavailableError,
)

logger = logging.getLogger("agentic_crm.providers.openrouter")

DEFAULT_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_OPENROUTER_MODEL = "nvidia/nemotron-3.5-lightning:free"
APP_REFERER = "https://github.com/zubairrazzaq555-commits/agentic-crm"
APP_TITLE = "Agentic CRM"


class OpenRouterProvider(BaseProvider):
    """OpenRouter provider conforming to BaseProvider interface.

    Communicates with OpenRouter via HTTP POST to /chat/completions.
    Credentials are read from environment or config, never logged or exposed.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        name: str = "openrouter",
        timeout: float = 30.0,
        is_paid: bool = False,
        http_client: Optional[httpx.AsyncClient] = None,
    ) -> None:
        """Initialize OpenRouter provider.

        Args:
            api_key: OpenRouter API key. If omitted, resolved from OPENROUTER_API_KEY
                     env var or application settings.
            model: Model identifier string (e.g. 'nvidia/nemotron-3.5-lightning:free').
                   If omitted, resolved from OPENROUTER_MODEL or default free model.
            base_url: OpenRouter API base URL (default: https://openrouter.ai/api/v1).
            name: Provider name identifier for ProviderManager (default: 'openrouter').
            timeout: HTTP request timeout in seconds.
            is_paid: Flag indicating paid tier. Defaults to False (free models only).
            http_client: Optional injected httpx.AsyncClient (e.g. for mocked testing).
        """
        self._name = name
        self._is_paid = is_paid
        self._timeout = timeout

        settings = get_settings()

        # Resolve credentials safely
        if api_key is not None:
            self._api_key = api_key
        else:
            self._api_key = (
                os.environ.get("OPENROUTER_API_KEY")
                or settings.openrouter_api_key
            )

        # Resolve model
        self._model = (
            model
            or os.environ.get("OPENROUTER_MODEL")
            or getattr(settings, "openrouter_model", DEFAULT_OPENROUTER_MODEL)
            or DEFAULT_OPENROUTER_MODEL
        )

        # Resolve base URL
        resolved_url = (
            base_url
            or os.environ.get("OPENROUTER_BASE_URL")
            or getattr(settings, "openrouter_base_url", DEFAULT_OPENROUTER_BASE_URL)
            or DEFAULT_OPENROUTER_BASE_URL
        )
        self._base_url = resolved_url.rstrip("/")

        self._injected_client = http_client
        self._owned_client: Optional[httpx.AsyncClient] = None

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
        """The default model identifier used by this provider."""
        return self._model

    @property
    def base_url(self) -> str:
        """OpenRouter API base URL."""
        return self._base_url

    def _get_headers(self) -> Dict[str, str]:
        """Construct standard HTTP headers.

        Raises:
            ProviderUnavailableError: If API key is not configured.
        """
        if not self._api_key:
            raise ProviderUnavailableError(self._name, "API key is not configured")

        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": APP_REFERER,
            "X-Title": APP_TITLE,
        }

    def _get_client(self) -> httpx.AsyncClient:
        """Return the active HTTP client."""
        if self._injected_client is not None:
            return self._injected_client
        if self._owned_client is None or self._owned_client.is_closed:
            self._owned_client = httpx.AsyncClient(timeout=self._timeout)
        return self._owned_client

    async def close(self) -> None:
        """Close internally managed HTTP client if open."""
        if self._owned_client is not None and not self._owned_client.is_closed:
            await self._owned_client.aclose()
            self._owned_client = None

    async def __aenter__(self) -> OpenRouterProvider:
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.close()

    def _sanitize_error_text(self, text: str) -> str:
        """Strip raw API key if present in error message text."""
        if self._api_key and self._api_key in text:
            return text.replace(self._api_key, "[REDACTED_API_KEY]")
        return text

    async def generate(self, prompt: str, **kwargs: Any) -> ProviderResult:
        """Generate text completion from prompt via OpenRouter.

        Args:
            prompt: Text prompt to submit.
            **kwargs: Generation overrides (e.g. model, temperature, max_tokens).

        Returns:
            Standardized ProviderResult.

        Raises:
            ProviderUnavailableError: If provider API key is not configured.
            ProviderError: On HTTP error, auth failure, timeout, or invalid response.
        """
        headers = self._get_headers()
        client = self._get_client()

        target_model = kwargs.get("model", self._model)
        temperature = kwargs.get("temperature", 0.7)
        max_tokens = kwargs.get("max_tokens", 1000)

        # Support optional custom messages or format from single prompt
        messages = kwargs.get("messages")
        if not messages:
            messages = [{"role": "user", "content": prompt}]

        payload = {
            "model": target_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        url = f"{self._base_url}/chat/completions"
        start_time = time.perf_counter()

        try:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            safe_body = self._sanitize_error_text(exc.response.text)
            if status in (401, 403):
                raise ProviderError(
                    f"OpenRouter authentication failed (HTTP {status}): {safe_body}"
                ) from exc
            if status == 429:
                raise ProviderError(
                    f"OpenRouter rate limit exceeded (HTTP 429): {safe_body}"
                ) from exc
            raise ProviderError(
                f"OpenRouter API error (HTTP {status}): {safe_body}"
            ) from exc
        except httpx.RequestError as exc:
            safe_err = self._sanitize_error_text(str(exc))
            raise ProviderError(
                f"OpenRouter network request failed ({type(exc).__name__}): {safe_err}"
            ) from exc
        except Exception as exc:
            safe_err = self._sanitize_error_text(str(exc))
            raise ProviderError(f"OpenRouter unexpected failure: {safe_err}") from exc

        latency_ms = (time.perf_counter() - start_time) * 1000.0

        try:
            data = response.json()
            choices = data.get("choices", [])
            if not choices:
                raise ProviderError("OpenRouter response contains no completion choices")

            choice = choices[0]
            msg = choice.get("message", {})
            text = msg.get("content") or ""
            # Fallback to reasoning if content is empty (e.g. reasoning models)
            if not text and msg.get("reasoning"):
                text = msg.get("reasoning")

            usage = data.get("usage") or {}
            prompt_tokens = usage.get("prompt_tokens")
            completion_tokens = usage.get("completion_tokens")
            total_tokens = usage.get("total_tokens")

            return ProviderResult(
                text=text,
                provider_name=self._name,
                model=data.get("model", target_model),
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                latency_ms=latency_ms,
                metadata={
                    "id": data.get("id"),
                    "finish_reason": choice.get("finish_reason"),
                    "raw_message": msg,
                },
            )
        except json.JSONDecodeError as exc:
            raise ProviderError(f"Failed to decode OpenRouter JSON response: {exc}") from exc
        except KeyError as exc:
            raise ProviderError(f"Missing expected field in OpenRouter response: {exc}") from exc

    async def check_availability(self) -> bool:
        """Lightweight check verifying OpenRouter availability and credentials.

        Returns:
            True if OpenRouter endpoint responds successfully; False otherwise.
        """
        if not self._api_key:
            return False

        try:
            headers = self._get_headers()
            client = self._get_client()
            url = f"{self._base_url}/auth/key"
            response = await client.get(url, headers=headers)
            return response.status_code == 200
        except Exception:
            # Fallback check against models endpoint if auth/key is unavailable
            try:
                headers = self._get_headers()
                client = self._get_client()
                url = f"{self._base_url}/models"
                response = await client.get(url, headers=headers)
                return response.status_code == 200
            except Exception:
                return False
