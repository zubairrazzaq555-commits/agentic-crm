"""State definitions for the Sales Domain Agent."""

from typing import Any, Dict, Optional, TypedDict

SUPPORTED_SALES_CATEGORIES = (
    "lead_management",
    "opportunity_management",
    "deal_management",
    "general_sales",
)


class SalesAgentState(TypedDict, total=False):
    """Execution state schema for the Sales Domain Agent graph."""

    task_id: str
    task_type: str
    input_payload: Dict[str, Any]
    sales_task_category: str
    execution_status: str
    handler_result: Optional[Dict[str, Any]]
    error_message: Optional[str]
    step: int


def create_initial_sales_state(
    task_id: str,
    task_type: str,
    input_payload: Optional[Dict[str, Any]] = None,
) -> SalesAgentState:
    """Create a validated initial state for the sales agent graph.

    Args:
        task_id: Unique task identifier.
        task_type: Specific sales task type or category string.
        input_payload: Optional dictionary payload carrying task inputs.

    Returns:
        Initialized SalesAgentState.
    """
    return {
        "task_id": task_id,
        "task_type": task_type,
        "input_payload": input_payload if input_payload is not None else {},
        "sales_task_category": "",
        "execution_status": "PENDING",
        "handler_result": None,
        "error_message": None,
        "step": 0,
    }

