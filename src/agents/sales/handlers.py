"""Subdomain handlers for the Sales Domain Agent.

These handlers serve as decoupled placeholders for specific sales subdomains:
- Lead Management: intake, qualification, enrichment, routing
- Opportunity Management: pipeline stage advancement, forecasting
- Deal Management: quotes, contracts, pricing, closing
- General Sales: catch-all for broad sales reporting and metrics
"""

from typing import Any, Dict

from src.agents.sales.state import SalesAgentState


def _build_handler_result(
    category: str,
    handler_name: str,
    state: SalesAgentState,
    details: str,
) -> Dict[str, Any]:
    """Helper to build consistent subdomain handler result dictionaries."""
    return {
        "category": category,
        "handler": handler_name,
        "status": "COMPLETED",
        "task_id": state.get("task_id", ""),
        "task_type": state.get("task_type", ""),
        "input_payload": state.get("input_payload", {}),
        "details": details,
    }


def lead_management_handler(state: SalesAgentState) -> Dict[str, Any]:
    """Handler for lead intake, qualification, and routing."""
    step = state.get("step", 0)
    result = _build_handler_result(
        category="lead_management",
        handler_name="lead_management_handler",
        state=state,
        details="Lead processed successfully by Lead Management Handler.",
    )
    return {
        "execution_status": "SUCCESS",
        "handler_result": result,
        "step": step + 1,
    }


def opportunity_management_handler(state: SalesAgentState) -> Dict[str, Any]:
    """Handler for pipeline, stages, and sales forecasting."""
    step = state.get("step", 0)
    result = _build_handler_result(
        category="opportunity_management",
        handler_name="opportunity_management_handler",
        state=state,
        details="Opportunity processed successfully by Opportunity Management Handler.",
    )
    return {
        "execution_status": "SUCCESS",
        "handler_result": result,
        "step": step + 1,
    }


def deal_management_handler(state: SalesAgentState) -> Dict[str, Any]:
    """Handler for quotes, proposals, contracts, and negotiation."""
    step = state.get("step", 0)
    result = _build_handler_result(
        category="deal_management",
        handler_name="deal_management_handler",
        state=state,
        details="Deal processed successfully by Deal Management Handler.",
    )
    return {
        "execution_status": "SUCCESS",
        "handler_result": result,
        "step": step + 1,
    }


def general_sales_handler(state: SalesAgentState) -> Dict[str, Any]:
    """Fallback handler for broad sales operations and reporting."""
    step = state.get("step", 0)
    result = _build_handler_result(
        category="general_sales",
        handler_name="general_sales_handler",
        state=state,
        details="Task processed by General Sales Handler.",
    )
    return {
        "execution_status": "SUCCESS",
        "handler_result": result,
        "step": step + 1,
    }

