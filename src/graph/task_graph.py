"""Task execution graph wired to ProviderManager.

Topology:
    START -> prepare_node -> execute_provider_node -> END

Connects LangGraph state flow directly to the provider abstraction layer.
"""

from __future__ import annotations

import logging
from typing import Any, Dict
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from src.graph.task_state import TaskExecutionState
from src.providers.exceptions import ProviderError, ProviderNotFoundError
from src.providers.manager import ProviderManager

logger = logging.getLogger("agentic_crm.graph.task_graph")


def create_task_graph(provider_manager: ProviderManager) -> CompiledStateGraph:
    """Construct, connect, and compile a task execution graph.

    Args:
        provider_manager: Initialized ProviderManager instance containing
            registered providers and health tracking.

    Returns:
        CompiledStateGraph ready for async invocation with `TaskExecutionState`.
    """

    async def prepare_node(state: TaskExecutionState) -> Dict[str, Any]:
        """Prepare task state and ensure prompt and default fields are populated."""
        current_step = state.get("step", 0)
        prompt = state.get("prompt", "")
        if not prompt:
            prompt = f"Process {state.get('task_type', 'unknown')}: {state.get('input_payload', {})}"

        return {
            "prompt": prompt,
            "generated_output": state.get("generated_output", ""),
            "error_message": state.get("error_message", None),
            "provider_result": state.get("provider_result", None),
            "execution_status": state.get("execution_status", "PENDING"),
            "step": current_step + 1,
        }

    async def execute_provider_node(state: TaskExecutionState) -> Dict[str, Any]:
        """Obtain provider from ProviderManager, execute generation, and capture results."""
        current_step = state.get("step", 0)
        provider_name = state.get("selected_provider", "")
        prompt = state.get("prompt", "")

        # 1. Check if provider is registered
        if not provider_manager.has_provider(provider_name):
            err = f"Provider {provider_name!r} is not registered"
            logger.warning(err)
            return {
                "execution_status": "FAILED",
                "error_message": err,
                "step": current_step + 1,
            }

        # 2. Check if provider is available (health status & circuit breaker)
        if not provider_manager.is_available(provider_name):
            err = f"Provider {provider_name!r} is currently unavailable or circuit is open"
            logger.warning(err)
            return {
                "execution_status": "FAILED",
                "error_message": err,
                "step": current_step + 1,
            }

        # 3. Retrieve provider and execute async generation
        try:
            provider = provider_manager.get_provider(provider_name)
            result = await provider.generate(prompt)

            # Record success with ProviderManager
            provider_manager.record_success(provider_name)

            return {
                "generated_output": result.text,
                "provider_result": {
                    "text": result.text,
                    "provider_name": result.provider_name,
                    "model": result.model,
                    "prompt_tokens": result.prompt_tokens,
                    "completion_tokens": result.completion_tokens,
                    "total_tokens": result.total_tokens,
                    "latency_ms": result.latency_ms,
                    "metadata": result.metadata,
                },
                "execution_status": "SUCCESS",
                "error_message": None,
                "step": current_step + 1,
            }

        except (ProviderError, Exception) as exc:
            logger.error("Generation failed on provider %r: %s", provider_name, exc)
            # Record failure with ProviderManager to update circuit breaker
            try:
                provider_manager.record_failure(provider_name)
            except ProviderNotFoundError:
                pass

            return {
                "execution_status": "FAILED",
                "error_message": str(exc),
                "step": current_step + 1,
            }

    builder = StateGraph(TaskExecutionState)
    builder.add_node("prepare", prepare_node)
    builder.add_node("execute_provider", execute_provider_node)

    builder.add_edge(START, "prepare")
    builder.add_edge("prepare", "execute_provider")
    builder.add_edge("execute_provider", END)

    return builder.compile()
