"""Domain handler nodes for the Grandparent Orchestrator.

These nodes represent lightweight, decoupled domain-level placeholders.
In future milestones (e.g. Phase 4.2+), these can delegate to dedicated
sub-graphs or domain agent workers.
"""

from typing import Any, Dict, Optional

from src.agents.orchestrator.state import OrchestratorState
from src.agents.sales.agent import SalesDomainAgent


def _build_delegation_payload(
    domain: str,
    handler_name: str,
    status: str,
    state: OrchestratorState,
    details: str,
) -> Dict[str, Any]:
    """Helper to build consistent delegation result dictionaries."""
    return {
        "domain": domain,
        "handler": handler_name,
        "delegation_status": status,
        "task_id": state.get("task_id", ""),
        "task_type": state.get("task_type", ""),
        "input_payload": state.get("input_payload", {}),
        "details": details,
    }


def sales_handler_node(
    state: OrchestratorState,
    sales_agent: Optional[SalesDomainAgent] = None,
) -> Dict[str, Any]:
    """Domain Handler: Dispatches sales tasks to the Sales Domain Agent."""
    step = state.get("step", 0)
    agent = sales_agent or SalesDomainAgent()
    sales_result = agent.execute(
        task_id=state.get("task_id", ""),
        task_type=state.get("task_type", ""),
        input_payload=state.get("input_payload", {}),
    )
    delegation = _build_delegation_payload(
        domain="sales",
        handler_name="sales_handler_node",
        status="DELEGATED",
        state=state,
        details="Task successfully delegated to Sales Agent.",
    )
    delegation["sales_agent_result"] = sales_result
    return {
        "execution_status": "SUCCESS",
        "delegation_result": delegation,
        "step": step + 1,
    }


def marketing_handler_node(state: OrchestratorState) -> Dict[str, Any]:
    """Domain Handler: Dispatches marketing tasks (campaigns, newsletters, ads)."""
    step = state.get("step", 0)
    delegation = _build_delegation_payload(
        domain="marketing",
        handler_name="marketing_handler_node",
        status="DELEGATED",
        state=state,
        details="Task successfully delegated to Marketing Agent.",
    )
    return {
        "execution_status": "SUCCESS",
        "delegation_result": delegation,
        "step": step + 1,
    }


def customer_service_handler_node(state: OrchestratorState) -> Dict[str, Any]:
    """Domain Handler: Dispatches service tasks (tickets, support, inquiries)."""
    step = state.get("step", 0)
    delegation = _build_delegation_payload(
        domain="customer_service",
        handler_name="customer_service_handler_node",
        status="DELEGATED",
        state=state,
        details="Task successfully delegated to Customer Service Agent.",
    )
    return {
        "execution_status": "SUCCESS",
        "delegation_result": delegation,
        "step": step + 1,
    }


def data_handler_node(state: OrchestratorState) -> Dict[str, Any]:
    """Domain Handler: Dispatches data tasks (import/export, cleanup, sync)."""
    step = state.get("step", 0)
    delegation = _build_delegation_payload(
        domain="data",
        handler_name="data_handler_node",
        status="DELEGATED",
        state=state,
        details="Task successfully delegated to Data Agent.",
    )
    return {
        "execution_status": "SUCCESS",
        "delegation_result": delegation,
        "step": step + 1,
    }


def unknown_handler_node(state: OrchestratorState) -> Dict[str, Any]:
    """Fallback Handler: Handles unclassified or unrecognized tasks."""
    step = state.get("step", 0)
    delegation = _build_delegation_payload(
        domain="unknown",
        handler_name="unknown_handler_node",
        status="UNRESOLVED",
        state=state,
        details="Task domain could not be identified; dispatched to general fallback handler.",
    )
    return {
        "execution_status": "SUCCESS",
        "delegation_result": delegation,
        "step": step + 1,
    }

