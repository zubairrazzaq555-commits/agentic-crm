"""Unit tests for Milestone 5.6: Execution Mode & Model Capability Foundation.

Covers:
- ExecutionMode enum (LOCAL, CLOUD, HYBRID)
- Settings configuration for execution modes and cloud fallback
- Local isolation policy (LOCAL mode strictly blocks cloud fallback)
- ModelTier enum (SLM_SMALL, SLM_MEDIUM, LLM_LARGE)
- TaskComplexity enum (DETERMINISTIC, EXTRACTION, CLASSIFICATION, REASONING, PLANNING)
- ModelDescriptor dataclass (immutability, defaults, can_handle)
- BaseProvider capability metadata and backward compatibility defaults
- MockProvider descriptor and is_local behavior
- OpenRouterProvider descriptor and is_local behavior
"""

from __future__ import annotations

import os
from typing import Any

import pytest

from src.config import ExecutionMode, Settings
from src.providers.base import (
    BaseProvider,
    ModelDescriptor,
    ModelTier,
    ProviderResult,
    TaskComplexity,
)
from src.providers.mock_provider import MockProvider
from src.providers.openrouter import OpenRouterProvider


# ==========================================================================
# ExecutionMode & Configuration Tests
# ==========================================================================


class TestExecutionModeConfig:
    """Verify ExecutionMode enum and configuration settings."""

    def test_execution_mode_enum_values(self) -> None:
        assert ExecutionMode.LOCAL == "local"
        assert ExecutionMode.CLOUD == "cloud"
        assert ExecutionMode.HYBRID == "hybrid"

    def test_default_settings_execution_mode(self, clean_env: None) -> None:
        settings = Settings()
        assert settings.execution_mode == ExecutionMode.HYBRID
        assert settings.allow_cloud_fallback is False
        assert settings.can_use_local is True
        assert settings.can_use_cloud is False

    def test_override_execution_mode_local(self, clean_env: None) -> None:
        os.environ["AGENTIC_CRM_EXECUTION_MODE"] = "local"
        settings = Settings()
        assert settings.execution_mode == ExecutionMode.LOCAL
        assert settings.can_use_local is True
        assert settings.can_use_cloud is False

    def test_case_insensitive_execution_mode(self, clean_env: None) -> None:
        os.environ["AGENTIC_CRM_EXECUTION_MODE"] = "LOCAL"
        settings = Settings()
        assert settings.execution_mode == ExecutionMode.LOCAL

        os.environ["AGENTIC_CRM_EXECUTION_MODE"] = "Hybrid"
        settings2 = Settings()
        assert settings2.execution_mode == ExecutionMode.HYBRID

    def test_override_execution_mode_cloud(self, clean_env: None) -> None:
        os.environ["AGENTIC_CRM_EXECUTION_MODE"] = "cloud"
        settings = Settings()
        assert settings.execution_mode == ExecutionMode.CLOUD
        assert settings.can_use_local is False
        assert settings.can_use_cloud is True

    def test_hybrid_with_cloud_fallback_opt_in(self, clean_env: None) -> None:
        os.environ["AGENTIC_CRM_EXECUTION_MODE"] = "hybrid"
        os.environ["AGENTIC_CRM_ALLOW_CLOUD_FALLBACK"] = "true"
        settings = Settings()
        assert settings.execution_mode == ExecutionMode.HYBRID
        assert settings.allow_cloud_fallback is True
        assert settings.can_use_local is True
        assert settings.can_use_cloud is True

    def test_local_mode_strictly_overrides_cloud_fallback(
        self, clean_env: None
    ) -> None:
        """LOCAL mode must never allow cloud fallback, even if explicitly requested."""
        os.environ["AGENTIC_CRM_EXECUTION_MODE"] = "local"
        os.environ["AGENTIC_CRM_ALLOW_CLOUD_FALLBACK"] = "true"
        settings = Settings()
        assert settings.execution_mode == ExecutionMode.LOCAL
        assert settings.allow_cloud_fallback is False
        assert settings.can_use_local is True
        assert settings.can_use_cloud is False

    def test_direct_settings_local_mode_guard(self) -> None:
        settings = Settings(
            execution_mode=ExecutionMode.LOCAL,
            allow_cloud_fallback=True,
        )
        assert settings.execution_mode == ExecutionMode.LOCAL
        assert settings.allow_cloud_fallback is False
        assert settings.can_use_cloud is False

    def test_safe_summary_includes_execution_mode_keys(
        self, clean_env: None
    ) -> None:
        settings = Settings()
        summary = settings.safe_summary()
        assert summary["execution_mode"] == "hybrid"
        assert summary["allow_cloud_fallback"] == "False"
        assert summary["can_use_local"] == "True"
        assert summary["can_use_cloud"] == "False"


# ==========================================================================
# ModelTier & TaskComplexity Enum Tests
# ==========================================================================


class TestModelCapabilityEnums:
    """Verify ModelTier and TaskComplexity definitions."""

    def test_model_tier_values(self) -> None:
        assert ModelTier.SLM_SMALL == "slm_small"
        assert ModelTier.SLM_MEDIUM == "slm_medium"
        assert ModelTier.LLM_LARGE == "llm_large"

    def test_task_complexity_values(self) -> None:
        assert TaskComplexity.DETERMINISTIC == "deterministic"
        assert TaskComplexity.EXTRACTION == "extraction"
        assert TaskComplexity.CLASSIFICATION == "classification"
        assert TaskComplexity.REASONING == "reasoning"
        assert TaskComplexity.PLANNING == "planning"


# ==========================================================================
# ModelDescriptor Dataclass Tests
# ==========================================================================


class TestModelDescriptor:
    """Verify ModelDescriptor defaults, immutability, and handling checks."""

    def test_descriptor_defaults(self) -> None:
        desc = ModelDescriptor(model_id="qwen2.5:1.5b")
        assert desc.model_id == "qwen2.5:1.5b"
        assert desc.tier == ModelTier.SLM_SMALL
        assert desc.is_local is False
        assert desc.context_window == 4096
        assert desc.supports_structured_output is True
        assert desc.ram_required_mb is None
        assert desc.cost_per_1k_tokens == 0.0
        assert desc.supported_complexities == (
            TaskComplexity.EXTRACTION,
            TaskComplexity.CLASSIFICATION,
        )
        assert desc.metadata == {}

    def test_descriptor_immutability(self) -> None:
        desc = ModelDescriptor(model_id="test-model")
        with pytest.raises(Exception):  # FrozenInstanceError
            desc.model_id = "new-model"  # type: ignore[misc]

    def test_descriptor_can_handle(self) -> None:
        desc = ModelDescriptor(
            model_id="qwen2.5:1.5b",
            supported_complexities=(
                TaskComplexity.EXTRACTION,
                TaskComplexity.CLASSIFICATION,
            ),
        )
        assert desc.can_handle(TaskComplexity.EXTRACTION) is True
        assert desc.can_handle(TaskComplexity.CLASSIFICATION) is True
        assert desc.can_handle(TaskComplexity.REASONING) is False
        assert desc.can_handle(TaskComplexity.PLANNING) is False
        assert desc.can_handle(TaskComplexity.DETERMINISTIC) is False


# ==========================================================================
# BaseProvider Capability Interface Tests
# ==========================================================================


class _MinimalProvider(BaseProvider):
    """Minimal provider implementation without an explicit descriptor."""

    @property
    def name(self) -> str:
        return "minimal"

    @property
    def is_paid(self) -> bool:
        return False

    @property
    def model_name(self) -> str:
        return "minimal-model"

    async def generate(self, prompt: str, **kwargs: Any) -> ProviderResult:
        return ProviderResult(text="ok", provider_name=self.name, model=self.model_name)

    async def check_availability(self) -> bool:
        return True


class _CustomDescriptorProvider(_MinimalProvider):
    """Provider supplying a specialized descriptor."""

    def __init__(self, descriptor: ModelDescriptor) -> None:
        self._descriptor = descriptor

    @property
    def descriptor(self) -> ModelDescriptor | None:
        return self._descriptor


class TestBaseProviderCapabilities:
    """Verify BaseProvider optional capability methods and backward compatibility."""

    def test_base_provider_default_capabilities(self) -> None:
        provider = _MinimalProvider()
        assert provider.descriptor is None
        assert provider.is_local is False
        # Default backward-compatible complexities:
        assert provider.can_handle_complexity(TaskComplexity.DETERMINISTIC) is True
        assert provider.can_handle_complexity(TaskComplexity.EXTRACTION) is True
        assert provider.can_handle_complexity(TaskComplexity.CLASSIFICATION) is True
        assert provider.can_handle_complexity(TaskComplexity.REASONING) is False
        assert provider.can_handle_complexity(TaskComplexity.PLANNING) is False

    def test_custom_descriptor_delegation(self) -> None:
        desc = ModelDescriptor(
            model_id="reasoning-slm",
            tier=ModelTier.SLM_MEDIUM,
            is_local=True,
            supported_complexities=(
                TaskComplexity.REASONING,
                TaskComplexity.PLANNING,
            ),
        )
        provider = _CustomDescriptorProvider(descriptor=desc)
        assert provider.descriptor == desc
        assert provider.is_local is True
        assert provider.can_handle_complexity(TaskComplexity.REASONING) is True
        assert provider.can_handle_complexity(TaskComplexity.PLANNING) is True
        assert provider.can_handle_complexity(TaskComplexity.EXTRACTION) is False


# ==========================================================================
# Concrete Providers: MockProvider & OpenRouterProvider
# ==========================================================================


class TestConcreteProviderDescriptors:
    """Verify MockProvider and OpenRouterProvider descriptors."""

    def test_mock_provider_default_descriptor(self) -> None:
        mock = MockProvider()
        assert mock.descriptor is not None
        assert mock.descriptor.model_id == "mock-model-v1"
        assert mock.descriptor.tier == ModelTier.SLM_SMALL
        assert mock.descriptor.is_local is True
        assert mock.is_local is True
        assert mock.descriptor.metadata.get("is_mock") is True
        # Mock handles all complexities
        for complexity in TaskComplexity:
            assert mock.can_handle_complexity(complexity) is True

    def test_mock_provider_custom_descriptor(self) -> None:
        custom_desc = ModelDescriptor(
            model_id="custom-mock",
            tier=ModelTier.SLM_MEDIUM,
            is_local=False,
            supported_complexities=(TaskComplexity.CLASSIFICATION,),
        )
        mock = MockProvider(descriptor=custom_desc)
        assert mock.descriptor == custom_desc
        assert mock.is_local is False
        assert mock.can_handle_complexity(TaskComplexity.CLASSIFICATION) is True
        assert mock.can_handle_complexity(TaskComplexity.PLANNING) is False

    def test_openrouter_provider_default_descriptor(self) -> None:
        orp = OpenRouterProvider(api_key="test-key")
        assert orp.descriptor is not None
        assert orp.descriptor.tier == ModelTier.LLM_LARGE
        assert orp.descriptor.is_local is False
        assert orp.is_local is False
        # Cloud LLM handles all complexities
        for complexity in TaskComplexity:
            assert orp.can_handle_complexity(complexity) is True

    def test_openrouter_provider_custom_descriptor(self) -> None:
        custom_desc = ModelDescriptor(
            model_id="custom-openrouter",
            tier=ModelTier.LLM_LARGE,
            is_local=False,
            supported_complexities=(TaskComplexity.REASONING,),
        )
        orp = OpenRouterProvider(api_key="test-key", descriptor=custom_desc)
        assert orp.descriptor == custom_desc
        assert orp.can_handle_complexity(TaskComplexity.REASONING) is True
        assert orp.can_handle_complexity(TaskComplexity.EXTRACTION) is False

