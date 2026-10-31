"""Focused tests for OpenRouterProvider (Phase 5, Milestone 5.1)."""

import httpx
import pytest

from src.providers.exceptions import (
    ProviderError,
    ProviderUnavailableError,
)
from src.providers.manager import ProviderManager
from src.providers.openrouter import (
    APP_REFERER,
    APP_TITLE,
    DEFAULT_OPENROUTER_BASE_URL,
    DEFAULT_OPENROUTER_MODEL,
    OpenRouterProvider,
)


# =====================================================================
# 1. Initialization and Configuration Tests
# =====================================================================


def test_openrouter_initialization_explicit() -> None:
    provider = OpenRouterProvider(
        api_key="test-key-123",
        model="custom/test-model",
        base_url="https://custom.openrouter.test/v1",
        name="openrouter_test",
        is_paid=False,
    )
    assert provider.name == "openrouter_test"
    assert provider.model_name == "custom/test-model"
    assert provider.base_url == "https://custom.openrouter.test/v1"
    assert provider.is_paid is False


def test_openrouter_initialization_defaults(monkeypatch) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_MODEL", raising=False)
    monkeypatch.delenv("OPENROUTER_BASE_URL", raising=False)

    provider = OpenRouterProvider(api_key="some-key")
    assert provider.name == "openrouter"
    assert provider.model_name == DEFAULT_OPENROUTER_MODEL
    assert provider.base_url == DEFAULT_OPENROUTER_BASE_URL
    assert provider.is_paid is False


def test_openrouter_env_resolution(monkeypatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "env-secret-key")
    monkeypatch.setenv("OPENROUTER_MODEL", "env/test-model:free")
    monkeypatch.setenv("OPENROUTER_BASE_URL", "https://env.openrouter.test/v1")

    provider = OpenRouterProvider()
    assert provider.model_name == "env/test-model:free"
    assert provider.base_url == "https://env.openrouter.test/v1"
    assert provider._api_key == "env-secret-key"


# =====================================================================
# 2. Missing API Key Handling
# =====================================================================


@pytest.mark.asyncio
async def test_missing_api_key_availability(monkeypatch) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    provider = OpenRouterProvider(api_key="")
    assert await provider.check_availability() is False


@pytest.mark.asyncio
async def test_missing_api_key_generate_raises(monkeypatch) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    provider = OpenRouterProvider(api_key="")
    with pytest.raises(ProviderUnavailableError, match="API key is not configured"):
        await provider.generate("Hello world")


# =====================================================================
# 3. Health & Availability Checking with Mock HTTP
# =====================================================================


@pytest.mark.asyncio
async def test_check_availability_success() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer mock-api-key"
        assert str(request.url).endswith("/auth/key")
        return httpx.Response(200, json={"data": {"label": "valid-key"}})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = OpenRouterProvider(api_key="mock-api-key", http_client=client)
        assert await provider.check_availability() is True


@pytest.mark.asyncio
async def test_check_availability_auth_failure() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "Invalid API key"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = OpenRouterProvider(api_key="bad-api-key", http_client=client)
        assert await provider.check_availability() is False


@pytest.mark.asyncio
async def test_check_availability_network_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Connection refused")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = OpenRouterProvider(api_key="mock-key", http_client=client)
        assert await provider.check_availability() is False


# =====================================================================
# 4. Successful Generation with Mock HTTP
# =====================================================================


@pytest.mark.asyncio
async def test_generate_success_mocked() -> None:
    recorded_request = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        body = json.loads(request.content.decode("utf-8"))
        recorded_request["headers"] = dict(request.headers)
        recorded_request["body"] = body

        response_data = {
            "id": "gen-12345",
            "model": "nvidia/nemotron-3.5-lightning:free",
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "OpenRouter provider test successful.",
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 12,
                "completion_tokens": 8,
                "total_tokens": 20,
            },
        }
        return httpx.Response(200, json=response_data)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = OpenRouterProvider(
            api_key="test-secret-key",
            model="nvidia/nemotron-3.5-lightning:free",
            http_client=client,
        )

        result = await provider.generate(
            "Respond with exactly: OpenRouter provider test successful.",
            temperature=0.0,
            max_tokens=50,
        )

        # Assert result structure
        assert result.text == "OpenRouter provider test successful."
        assert result.provider_name == "openrouter"
        assert result.model == "nvidia/nemotron-3.5-lightning:free"
        assert result.prompt_tokens == 12
        assert result.completion_tokens == 8
        assert result.total_tokens == 20
        assert result.latency_ms is not None
        assert result.latency_ms > 0
        assert result.metadata["id"] == "gen-12345"
        assert result.metadata["finish_reason"] == "stop"

        # Assert outgoing HTTP contract
        headers = recorded_request["headers"]
        assert headers["authorization"] == "Bearer test-secret-key"
        assert headers["http-referer"] == APP_REFERER
        assert headers["x-title"] == APP_TITLE

        body = recorded_request["body"]
        assert body["model"] == "nvidia/nemotron-3.5-lightning:free"
        assert body["messages"] == [
            {"role": "user", "content": "Respond with exactly: OpenRouter provider test successful."}
        ]
        assert body["temperature"] == 0.0
        assert body["max_tokens"] == 50


@pytest.mark.asyncio
async def test_generate_model_override() -> None:
    recorded_model = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        body = json.loads(request.content.decode("utf-8"))
        recorded_model["model"] = body["model"]
        return httpx.Response(
            200,
            json={
                "id": "gen-999",
                "model": body["model"],
                "choices": [{"message": {"role": "assistant", "content": "Override OK"}}],
            },
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = OpenRouterProvider(
            api_key="test-key",
            model="default-model",
            http_client=client,
        )

        result = await provider.generate("Test prompt", model="special-override-model:free")
        assert result.text == "Override OK"
        assert recorded_model["model"] == "special-override-model:free"


# =====================================================================
# 5. API Error Handling
# =====================================================================


@pytest.mark.parametrize(
    ("status_code", "error_response", "expected_match"),
    [
        (401, {"error": {"message": "Invalid API key"}}, "authentication failed"),
        (429, {"error": {"message": "Rate limit exceeded"}}, "rate limit exceeded"),
        (500, {"error": {"message": "Internal server error"}}, "OpenRouter API error"),
    ],
)
@pytest.mark.asyncio
async def test_generate_http_error_codes(
    status_code: int,
    error_response: dict,
    expected_match: str,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json=error_response)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = OpenRouterProvider(api_key="test-key", http_client=client)
        with pytest.raises(ProviderError, match=expected_match):
            await provider.generate("Hello world")


@pytest.mark.asyncio
async def test_generate_network_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("Timed out waiting for response")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = OpenRouterProvider(api_key="test-key", http_client=client)
        with pytest.raises(ProviderError, match="network request failed"):
            await provider.generate("Hello world")


@pytest.mark.asyncio
async def test_generate_empty_choices() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"id": "empty", "choices": []})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = OpenRouterProvider(api_key="test-key", http_client=client)
        with pytest.raises(ProviderError, match="no completion choices"):
            await provider.generate("Hello world")


# =====================================================================
# 6. ProviderManager Integration
# =====================================================================


def test_providermanager_registration_and_lookup() -> None:
    pm = ProviderManager(allow_paid=False)
    provider = OpenRouterProvider(api_key="mock-key")

    # Registration succeeds under allow_paid=False because is_paid=False
    pm.register(provider)
    assert pm.has_provider("openrouter")
    assert pm.get_provider("openrouter") is provider
    assert "openrouter" in pm.list_providers()


@pytest.mark.asyncio
async def test_providermanager_health_and_circuit_breaker() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "Service down"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = OpenRouterProvider(api_key="mock-key", http_client=client)
        pm = ProviderManager(
            allow_paid=False,
            circuit_breaker_failure_threshold=2,
            circuit_breaker_cooldown_seconds=30.0,
        )
        pm.register(provider)

        # Provider availability check
        is_available = await provider.check_availability()
        assert is_available is False

        # Mark unhealthy on PM
        pm.mark_unhealthy("openrouter")
        from src.providers.health import CircuitState, HealthStatus

        assert pm.get_health("openrouter") == HealthStatus.UNHEALTHY

        # Simulate failures to trip circuit breaker
        cb = pm.get_circuit_breaker("openrouter")
        cb.record_failure()
        cb.record_failure()
        assert cb.is_available is False
        assert cb.state == CircuitState.OPEN


# =====================================================================
# 7. Secret Sanitization Verification
# =====================================================================


@pytest.mark.asyncio
async def test_api_key_not_leaked_in_errors() -> None:
    secret_key = "super-secret-key-xyz-987"

    def handler(request: httpx.Request) -> httpx.Response:
        # Simulate server error echoing request headers/key
        return httpx.Response(
            401,
            text=f"Unauthorized access with token {secret_key}",
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = OpenRouterProvider(api_key=secret_key, http_client=client)
        with pytest.raises(ProviderError) as exc_info:
            await provider.generate("Test prompt")

        error_msg = str(exc_info.value)
        assert secret_key not in error_msg
        assert "[REDACTED_API_KEY]" in error_msg
