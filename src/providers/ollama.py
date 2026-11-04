"""Ollama local AI provider implementation.

Integrates with Ollama's local HTTP API (/api/generate, /api/tags), supporting
local SLM execution, health/availability checks, installed model detection,
configurable timeouts, and zero-cost local inference.
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

import httpx

from src.config import get_settings
from src.providers.base import (
    BaseProvider,
    ModelDescriptor,
    ModelTier,
    ProviderResult,
    TaskComplexity,
)
from src.providers.exceptions import (
    ProviderError,
    ProviderUnavailableError,
)

logger = logging.getLogger("agentic_crm.providers.ollama")

DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_OLLAMA_MODEL = "phi3:mini"
DEFAULT_OLLAMA_TIMEOUT = 30.0


def _infer_model_descriptor(model_id: str) -> ModelDescriptor:
    """Infer sensible model tier and RAM estimation from model name."""
    lower = model_id.lower()
    if any(tag in lower for tag in ("70b", "65b")):
        tier = ModelTier.LLM_LARGE
        ram_mb = 40960
        complexities = tuple(TaskComplexity)
    elif any(tag in lower for tag in ("7b", "8b", "13b", "14b", "medium")):
        tier = ModelTier.SLM_MEDIUM
        ram_mb = 5120
        complexities = (
            TaskComplexity.DETERMINISTIC,
            TaskComplexity.EXTRACTION,
            TaskComplexity.CLASSIFICATION,
            TaskComplexity.REASONING,
        )
    else:
        # Default ~1B-3.8B SLMs (e.g. phi3:mini, qwen2.5:1.5b, llama3.2:1b)
        tier = ModelTier.SLM_SMALL
        ram_mb = 2048
        complexities = (
            TaskComplexity.DETERMINISTIC,
            TaskComplexity.EXTRACTION,
            TaskComplexity.CLASSIFICATION,
            TaskComplexity.REASONING,
        )

    return ModelDescriptor(
        model_id=model_id,
        tier=tier,
        is_local=True,
        context_window=4096,
        supports_structured_output=True,
        ram_required_mb=ram_mb,
        cost_per_1k_tokens=0.0,
        supported_complexities=complexities,
        metadata={"is_local": True, "provider": "ollama"},
    )


class OllamaProvider(BaseProvider):
    """Local Ollama provider conforming to BaseProvider interface.

    Communicates with a locally running Ollama daemon via HTTP POST /api/generate
    and GET /api/tags for model inspection and health verification.

    Zero external network calls, zero API keys, and $0 cost.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        name: str = "ollama",
        timeout: Optional[float] = None,
        http_client: Optional[httpx.AsyncClient] = None,
        descriptor: Optional[ModelDescriptor] = None,
    ) -> None:
        """Initialize Ollama provider.

        Args:
            base_url: Ollama API base URL (default: http://localhost:11434).
            model: Model identifier string (e.g. 'phi3:mini').
                   If omitted, resolved from OLLAMA_DEFAULT_MODEL or settings.
            name: Provider name identifier for ProviderManager (default: 'ollama').
            timeout: HTTP request timeout in seconds.
            http_client: Optional injected httpx.AsyncClient (e.g. for mocked testing).
            descriptor: Optional model descriptor override.
        """
        self._name = name
        settings = get_settings()

        # Resolve base URL
        resolved_url = (
            base_url
            or os.environ.get("OLLAMA_BASE_URL")
            or getattr(settings, "ollama_base_url", DEFAULT_OLLAMA_BASE_URL)
            or DEFAULT_OLLAMA_BASE_URL
        )
        self._base_url = resolved_url.rstrip("/")

        # Resolve model
        self._model = (
            model
            or os.environ.get("OLLAMA_DEFAULT_MODEL")
            or getattr(settings, "ollama_default_model", DEFAULT_OLLAMA_MODEL)
            or DEFAULT_OLLAMA_MODEL
        )

        # Resolve timeout
        if timeout is not None:
            self._timeout = timeout
        else:
            self._timeout = getattr(settings, "ollama_timeout", DEFAULT_OLLAMA_TIMEOUT)

        self._injected_client = http_client
        self._owned_client: Optional[httpx.AsyncClient] = None
        self._descriptor = descriptor or _infer_model_descriptor(self._model)

    @property
    def name(self) -> str:
        """Unique identifier for this provider."""
        return self._name

    @property
    def is_paid(self) -> bool:
        """Whether this provider uses a paid API tier. Always False for local Ollama."""
        return False

    @property
    def model_name(self) -> str:
        """The default model identifier used by this provider."""
        return self._model

    @property
    def descriptor(self) -> Optional[ModelDescriptor]:
        """Model capability and resource descriptor for this provider."""
        return self._descriptor

    @property
    def base_url(self) -> str:
        """Ollama API base URL."""
        return self._base_url

    @property
    def timeout(self) -> float:
        """HTTP request timeout in seconds."""
        return self._timeout

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

    async def __aenter__(self) -> OllamaProvider:
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.close()

    async def check_availability(self) -> bool:
        """Lightweight health check verifying Ollama server reachability.

        Queries GET /api/version or GET /api/tags to verify daemon status.

        Returns:
            True if Ollama daemon responds with HTTP 200; False otherwise.
        """
        client = self._get_client()
        for endpoint in ("/api/version", "/api/tags"):
            try:
                response = await client.get(f"{self._base_url}{endpoint}")
                if response.status_code == 200:
                    return True
            except Exception:
                continue
        return False

    async def list_models(self) -> List[str]:
        """List all model names installed and available in local Ollama.

        Returns:
            List of model names (e.g. ['phi3:mini', 'qwen2.5:1.5b']).

        Raises:
            ProviderUnavailableError: If Ollama daemon is unreachable.
            ProviderError: If the response is malformed or invalid.
        """
        client = self._get_client()
        url = f"{self._base_url}/api/tags"
        try:
            response = await client.get(url)
        except (httpx.ConnectError, httpx.NetworkError) as exc:
            raise ProviderUnavailableError(
                self._name, f"Ollama daemon unreachable at {self._base_url}: {exc}"
            ) from exc
        except httpx.TimeoutException as exc:
            raise ProviderUnavailableError(
                self._name, f"Ollama connection timed out at {self._base_url}: {exc}"
            ) from exc
        except Exception as exc:
            raise ProviderUnavailableError(
                self._name, f"Failed to connect to Ollama at {self._base_url}: {exc}"
            ) from exc

        if response.status_code != 200:
            raise ProviderError(
                f"Ollama list_models returned unexpected status {response.status_code}: {response.text}"
            )

        try:
            data = response.json()
            models_data = data.get("models", [])
            return [m.get("name") for m in models_data if m.get("name")]
        except Exception as exc:
            raise ProviderError(f"Failed to parse Ollama models list response: {exc}") from exc

    async def is_model_available(self, model_name: Optional[str] = None) -> bool:
        """Check whether a specific model is pulled and available locally.

        Args:
            model_name: Model identifier to verify. If omitted, checks default model.

        Returns:
            True if model is available locally; False otherwise.
        """
        target = (model_name or self._model).strip().lower()
        try:
            installed = await self.list_models()
            installed_lower = [m.lower() for m in installed]
            if target in installed_lower:
                return True
            # Match 'model:latest' if user checked bare 'model'
            if ":" not in target and f"{target}:latest" in installed_lower:
                return True
            return False
        except Exception:
            return False

    async def generate(self, prompt: str, **kwargs: Any) -> ProviderResult:
        """Generate text completion from prompt via local Ollama.

        Args:
            prompt: Text prompt to submit.
            **kwargs: Generation overrides (e.g. model, temperature, max_tokens, format).

        Returns:
            Standardized ProviderResult.

        Raises:
            ProviderUnavailableError: If Ollama daemon is unreachable or model is not pulled.
            ProviderError: On timeout, invalid response format, or generation error.
        """
        client = self._get_client()
        target_model = kwargs.get("model", self._model)

        payload: Dict[str, Any] = {
            "model": target_model,
            "prompt": prompt,
            "stream": False,
        }

        options: Dict[str, Any] = {}
        if "temperature" in kwargs:
            options["temperature"] = kwargs["temperature"]
        if "max_tokens" in kwargs:
            options["num_predict"] = kwargs["max_tokens"]
        elif "num_predict" in kwargs:
            options["num_predict"] = kwargs["num_predict"]
        if "top_p" in kwargs:
            options["top_p"] = kwargs["top_p"]

        if options:
            payload["options"] = options

        if "format" in kwargs:
            payload["format"] = kwargs["format"]

        url = f"{self._base_url}/api/generate"
        start_time = time.perf_counter()

        try:
            response = await client.post(url, json=payload)
        except (httpx.ConnectError, httpx.NetworkError) as exc:
            raise ProviderUnavailableError(
                self._name, f"Ollama daemon unreachable at {self._base_url}: {exc}"
            ) from exc
        except httpx.TimeoutException as exc:
            raise ProviderError(
                f"Ollama request timed out after {self._timeout}s: {exc}"
            ) from exc
        except httpx.RequestError as exc:
            raise ProviderUnavailableError(
                self._name, f"Ollama HTTP request error: {exc}"
            ) from exc

        latency_ms = (time.perf_counter() - start_time) * 1000

        # Handle 404: Model not found locally
        if response.status_code == 404:
            try:
                err_data = response.json()
                err_msg = err_data.get("error", response.text)
            except Exception:
                err_msg = response.text
            raise ProviderUnavailableError(
                self._name, f"Model '{target_model}' not found in Ollama: {err_msg}"
            )

        if response.status_code != 200:
            try:
                err_data = response.json()
                err_msg = err_data.get("error", response.text)
            except Exception:
                err_msg = response.text
            raise ProviderError(
                f"Ollama generation failed with status {response.status_code}: {err_msg}"
            )

        try:
            data = response.json()
        except json.JSONDecodeError as exc:
            raise ProviderError(f"Failed to decode Ollama JSON response: {exc}") from exc

        text = data.get("response", "")
        prompt_tokens = data.get("prompt_eval_count")
        completion_tokens = data.get("eval_count")
        total_tokens = None
        if prompt_tokens is not None or completion_tokens is not None:
            total_tokens = (prompt_tokens or 0) + (completion_tokens or 0)

        return ProviderResult(
            text=text,
            provider_name=self._name,
            model=data.get("model", target_model),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            latency_ms=latency_ms,
            metadata={
                "done": data.get("done", True),
                "total_duration": data.get("total_duration"),
                "load_duration": data.get("load_duration"),
                "eval_duration": data.get("eval_duration"),
            },
        )
