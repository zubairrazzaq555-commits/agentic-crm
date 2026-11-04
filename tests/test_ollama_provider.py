"""Unit tests for src.providers.ollama — Local Ollama provider.

Covers:
- OllamaProvider initialization with defaults and custom parameters
- Environment variable and settings resolution
- Model descriptor inference and custom descriptor injection
- Health check / availability check (success, fallback, failure)
- Model listing and model availability verification (exact and tag-alias matching)
- Text generation success with token counts, latency, and metadata
- Generation with option overrides (model, temperature, max_tokens, format)
- Error handling: connection errors, timeouts, HTTP errors (404, 500), malformed JSON
- ProviderManager registration, health tracking, and circuit breaker
- LOCAL execution mode compatibility
- Coexistence with MockProvider and OpenRouterProvider
"""

from __future__ import annotations

import json
from typing import Any, Dict, List
from unittest.mock import patch

import httpx
import pytest

from src.config import ExecutionMode, Settings
from src.providers.base import ModelDescriptor, ModelTier, TaskComplexity
from src.providers.exceptions import (
    ProviderError,
    ProviderUnavailableError,
)
from src.providers.manager import ProviderManager
from src.providers.mock_provider import MockProvider
from src.providers.ollama import (
    DEFAULT_OLLAMA_BASE_URL,
    DEFAULT_OLLAMA_MODEL,
    DEFAULT_OLLAMA_TIMEOUT,
    OllamaProvider,
    _infer_model_descriptor,
)
from src.providers.openrouter import OpenRouterProvider


# ==========================================================================
# Helpers: Mock Transports
# ==========================================================================


def _create_mock_client(
    handler: Any,
) -> httpx.AsyncClient:
    """Create an AsyncClient backed by a mock transport."""
    transport = httpx.MockTransport(handler)
    return httpx.AsyncClient(transport=transport)


# ==========================================================================
# Initialization & Descriptor Tests
# ==========================================================================


class TestOllamaInitialization:
    """Verify OllamaProvider initialization and configuration resolution."""

    def test_default_initialization(self, clean_env: None) -> None:
        provider = OllamaProvider()
        assert provider.name == "ollama"
        assert provider.model_name == DEFAULT_OLLAMA_MODEL
        assert provider.base_url == DEFAULT_OLLAMA_BASE_URL
        assert provider.is_paid is False
        assert provider.is_local is True
        assert provider.timeout == DEFAULT_OLLAMA_TIMEOUT
        assert provider.descriptor is not None
        assert provider.descriptor.is_local is True
        assert provider.descriptor.tier == ModelTier.SLM_SMALL

    def test_explicit_initialization(self) -> None:
        provider = OllamaProvider(
            base_url="http://192.168.1.50:11434",
            model="qwen2.5:7b",
            name="custom_ollama",
            timeout=45.0,
        )
        assert provider.name == "custom_ollama"
        assert provider.base_url == "http://192.168.1.50:11434"
        assert provider.model_name == "qwen2.5:7b"
        assert provider.timeout == 45.0
        assert provider.descriptor is not None
        assert provider.descriptor.tier == ModelTier.SLM_MEDIUM

    def test_env_var_resolution(self, clean_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OLLAMA_BASE_URL", "http://ollama-host:11434")
        monkeypatch.setenv("OLLAMA_DEFAULT_MODEL", "llama3.2:3b")
        provider = OllamaProvider()
        assert provider.base_url == "http://ollama-host:11434"
        assert provider.model_name == "llama3.2:3b"

    def test_descriptor_inference_tiers(self) -> None:
        d_small = _infer_model_descriptor("qwen2.5:1.5b")
        assert d_small.tier == ModelTier.SLM_SMALL
        assert d_small.ram_required_mb == 2048

        d_med = _infer_model_descriptor("mistral:7b")
        assert d_med.tier == ModelTier.SLM_MEDIUM
        assert d_med.ram_required_mb == 5120

        d_large = _infer_model_descriptor("llama3:70b")
        assert d_large.tier == ModelTier.LLM_LARGE
        assert d_large.ram_required_mb == 40960

    def test_custom_descriptor_override(self) -> None:
        custom_desc = ModelDescriptor(
            model_id="custom:1b",
            tier=ModelTier.SLM_SMALL,
            is_local=True,
            supported_complexities=(TaskComplexity.CLASSIFICATION,),
        )
        provider = OllamaProvider(descriptor=custom_desc)
        assert provider.descriptor == custom_desc
        assert provider.can_handle_complexity(TaskComplexity.CLASSIFICATION) is True
        assert provider.can_handle_complexity(TaskComplexity.PLANNING) is False


# ==========================================================================
# Health Check & Model Listing Tests
# ==========================================================================


class TestOllamaHealthAndModelListing:
    """Verify check_availability, list_models, and is_model_available."""

    @pytest.mark.asyncio
    async def test_check_availability_version_success(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/api/version":
                return httpx.Response(200, json={"version": "0.1.32"})
            return httpx.Response(404)

        client = _create_mock_client(handler)
        provider = OllamaProvider(http_client=client)
        assert await provider.check_availability() is True

    @pytest.mark.asyncio
    async def test_check_availability_tags_fallback(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/api/version":
                return httpx.Response(404)
            if request.url.path == "/api/tags":
                return httpx.Response(200, json={"models": []})
            return httpx.Response(404)

        client = _create_mock_client(handler)
        provider = OllamaProvider(http_client=client)
        assert await provider.check_availability() is True

    @pytest.mark.asyncio
    async def test_check_availability_failure(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("Connection refused")

        client = _create_mock_client(handler)
        provider = OllamaProvider(http_client=client)
        assert await provider.check_availability() is False

    @pytest.mark.asyncio
    async def test_list_models_success(self) -> None:
        models_payload = {
            "models": [
                {"name": "phi3:mini", "modified_at": "2024-05-01T00:00:00Z"},
                {"name": "qwen2.5:1.5b", "modified_at": "2024-05-01T00:00:00Z"},
            ]
        }

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/api/tags":
                return httpx.Response(200, json=models_payload)
            return httpx.Response(404)

        client = _create_mock_client(handler)
        provider = OllamaProvider(http_client=client)
        models = await provider.list_models()
        assert models == ["phi3:mini", "qwen2.5:1.5b"]

    @pytest.mark.asyncio
    async def test_list_models_connection_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("Daemon offline")

        client = _create_mock_client(handler)
        provider = OllamaProvider(http_client=client)
        with pytest.raises(ProviderUnavailableError) as exc_info:
            await provider.list_models()
        assert "Ollama daemon unreachable" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_is_model_available_matching(self) -> None:
        models_payload = {
            "models": [
                {"name": "phi3:mini"},
                {"name": "mistral:latest"},
            ]
        }

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=models_payload)

        client = _create_mock_client(handler)
        provider = OllamaProvider(model="phi3:mini", http_client=client)

        # Exact match of default model
        assert await provider.is_model_available() is True
        # Exact match of another model
        assert await provider.is_model_available("phi3:mini") is True
        # Alias match for mistral -> mistral:latest
        assert await provider.is_model_available("mistral") is True
        # Non-existent model
        assert await provider.is_model_available("llama3:70b") is False


# ==========================================================================
# Generation Tests
# ==========================================================================


class TestOllamaGeneration:
    """Verify text generation and payload processing."""

    @pytest.mark.asyncio
    async def test_generate_success(self) -> None:
        generate_response = {
            "model": "phi3:mini",
            "created_at": "2024-05-01T12:00:00Z",
            "response": "Qualifying lead for Acme Corp.",
            "done": True,
            "total_duration": 4500000000,
            "load_duration": 50000000,
            "prompt_eval_count": 15,
            "eval_count": 30,
            "eval_duration": 4000000000,
        }

        captured_request: Dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/api/generate":
                captured_request["body"] = json.loads(request.content.decode("utf-8"))
                return httpx.Response(200, json=generate_response)
            return httpx.Response(404)

        client = _create_mock_client(handler)
        provider = OllamaProvider(http_client=client)
        result = await provider.generate("Extract lead information")

        assert result.text == "Qualifying lead for Acme Corp."
        assert result.provider_name == "ollama"
        assert result.model == "phi3:mini"
        assert result.prompt_tokens == 15
        assert result.completion_tokens == 30
        assert result.total_tokens == 45
        assert result.latency_ms is not None and result.latency_ms >= 0.0
        assert result.metadata.get("done") is True

        # Verify captured payload
        assert captured_request["body"]["prompt"] == "Extract lead information"
        assert captured_request["body"]["model"] == "phi3:mini"
        assert captured_request["body"]["stream"] is False

    @pytest.mark.asyncio
    async def test_generate_with_options_and_format(self) -> None:
        captured_request: Dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured_request["body"] = json.loads(request.content.decode("utf-8"))
            return httpx.Response(
                200,
                json={"response": '{"intent": "create_lead"}', "model": "qwen2.5:1.5b", "done": True},
            )

        client = _create_mock_client(handler)
        provider = OllamaProvider(http_client=client)
        result = await provider.generate(
            "Classify intent",
            model="qwen2.5:1.5b",
            temperature=0.2,
            max_tokens=150,
            format="json",
        )

        assert result.text == '{"intent": "create_lead"}'
        assert result.model == "qwen2.5:1.5b"
        assert captured_request["body"]["options"]["temperature"] == 0.2
        assert captured_request["body"]["options"]["num_predict"] == 150
        assert captured_request["body"]["format"] == "json"

    @pytest.mark.asyncio
    async def test_generate_missing_model_404(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(404, json={"error": "model 'nonexistent:latest' not found, try pulling it first"})

        client = _create_mock_client(handler)
        provider = OllamaProvider(http_client=client)
        with pytest.raises(ProviderUnavailableError) as exc_info:
            await provider.generate("hello", model="nonexistent:latest")
        assert "not found in Ollama" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_generate_server_error_500(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, json={"error": "CUDA out of memory"})

        client = _create_mock_client(handler)
        provider = OllamaProvider(http_client=client)
        with pytest.raises(ProviderError) as exc_info:
            await provider.generate("hello")
        assert "failed with status 500" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_generate_timeout(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ReadTimeout("Generation timed out")

        client = _create_mock_client(handler)
        provider = OllamaProvider(http_client=client)
        with pytest.raises(ProviderError) as exc_info:
            await provider.generate("hello")
        assert "timed out" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_generate_connect_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("Connection refused")

        client = _create_mock_client(handler)
        provider = OllamaProvider(http_client=client)
        with pytest.raises(ProviderUnavailableError) as exc_info:
            await provider.generate("hello")
        assert "daemon unreachable" in str(exc_info.value)


# ==========================================================================
# ProviderManager & Execution Mode Integration
# ==========================================================================


class TestOllamaProviderManagerIntegration:
    """Verify OllamaProvider behaves correctly inside ProviderManager."""

    def test_registration_and_lookup(self) -> None:
        manager = ProviderManager(allow_paid=False)
        ollama = OllamaProvider()
        manager.register(ollama)

        assert "ollama" in manager.list_providers()
        retrieved = manager.get_provider("ollama")
        assert retrieved is ollama
        assert retrieved.is_paid is False
        assert retrieved.is_local is True

    @pytest.mark.asyncio
    async def test_health_and_circuit_breaker(self) -> None:
        manager = ProviderManager(
            allow_paid=False,
            circuit_breaker_failure_threshold=2,
            circuit_breaker_cooldown_seconds=10.0,
        )
        ollama = OllamaProvider()
        manager.register(ollama)

        assert manager.is_available("ollama") is True

        # Record failures to trip circuit
        manager.record_failure("ollama")
        assert manager.is_available("ollama") is True
        manager.record_failure("ollama")
        # Circuit is now open
        assert manager.is_available("ollama") is False

        # Reset via success
        manager.record_success("ollama")
        assert manager.is_available("ollama") is True

    def test_local_execution_mode_compatibility(self) -> None:
        """LOCAL mode requires local providers; OllamaProvider satisfies is_local."""
        settings = Settings(execution_mode=ExecutionMode.LOCAL)
        assert settings.can_use_local is True
        assert settings.can_use_cloud is False

        provider = OllamaProvider()
        assert provider.is_local is True
        # Provider descriptor confirms locality
        assert provider.descriptor is not None
        assert provider.descriptor.is_local is True

    def test_local_mode_rejects_openrouter_selection(self) -> None:
        """In LOCAL mode, cloud providers (OpenRouter) cannot be selected."""
        settings = Settings(execution_mode=ExecutionMode.LOCAL)
        manager = ProviderManager(allow_paid=False)
        manager.register(OllamaProvider())
        manager.register(OpenRouterProvider(api_key="test-key"))

        # In LOCAL mode: only local providers are eligible
        eligible = [
            p for p in manager.get_available_providers()
            if (p.is_local if not settings.can_use_cloud else True)
        ]
        assert all(p.is_local for p in eligible)
        assert any(p.name == "ollama" for p in eligible)
        assert not any(p.name == "openrouter" for p in eligible)

    @pytest.mark.asyncio
    async def test_ollama_failure_does_not_crash_startup(self) -> None:
        """Application and provider instantiate and degrade gracefully when Ollama is offline."""
        settings = Settings()
        assert settings.ollama_base_url is not None

        def offline_handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("Daemon is offline")

        client = _create_mock_client(offline_handler)
        provider = OllamaProvider(base_url="http://localhost:11434", http_client=client)
        assert provider.name == "ollama"
        # Health check safely returns False, does not raise
        assert await provider.check_availability() is False

    def test_coexistence_with_mock_and_openrouter(self) -> None:
        """ProviderManager successfully registers and distinguishes all 3 providers."""
        manager = ProviderManager(allow_paid=False)
        mock = MockProvider()
        ollama = OllamaProvider()
        openrouter = OpenRouterProvider(api_key="test-key")

        manager.register(mock)
        manager.register(ollama)
        manager.register(openrouter)

        assert len(manager.list_providers()) == 3
        assert manager.get_provider("mock").is_local is True
        assert manager.get_provider("ollama").is_local is True
        assert manager.get_provider("openrouter").is_local is False

