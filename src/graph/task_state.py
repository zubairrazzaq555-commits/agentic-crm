"""State schemas and mapping utilities for task execution workflows in LangGraph."""

from __future__ import annotations

from typing import Any, Dict, Optional, TypedDict


class TaskExecutionState(TypedDict, total=False):
    """LangGraph state representation for executing a CRM task.

    Attributes:
        task_id: Unique task identifier from the persistent task queue.
        task_type: Short string categorizing the task (e.g. "qualify_lead").
        input_payload: Deserialized payload dict from the task record.
        selected_provider: Name of the provider to use for generation.
        prompt: Formatted prompt string passed to the provider.
        generated_output: Text output returned by the provider.
        provider_result: Serialized ProviderResult metadata dict.
        execution_status: Final graph execution status ("SUCCESS" or "FAILED").
        error_message: Error description if execution failed.
        step: Step counter incremented during graph execution.
    """

    task_id: str
    task_type: str
    input_payload: Dict[str, Any]
    selected_provider: str
    prompt: str
    generated_output: str
    provider_result: Optional[Dict[str, Any]]
    execution_status: str
    error_message: Optional[str]
    step: int


def task_to_graph_state(
    task: Dict[str, Any],
    default_provider: str = "mock",
) -> TaskExecutionState:
    """Map a task dictionary from the database into a TaskExecutionState.

    Args:
        task: Dict returned by `get_task()` or `dequeue_task()`.
        default_provider: Provider name to fall back on if not in payload.

    Returns:
        Initialized TaskExecutionState dictionary.
    """
    payload = task.get("payload")
    if not isinstance(payload, dict):
        payload_dict: Dict[str, Any] = {"raw_payload": payload} if payload is not None else {}
    else:
        payload_dict = payload

    # Determine prompt: prioritize explicit 'prompt' field in payload,
    # otherwise construct deterministic representation from task_type and payload
    if "prompt" in payload_dict and isinstance(payload_dict["prompt"], str):
        prompt = payload_dict["prompt"]
    else:
        prompt = f"Execute {task.get('task_type')}: {payload_dict}"

    selected_provider = str(payload_dict.get("provider", default_provider))

    return {
        "task_id": str(task.get("id", "")),
        "task_type": str(task.get("task_type", "")),
        "input_payload": payload_dict,
        "selected_provider": selected_provider,
        "prompt": prompt,
        "generated_output": "",
        "provider_result": None,
        "execution_status": "PENDING",
        "error_message": None,
        "step": 0,
    }


def graph_state_to_task_result(state: TaskExecutionState) -> Dict[str, Any]:
    """Extract a JSON-serializable result dictionary from final graph state.

    Args:
        state: Final TaskExecutionState after graph completion.

    Returns:
        Structured result dict suitable for persisting in the database.
    """
    status = state.get("execution_status", "UNKNOWN")

    if status == "SUCCESS":
        return {
            "status": "success",
            "output": state.get("generated_output", ""),
            "provider": state.get("selected_provider", ""),
            "provider_result": state.get("provider_result"),
            "steps": state.get("step", 0),
        }

    return {
        "status": "failed",
        "error": state.get("error_message", "Unknown error occurred"),
        "provider": state.get("selected_provider", ""),
        "steps": state.get("step", 0),
    }
