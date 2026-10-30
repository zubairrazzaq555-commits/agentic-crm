"""State definitions for the Grandparent Orchestrator."""

from typing import Any, Dict, Optional, TypedDict

SUPPORTED_DOMAINS = (
    "sales",
    "marketing",
    "customer_service",
    "data",
    "unknown",
)


class OrchestratorState(TypedDict, total=False):
    """Execution state schema for the Grandparent Orchestrator graph."""

    task_id: str
    task_type: str
    input_payload: Dict[str, Any]
    classified_domain: str
    execution_status: str
    delegation_result: Optional[Dict[str, Any]]
    error_message: Optional[str]
    step: int


def create_initial_orchestrator_state(
    task_id: str,
    task_type: str,
    input_payload: Optional[Dict[str, Any]] = None,
) -> OrchestratorState:
    """Create a validated initial state for the orchestrator graph.

    Args:
        task_id: Unique task identifier.
        task_type: Type/category string of the task.
        input_payload: Optional dictionary payload carrying task inputs.

    Returns:
        Initialized OrchestratorState.
    """
    return {
        "task_id": task_id,
        "task_type": task_type,
        "input_payload": input_payload if input_payload is not None else {},
        "classified_domain": "",
        "execution_status": "PENDING",
        "delegation_result": None,
        "error_message": None,
        "step": 0,
    }

