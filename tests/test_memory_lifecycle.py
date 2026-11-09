"""Unit tests for Milestone 5.8: RAM-Aware Model Lifecycle Manager.

Covers:
- System RAM detection via standard library (Windows, Linux, macOS) and graceful fallback
- HardwareProfile enum (AUTO, PROFILE_8GB, PROFILE_16GB) in Settings
- Dynamic resolution of AUTO profile and budget overrides
- Distinct ModelLoadState transitions: RESERVED (reservation only) vs LOADED (actual provider load)
- Approximate memory budget safety checks and MemoryBudgetExceededError
- Sequential single-model residency enforcement (eviction before load)
- Robust failure handling (eviction failure aborts new load, lock release guarantees, recovery from FAILED state)
- OllamaProvider keep_alive configuration, load_model, and unload_model (keep_alive: 0) API verification
- Concurrency safety under concurrent acquire, release, and evict calls
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict
from unittest.mock import MagicMock, mock_open, patch

import httpx
import pytest

from src.config import (
    HardwareProfile,
    Settings,
    detect_system_ram_mb,
)
from src.providers.base import ModelDescriptor, ModelTier, TaskComplexity
from src.providers.exceptions import ProviderError, ProviderUnavailableError
from src.providers.lifecycle import (
    MemoryBudgetExceededError,
    ModelLifecycleError,
    ModelLifecycleManager,
    ModelLoadState,
)
from src.providers.ollama import OllamaProvider


# ==========================================================================
# Helpers & Fixtures
# ==========================================================================


def _make_descriptor(model_id: str, ram_mb: int) -> ModelDescriptor:
    return ModelDescriptor(
        model_id=model_id,
        tier=ModelTier.SLM_SMALL,
        is_local=True,
        context_window=4096,
        supports_structured_output=True,
        ram_required_mb=ram_mb,
        cost_per_1k_tokens=0.0,
        supported_complexities=(TaskComplexity.DETERMINISTIC, TaskComplexity.EXTRACTION),
    )


# ==========================================================================
# 1. Hardware Profile & System RAM Detection Tests
# ==========================================================================


class TestHardwareProfileDetection:
    """Test RAM detection across OSes, HardwareProfile enum, and Settings resolution."""

    def test_hardware_profile_enum_values(self) -> None:
        assert HardwareProfile.AUTO == "auto"
        assert HardwareProfile.PROFILE_8GB == "8gb"
        assert HardwareProfile.PROFILE_16GB == "16gb"

    def test_detect_system_ram_mb_returns_positive_integer(self) -> None:
        ram = detect_system_ram_mb()
        assert isinstance(ram, int)
        assert ram > 0

    def test_detect_system_ram_mb_fallback_on_exception(self) -> None:
        with patch("sys.platform", "unknown_os"):
            ram = detect_system_ram_mb()
            assert ram == 8192

    def test_detect_system_ram_mb_linux_proc_meminfo(self) -> None:
        meminfo_data = "MemTotal:       16384232 kB\nMemFree:         8192000 kB\n"
        with patch("sys.platform", "linux"):
            with patch("os.path.exists", return_value=True):
                with patch("builtins.open", mock_open(read_data=meminfo_data)):
                    ram = detect_system_ram_mb()
                    assert ram == int(16384232 / 1024)

    def test_detect_system_ram_mb_darwin_fallback(self) -> None:
        with patch("sys.platform", "darwin"):
            with patch("ctypes.CDLL", side_effect=Exception("No dylib")):
                ram = detect_system_ram_mb()
                assert ram == 8192

    def test_settings_default_hardware_profile_is_auto(self, clean_env: None) -> None:
        settings = Settings()
        assert settings.ram_profile == HardwareProfile.AUTO
        assert settings.model_keep_alive == "0"

    def test_settings_resolved_profile_auto_under_12gb(self, clean_env: None) -> None:
        with patch("src.config.detect_system_ram_mb", return_value=8192):
            settings = Settings()
            assert settings.resolved_ram_profile == HardwareProfile.PROFILE_8GB
            assert settings.model_ram_budget_mb == 2200

    def test_settings_resolved_profile_auto_over_12gb(self, clean_env: None) -> None:
        with patch("src.config.detect_system_ram_mb", return_value=16384):
            settings = Settings()
            assert settings.resolved_ram_profile == HardwareProfile.PROFILE_16GB
            assert settings.model_ram_budget_mb == 5500

    def test_settings_manual_ram_profile_override(self, clean_env: None) -> None:
        settings_8 = Settings(ram_profile="8gb")
        assert settings_8.resolved_ram_profile == HardwareProfile.PROFILE_8GB
        assert settings_8.model_ram_budget_mb == 2200

        settings_16 = Settings(ram_profile="16GB")  # Case insensitive
        assert settings_16.resolved_ram_profile == HardwareProfile.PROFILE_16GB
        assert settings_16.model_ram_budget_mb == 5500

    def test_settings_custom_model_max_ram_mb(self, clean_env: None) -> None:
        settings = Settings(model_max_ram_mb=3500)
        assert settings.model_ram_budget_mb == 3500

    def test_safe_summary_includes_hardware_profile(self, clean_env: None) -> None:
        settings = Settings()
        summary = settings.safe_summary()
        assert "ram_profile" in summary
        assert "resolved_ram_profile" in summary
        assert "model_ram_budget_mb" in summary
        assert "model_keep_alive" in summary


# ==========================================================================
# 2. Approximate Budget Safety Gate Tests
# ==========================================================================


class TestModelLifecycleBudget:
    """Test memory budget evaluation and over-budget rejection."""

    def test_can_fit_model_under_budget(self) -> None:
        mgr = ModelLifecycleManager(profile=HardwareProfile.PROFILE_8GB, max_ram_mb=2200)
        desc = _make_descriptor("llama3.2:1b", 2048)
        assert mgr.can_fit_model(desc) is True

    def test_can_fit_model_over_budget(self) -> None:
        mgr = ModelLifecycleManager(profile=HardwareProfile.PROFILE_8GB, max_ram_mb=2200)
        desc = _make_descriptor("llama3.1:8b", 5120)
        assert mgr.can_fit_model(desc) is False

    @pytest.mark.asyncio
    async def test_acquire_model_over_budget_raises_error(self) -> None:
        mgr = ModelLifecycleManager(profile=HardwareProfile.PROFILE_8GB, max_ram_mb=2200)
        desc = _make_descriptor("llama3.1:8b", 5120)

        with pytest.raises(MemoryBudgetExceededError) as exc_info:
            await mgr.acquire_model("llama3.1:8b", descriptor=desc)

        err = exc_info.value
        assert err.model_name == "llama3.1:8b"
        assert err.required_mb == 5120
        assert err.budget_mb == 2200
        assert err.profile == HardwareProfile.PROFILE_8GB
        assert "exceeds hardware budget" in str(err)


# ==========================================================================
# 3. Model Reservation vs Loading Semantics & Single-Model Residency
# ==========================================================================


class TestModelLifecycleResidency:
    """Test clear distinction between reservation (no provider) and actual loading (with provider)."""

    @pytest.mark.asyncio
    async def test_acquire_without_provider_sets_reserved_not_loaded(self) -> None:
        """When no provider is supplied, model enters RESERVED state, NEVER LOADED."""
        mgr = ModelLifecycleManager(profile=HardwareProfile.PROFILE_8GB, max_ram_mb=2200)
        desc = _make_descriptor("llama3.2:1b", 2048)

        assert mgr.get_state("llama3.2:1b") == ModelLoadState.UNLOADED
        assert mgr.is_loaded("llama3.2:1b") is False
        assert mgr.is_reserved("llama3.2:1b") is False
        assert mgr.get_active_model() is None
        assert mgr.allocated_mb == 0

        # Acquire without provider (reservation only)
        await mgr.acquire_model("llama3.2:1b", descriptor=desc)

        # Semantics check: state is RESERVED, NOT LOADED
        assert mgr.get_state("llama3.2:1b") == ModelLoadState.RESERVED
        assert mgr.is_reserved("llama3.2:1b") is True
        assert mgr.is_loaded("llama3.2:1b") is False
        assert mgr.get_reserved_models() == ["llama3.2:1b"]
        assert mgr.get_loaded_models() == []
        assert mgr.get_active_model() == "llama3.2:1b"
        assert mgr.allocated_mb == 2048

        # Re-acquiring already reserved model without provider is an idempotent no-op
        await mgr.acquire_model("llama3.2:1b", descriptor=desc)
        assert mgr.get_state("llama3.2:1b") == ModelLoadState.RESERVED

    @pytest.mark.asyncio
    async def test_acquire_with_provider_transitions_from_reserved_to_loaded(self) -> None:
        """Calling acquire with provider on a reserved model loads it and transitions to LOADED."""
        mgr = ModelLifecycleManager(profile=HardwareProfile.PROFILE_8GB, max_ram_mb=2200)
        desc = _make_descriptor("llama3.2:1b", 2048)

        # 1. Initial reservation
        await mgr.acquire_model("llama3.2:1b", descriptor=desc)
        assert mgr.get_state("llama3.2:1b") == ModelLoadState.RESERVED
        assert mgr.is_loaded("llama3.2:1b") is False

        # 2. Mock provider that loads model
        provider = MagicMock()
        provider.load_model = MagicMock(return_value=asyncio.sleep(0.01))

        # 3. Acquire with provider -> executes provider.load_model and transitions to LOADED
        await mgr.acquire_model("llama3.2:1b", descriptor=desc, provider=provider)
        assert mgr.get_state("llama3.2:1b") == ModelLoadState.LOADED
        assert mgr.is_loaded("llama3.2:1b") is True
        assert mgr.is_reserved("llama3.2:1b") is False
        assert mgr.get_loaded_models() == ["llama3.2:1b"]
        assert mgr.get_reserved_models() == []

    @pytest.mark.asyncio
    async def test_release_model_transitions_to_unloaded(self) -> None:
        mgr = ModelLifecycleManager(profile=HardwareProfile.PROFILE_8GB, max_ram_mb=2200)
        desc = _make_descriptor("llama3.2:1b", 2048)

        await mgr.acquire_model("llama3.2:1b", descriptor=desc)
        assert mgr.get_active_model() == "llama3.2:1b"

        await mgr.release_model("llama3.2:1b")
        assert mgr.get_state("llama3.2:1b") == ModelLoadState.UNLOADED
        assert mgr.get_active_model() is None
        assert mgr.allocated_mb == 0

        # Releasing already unloaded model is a safe no-op
        await mgr.release_model("llama3.2:1b")
        assert mgr.get_state("llama3.2:1b") == ModelLoadState.UNLOADED

    @pytest.mark.asyncio
    async def test_single_model_residency_auto_evicts_previous_model(self) -> None:
        mgr = ModelLifecycleManager(profile=HardwareProfile.PROFILE_8GB, max_ram_mb=2200)
        desc_a = _make_descriptor("model_a:1b", 1500)
        desc_b = _make_descriptor("model_b:1b", 1500)

        # 1. Acquire Model A (reservation)
        await mgr.acquire_model("model_a:1b", descriptor=desc_a)
        assert mgr.get_active_model() == "model_a:1b"
        assert mgr.get_state("model_a:1b") == ModelLoadState.RESERVED

        # 2. Acquire Model B -> Model A must be evicted first
        await mgr.acquire_model("model_b:1b", descriptor=desc_b)
        assert mgr.get_state("model_a:1b") == ModelLoadState.UNLOADED
        assert mgr.get_state("model_b:1b") == ModelLoadState.RESERVED
        assert mgr.get_active_model() == "model_b:1b"
        assert mgr.allocated_mb == 1500

    @pytest.mark.asyncio
    async def test_evict_all_clears_active_and_failed_models(self) -> None:
        mgr = ModelLifecycleManager(profile=HardwareProfile.PROFILE_8GB, max_ram_mb=2200)
        desc = _make_descriptor("model_a:1b", 1500)

        await mgr.acquire_model("model_a:1b", descriptor=desc)
        assert mgr.get_active_model() == "model_a:1b"

        await mgr.evict_all()
        assert mgr.get_state("model_a:1b") == ModelLoadState.UNLOADED
        assert mgr.get_active_model() is None
        assert mgr.allocated_mb == 0


# ==========================================================================
# 4. Safe Failure Handling, Recovery & Lock Safety Tests
# ==========================================================================


class TestModelLifecycleFailureHandling:
    """Test failure recovery, lock safety, and state restoration."""

    @pytest.mark.asyncio
    async def test_eviction_failure_aborts_new_model_acquisition(self) -> None:
        mgr = ModelLifecycleManager(profile=HardwareProfile.PROFILE_8GB, max_ram_mb=2200)
        desc_a = _make_descriptor("model_a:1b", 1500)
        desc_b = _make_descriptor("model_b:1b", 1500)

        # Mock provider whose unload_model fails
        failing_provider = MagicMock()
        failing_provider.unload_model = MagicMock(side_effect=ProviderUnavailableError("ollama", "daemon down"))

        # Pre-load Model A
        await mgr.acquire_model("model_a:1b", descriptor=desc_a)
        assert mgr.get_active_model() == "model_a:1b"

        # Attempt to acquire Model B with failing eviction of Model A
        with pytest.raises(ModelLifecycleError) as exc_info:
            await mgr.acquire_model("model_b:1b", descriptor=desc_b, provider=failing_provider)

        assert "Failed to evict previously active model 'model_a:1b'" in str(exc_info.value)

        # Verification: Model A is FAILED, Model B was NEVER marked active or loaded
        assert mgr.get_state("model_a:1b") == ModelLoadState.FAILED
        assert mgr.get_state("model_b:1b") == ModelLoadState.UNLOADED
        assert mgr.get_active_model() is None
        assert mgr._lock.locked() is False

    @pytest.mark.asyncio
    async def test_recovery_from_failed_model_state(self) -> None:
        """A model in FAILED state can be successfully evicted on subsequent recovery."""
        mgr = ModelLifecycleManager(profile=HardwareProfile.PROFILE_8GB, max_ram_mb=2200)
        desc_a = _make_descriptor("model_a:1b", 1500)
        desc_b = _make_descriptor("model_b:1b", 1500)

        # 1. Fail eviction of Model A
        failing_provider = MagicMock()
        failing_provider.unload_model = MagicMock(side_effect=ProviderUnavailableError("ollama", "down"))
        await mgr.acquire_model("model_a:1b", descriptor=desc_a)

        with pytest.raises(ModelLifecycleError):
            await mgr.acquire_model("model_b:1b", descriptor=desc_b, provider=failing_provider)

        assert mgr.get_state("model_a:1b") == ModelLoadState.FAILED

        # 2. Recover: provider is now online and unload succeeds
        recovering_provider = MagicMock()
        recovering_provider.unload_model = MagicMock(return_value=asyncio.sleep(0.01))
        recovering_provider.load_model = MagicMock(return_value=asyncio.sleep(0.01))

        # Re-attempt acquisition of Model B
        await mgr.acquire_model("model_b:1b", descriptor=desc_b, provider=recovering_provider)

        assert mgr.get_state("model_a:1b") == ModelLoadState.UNLOADED
        assert mgr.get_state("model_b:1b") == ModelLoadState.LOADED
        assert mgr.get_active_model() == "model_b:1b"

    @pytest.mark.asyncio
    async def test_load_failure_marks_failed_and_clears_active(self) -> None:
        mgr = ModelLifecycleManager(profile=HardwareProfile.PROFILE_8GB, max_ram_mb=2200)
        desc = _make_descriptor("model_fail:1b", 1500)

        # Mock provider whose load_model fails
        failing_provider = MagicMock()
        failing_provider.load_model = MagicMock(side_effect=ProviderError("Out of memory on GPU"))

        with pytest.raises(ModelLifecycleError) as exc_info:
            await mgr.acquire_model("model_fail:1b", descriptor=desc, provider=failing_provider)

        assert "Failed to load model 'model_fail:1b'" in str(exc_info.value)
        assert mgr.get_state("model_fail:1b") == ModelLoadState.FAILED
        assert mgr.get_active_model() is None
        assert mgr.allocated_mb == 0
        assert mgr._lock.locked() is False


# ==========================================================================
# 5. Ollama Provider keep_alive, load_model & unload_model API Tests
# ==========================================================================


class TestOllamaProviderLoadUnload:
    """Verify OllamaProvider keep_alive configuration, load_model, and unload_model."""

    @pytest.mark.asyncio
    async def test_provider_keep_alive_resolves_from_settings(self, clean_env: None) -> None:
        settings = Settings(model_keep_alive="10m")
        with patch("src.providers.ollama.get_settings", return_value=settings):
            provider = OllamaProvider()
            assert provider.keep_alive == "10m"

    @pytest.mark.asyncio
    async def test_provider_keep_alive_explicit_override(self) -> None:
        provider = OllamaProvider(keep_alive="15m")
        assert provider.keep_alive == "15m"

    @pytest.mark.asyncio
    async def test_unload_model_strictly_sends_keep_alive_zero(self) -> None:
        captured_payloads: list[dict[str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/api/generate":
                import json
                payload = json.loads(request.content.decode("utf-8"))
                captured_payloads.append(payload)
                return httpx.Response(200, json={"done": True})
            return httpx.Response(404)

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            provider = OllamaProvider(http_client=client, keep_alive="30m")
            result = await provider.unload_model("phi3:mini")
            assert result is True

        assert len(captured_payloads) == 1
        assert captured_payloads[0]["model"] == "phi3:mini"
        assert captured_payloads[0]["keep_alive"] == 0  # Strictly 0 regardless of instance keep_alive

    @pytest.mark.asyncio
    async def test_load_model_sends_default_or_explicit_keep_alive(self) -> None:
        captured_payloads: list[dict[str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/api/generate":
                import json
                payload = json.loads(request.content.decode("utf-8"))
                captured_payloads.append(payload)
                return httpx.Response(200, json={"done": True})
            return httpx.Response(404)

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            provider = OllamaProvider(http_client=client, keep_alive="5m")

            # 1. Use default keep_alive ("5m")
            await provider.load_model("phi3:mini")
            assert captured_payloads[0]["keep_alive"] == "5m"

            # 2. Explicit keep_alive override ("20m")
            await provider.load_model("phi3:mini", keep_alive="20m")
            assert captured_payloads[1]["keep_alive"] == "20m"

    @pytest.mark.asyncio
    async def test_generate_sends_default_or_explicit_keep_alive(self) -> None:
        captured_payloads: list[dict[str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/api/generate":
                import json
                payload = json.loads(request.content.decode("utf-8"))
                captured_payloads.append(payload)
                return httpx.Response(200, json={"response": "ok", "done": True})
            return httpx.Response(404)

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            provider = OllamaProvider(http_client=client, keep_alive="2m")

            # 1. Default keep_alive
            await provider.generate("hello")
            assert captured_payloads[0]["keep_alive"] == "2m"

            # 2. Explicit override in kwargs
            await provider.generate("hello", keep_alive="1h")
            assert captured_payloads[1]["keep_alive"] == "1h"

    @pytest.mark.asyncio
    async def test_unload_model_handles_daemon_unreachable(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("Connection refused")

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            provider = OllamaProvider(http_client=client)
            with pytest.raises(ProviderUnavailableError) as exc_info:
                await provider.unload_model("phi3:mini")
            assert "unreachable" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_lifecycle_manager_end_to_end_with_mocked_ollama(self) -> None:
        events: list[tuple[str, str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/api/generate":
                import json
                payload = json.loads(request.content.decode("utf-8"))
                model = payload.get("model")
                keep_alive = payload.get("keep_alive")
                events.append(("generate", model, keep_alive))
                return httpx.Response(200, json={"done": True})
            return httpx.Response(404)

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            provider = OllamaProvider(http_client=client)
            mgr = ModelLifecycleManager(profile=HardwareProfile.PROFILE_8GB, max_ram_mb=2200)

            desc_1 = _make_descriptor("qwen2.5:1.5b", 1800)
            desc_2 = _make_descriptor("llama3.2:1b", 1200)

            # 1. Load Model 1
            await mgr.acquire_model("qwen2.5:1.5b", descriptor=desc_1, provider=provider)
            assert mgr.get_state("qwen2.5:1.5b") == ModelLoadState.LOADED
            assert mgr.get_active_model() == "qwen2.5:1.5b"

            # 2. Load Model 2 -> triggers eviction of Model 1 with keep_alive: 0
            await mgr.acquire_model("llama3.2:1b", descriptor=desc_2, provider=provider)
            assert mgr.get_state("qwen2.5:1.5b") == ModelLoadState.UNLOADED
            assert mgr.get_state("llama3.2:1b") == ModelLoadState.LOADED
            assert mgr.get_active_model() == "llama3.2:1b"

            # 3. Explicit release of Model 2
            await mgr.release_model("llama3.2:1b", provider=provider)
            assert mgr.get_state("llama3.2:1b") == ModelLoadState.UNLOADED
            assert mgr.get_active_model() is None

        # Verify exact sequence of Ollama API calls:
        # Event 1: Load qwen2.5:1.5b (keep_alive: '0')
        # Event 2: Unload qwen2.5:1.5b (keep_alive: 0)
        # Event 3: Load llama3.2:1b (keep_alive: '0')
        # Event 4: Unload llama3.2:1b (keep_alive: 0)
        assert len(events) == 4
        assert events[0] == ("generate", "qwen2.5:1.5b", "0")
        assert events[1] == ("generate", "qwen2.5:1.5b", 0)
        assert events[2] == ("generate", "llama3.2:1b", "0")
        assert events[3] == ("generate", "llama3.2:1b", 0)


# ==========================================================================
# 6. Concurrency Safety Tests
# ==========================================================================


class TestModelLifecycleConcurrency:
    """Verify that concurrent calls to acquire, release, and evict preserve consistency."""

    @pytest.mark.asyncio
    async def test_concurrent_acquire_same_model_is_consistent(self) -> None:
        mgr = ModelLifecycleManager(profile=HardwareProfile.PROFILE_8GB, max_ram_mb=2200)
        desc = _make_descriptor("llama3.2:1b", 2048)

        provider = MagicMock()
        load_count = 0

        async def fake_load(model_name: str, keep_alive: Any = None) -> bool:
            nonlocal load_count
            load_count += 1
            await asyncio.sleep(0.01)
            return True

        provider.load_model = fake_load

        # Run 5 concurrent acquires for the same model
        await asyncio.gather(
            mgr.acquire_model("llama3.2:1b", descriptor=desc, provider=provider),
            mgr.acquire_model("llama3.2:1b", descriptor=desc, provider=provider),
            mgr.acquire_model("llama3.2:1b", descriptor=desc, provider=provider),
            mgr.acquire_model("llama3.2:1b", descriptor=desc, provider=provider),
            mgr.acquire_model("llama3.2:1b", descriptor=desc, provider=provider),
        )

        assert mgr.get_state("llama3.2:1b") == ModelLoadState.LOADED
        assert mgr.get_active_model() == "llama3.2:1b"
        assert mgr.allocated_mb == 2048
        # Because of locking and idempotency check, load should only execute once
        assert load_count == 1
        assert mgr._lock.locked() is False

    @pytest.mark.asyncio
    async def test_concurrent_acquire_and_release_preserves_valid_state(self) -> None:
        mgr = ModelLifecycleManager(profile=HardwareProfile.PROFILE_8GB, max_ram_mb=2200)
        desc_a = _make_descriptor("model_a:1b", 1500)
        desc_b = _make_descriptor("model_b:1b", 1500)

        # Run simultaneous acquire, release, evict
        await asyncio.gather(
            mgr.acquire_model("model_a:1b", descriptor=desc_a),
            mgr.release_model("model_a:1b"),
            mgr.acquire_model("model_b:1b", descriptor=desc_b),
            mgr.evict_all(),
            return_exceptions=True,
        )

        # Result must be in a consistent state without orphaned locks
        assert mgr._lock.locked() is False
        assert mgr.allocated_mb >= 0
        if mgr.get_active_model() is not None:
            active = mgr.get_active_model()
            assert mgr.get_state(active) in (ModelLoadState.RESERVED, ModelLoadState.LOADED)
        else:
            assert mgr.allocated_mb == 0
