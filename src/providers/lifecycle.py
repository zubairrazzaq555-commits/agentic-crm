"""RAM-aware local model lifecycle manager.

Governs local model load/unload states, enforces hardware RAM ceilings,
and manages single-model residency on low-RAM systems.

IMPORTANT LIMITATION NOTICE:
    Model RAM requirements are approximate heuristic estimates based on model
    descriptors. Real-world physical RAM and VRAM usage varies depending on
    quantization format (e.g. Q4_K_M vs Q8_0), context window length, KV cache
    growth, and Ollama server overhead.

    This manager provides approximate memory-budget safety gates to prevent
    obviously oversized models from crashing the system. It does NOT provide
    guaranteed operating-system-level physical RAM enforcement.

    Furthermore, dispatching keep_alive: 0 instructs the Ollama daemon to begin
    eviction. Actual physical operating system memory page deallocation is managed
    asynchronously by the host operating system.
"""

from __future__ import annotations

import asyncio
import logging
from enum import Enum
from typing import Any, Dict, List, Optional

from src.config import HardwareProfile, get_settings
from src.providers.base import ModelDescriptor
from src.providers.exceptions import ProviderError

logger = logging.getLogger("agentic_crm.providers.lifecycle")


class ModelLoadState(str, Enum):
    """Lifecycle state of a local model.

    States:
        UNLOADED: Model is not resident in memory.
        RESERVED: Model slot has been reserved; preparing for loading.
        LOADING:  Model load request has been dispatched to provider.
        LOADED:   Model has been successfully loaded into memory by provider.
        UNLOADING: Model unload request (keep_alive: 0) has been dispatched.
        FAILED:   Model load or unload operation encountered a failure.
    """

    UNLOADED = "unloaded"
    RESERVED = "reserved"
    LOADING = "loading"
    LOADED = "loaded"
    UNLOADING = "unloading"
    FAILED = "failed"


class MemoryBudgetExceededError(ProviderError):
    """Raised when a model's estimated RAM requirement exceeds the configured budget."""

    def __init__(
        self,
        model_name: str,
        required_mb: int,
        budget_mb: int,
        profile: HardwareProfile,
    ) -> None:
        super().__init__(
            f"Model '{model_name}' estimated RAM ({required_mb} MB) exceeds "
            f"hardware budget ({budget_mb} MB) for profile '{profile.value}'."
        )
        self.model_name = model_name
        self.required_mb = required_mb
        self.budget_mb = budget_mb
        self.profile = profile


class ModelLifecycleError(ProviderError):
    """Raised when a model lifecycle state transition or operation fails."""


class ModelLifecycleManager:
    """RAM-aware local model lifecycle manager.

    Coordinates model reservations, lazy loading, single-model residency,
    and eviction for local providers (such as OllamaProvider).

    Decoupled from routing: this manager tracks resource allocation and
    lifecycle states; it does not make routing or task decisions.
    """

    def __init__(
        self,
        profile: Optional[HardwareProfile] = None,
        max_ram_mb: Optional[int] = None,
        default_keep_alive: str = "0",
        allow_multi_model: bool = False,
    ) -> None:
        """Initialize the model lifecycle manager.

        Args:
            profile: Hardware profile override (defaults to settings.resolved_ram_profile).
            max_ram_mb: Model RAM budget ceiling override in MB.
            default_keep_alive: Default keep_alive parameter for loading (default '0').
            allow_multi_model: Whether concurrent model residency is permitted.
                               Initially False for both 8GB and 16GB profiles.
        """
        settings = get_settings()
        self._profile = profile or getattr(settings, "resolved_ram_profile", HardwareProfile.PROFILE_8GB)
        self._budget_mb = max_ram_mb or getattr(settings, "model_ram_budget_mb", 2200)
        self._default_keep_alive = default_keep_alive or getattr(settings, "model_keep_alive", "0")
        self._allow_multi_model = allow_multi_model

        self._lock = asyncio.Lock()
        # model_name -> ModelLoadState
        self._states: Dict[str, ModelLoadState] = {}
        # model_name -> estimated RAM in MB
        self._allocated_mb: Dict[str, int] = {}
        # Currently active model name in single-model residency
        self._active_model: Optional[str] = None

    @property
    def profile(self) -> HardwareProfile:
        """Configured or resolved hardware profile."""
        return self._profile

    @property
    def budget_mb(self) -> int:
        """Configured model RAM budget ceiling in MB."""
        return self._budget_mb

    @property
    def allocated_mb(self) -> int:
        """Approximate total allocated model RAM in MB."""
        return sum(self._allocated_mb.values())

    @property
    def allow_multi_model(self) -> bool:
        """Whether multiple models may be resident concurrently."""
        return self._allow_multi_model

    def get_state(self, model_name: str) -> ModelLoadState:
        """Return the current lifecycle state for a given model."""
        return self._states.get(model_name, ModelLoadState.UNLOADED)

    def get_active_model(self) -> Optional[str]:
        """Return the identifier of the currently active model under single-residency."""
        return self._active_model

    def get_loaded_models(self) -> List[str]:
        """Return a list of all models currently in the LOADED state."""
        return [m for m, s in self._states.items() if s == ModelLoadState.LOADED]

    def get_reserved_models(self) -> List[str]:
        """Return a list of all models currently in the RESERVED state."""
        return [m for m, s in self._states.items() if s == ModelLoadState.RESERVED]

    def is_loaded(self, model_name: str) -> bool:
        """Check whether a model is currently in the LOADED state."""
        return self._states.get(model_name) == ModelLoadState.LOADED

    def is_reserved(self, model_name: str) -> bool:
        """Check whether a model is currently in the RESERVED state."""
        return self._states.get(model_name) == ModelLoadState.RESERVED

    def can_fit_model(self, descriptor: ModelDescriptor) -> bool:
        """Check whether a model's approximate RAM requirement fits within the budget.

        Args:
            descriptor: Model capability and resource descriptor.

        Returns:
            True if estimated RAM requirement is <= budget; False otherwise.
        """
        estimated = descriptor.ram_required_mb or 2048
        return estimated <= self._budget_mb

    async def acquire_model(
        self,
        model_name: str,
        descriptor: Optional[ModelDescriptor] = None,
        provider: Optional[Any] = None,
    ) -> None:
        """Reserve and optionally load a model into memory.

        Enforces budget ceiling and single-model residency.

        Workflow:
            1. Approximate budget validation: raises MemoryBudgetExceededError if model exceeds budget.
            2. Acquisition lock acquired.
            3. If model is already LOADED and active, returns immediately.
            4. If another model is active under single-residency:
               - Marks previously active model as UNLOADING.
               - Dispatches provider.unload_model(previous).
               - On eviction failure: sets previous to FAILED, aborts acquisition without
                 marking target model as active, and raises ModelLifecycleError.
               - On eviction success: marks previous as UNLOADED.
            5. Reserves target model (RESERVED).
            6. If provider is provided:
               - Marks target model as LOADING.
               - Calls provider.load_model(model_name).
               - On loading failure: marks target as FAILED, clears active model,
                 and raises ModelLifecycleError.
               - On loading success: marks target as LOADED.
            7. If provider is None (reservation only): marks target as LOADED.

        Args:
            model_name: Target model identifier.
            descriptor: Optional model descriptor for RAM estimation.
            provider: Optional provider instance (e.g. OllamaProvider) to execute load/unload.

        Raises:
            MemoryBudgetExceededError: If estimated RAM exceeds the budget.
            ModelLifecycleError: If eviction of a previous model or loading of the new model fails.
        """
        estimated_mb = descriptor.ram_required_mb if descriptor and descriptor.ram_required_mb else 2048
        if estimated_mb > self._budget_mb:
            raise MemoryBudgetExceededError(
                model_name=model_name,
                required_mb=estimated_mb,
                budget_mb=self._budget_mb,
                profile=self._profile,
            )

        async with self._lock:
            # Check if already active and loaded/reserved
            current_state = self._states.get(model_name)
            if self._active_model == model_name:
                if current_state == ModelLoadState.LOADED:
                    logger.debug("Model '%s' is already active and LOADED.", model_name)
                    return
                if current_state == ModelLoadState.RESERVED and provider is None:
                    logger.debug("Model '%s' is already active and RESERVED.", model_name)
                    return

            # Single-model residency: evict previously resident or failed model if different
            if not self._allow_multi_model:
                lingering = [
                    m
                    for m, s in self._states.items()
                    if m != model_name
                    and s
                    in (
                        ModelLoadState.LOADED,
                        ModelLoadState.LOADING,
                        ModelLoadState.RESERVED,
                        ModelLoadState.FAILED,
                    )
                ]
                for previous_model in lingering:
                    logger.info(
                        "Single-model residency: evicting model '%s' (state=%s) before acquiring '%s'.",
                        previous_model,
                        self._states[previous_model].value,
                        model_name,
                    )
                    self._states[previous_model] = ModelLoadState.UNLOADING
                    if provider is not None and hasattr(provider, "unload_model"):
                        try:
                            await provider.unload_model(previous_model)
                        except Exception as exc:
                            self._states[previous_model] = ModelLoadState.FAILED
                            self._active_model = None
                            logger.error(
                                "Failed to unload model '%s'. Aborting acquisition of '%s': %s",
                                previous_model,
                                model_name,
                                exc,
                            )
                            raise ModelLifecycleError(
                                f"Failed to evict previously active model '{previous_model}': {exc}"
                            ) from exc

                    # Eviction succeeded
                    self._states[previous_model] = ModelLoadState.UNLOADED
                    self._allocated_mb.pop(previous_model, None)
                    if self._active_model == previous_model:
                        self._active_model = None

            # Phase 1: Reservation
            self._states[model_name] = ModelLoadState.RESERVED
            self._active_model = model_name
            self._allocated_mb[model_name] = estimated_mb

            # Phase 2: Loading (if provider supplied)
            if provider is not None and hasattr(provider, "load_model"):
                self._states[model_name] = ModelLoadState.LOADING
                try:
                    await provider.load_model(model_name, keep_alive=self._default_keep_alive)
                except Exception as exc:
                    self._states[model_name] = ModelLoadState.FAILED
                    self._active_model = None
                    self._allocated_mb.pop(model_name, None)
                    logger.error("Failed to load model '%s': %s", model_name, exc)
                    raise ModelLifecycleError(f"Failed to load model '{model_name}': {exc}") from exc

                # ONLY marked as LOADED after provider.load_model() has actually succeeded!
                self._states[model_name] = ModelLoadState.LOADED
                logger.info("Model '%s' is now in LOADED state (approx. %d MB).", model_name, estimated_mb)
            else:
                logger.info(
                    "Model '%s' reserved in memory budget (approx. %d MB, provider not supplied; state=RESERVED).",
                    model_name,
                    estimated_mb,
                )

    async def release_model(
        self,
        model_name: str,
        provider: Optional[Any] = None,
    ) -> None:
        """Unload a model from memory and update its lifecycle state.

        Args:
            model_name: Target model identifier.
            provider: Optional provider instance to execute unload_model.

        Raises:
            ModelLifecycleError: If the provider unload operation fails.
        """
        async with self._lock:
            current_state = self._states.get(model_name)
            if current_state in (ModelLoadState.UNLOADED, None):
                logger.debug("Model '%s' is already UNLOADED.", model_name)
                return

            self._states[model_name] = ModelLoadState.UNLOADING
            if provider is not None and hasattr(provider, "unload_model"):
                try:
                    await provider.unload_model(model_name)
                except Exception as exc:
                    self._states[model_name] = ModelLoadState.FAILED
                    logger.error("Failed to unload model '%s': %s", model_name, exc)
                    raise ModelLifecycleError(f"Failed to unload model '{model_name}': {exc}") from exc

            self._states[model_name] = ModelLoadState.UNLOADED
            self._allocated_mb.pop(model_name, None)
            if self._active_model == model_name:
                self._active_model = None
            logger.info("Model '%s' is now UNLOADED.", model_name)

    async def evict_all(self, provider: Optional[Any] = None) -> None:
        """Evict all resident models from memory."""
        async with self._lock:
            active_models = [
                m
                for m, s in self._states.items()
                if s
                in (
                    ModelLoadState.LOADED,
                    ModelLoadState.LOADING,
                    ModelLoadState.RESERVED,
                    ModelLoadState.FAILED,
                )
            ]
            for model_name in active_models:
                self._states[model_name] = ModelLoadState.UNLOADING
                if provider is not None and hasattr(provider, "unload_model"):
                    try:
                        await provider.unload_model(model_name)
                    except Exception as exc:
                        self._states[model_name] = ModelLoadState.FAILED
                        logger.warning("Error during evict_all for model '%s': %s", model_name, exc)
                        continue

                self._states[model_name] = ModelLoadState.UNLOADED
                self._allocated_mb.pop(model_name, None)

            self._active_model = None
            logger.info("All active models evicted.")

