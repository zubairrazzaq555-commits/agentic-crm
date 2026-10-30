"""Tests for Grandparent Orchestrator (Phase 4, Milestone 4.1)."""

import pytest
from src.agents.orchestrator import (
    DOMAIN_KEYWORDS,
    GrandparentOrchestrator,
    OrchestratorState,
    SUPPORTED_DOMAINS,
    classifier_node,
    classify_domain,
    create_initial_orchestrator_state,
    create_orchestrator_graph,
    customer_service_handler_node,
    data_handler_node,
    marketing_handler_node,
    route_domain,
    sales_handler_node,
    unknown_handler_node,
)


# =====================================================================
# State & Helpers
# =====================================================================


def test_create_initial_orchestrator_state() -> None:
    state = create_initial_orchestrator_state(
        task_id="task-100",
        task_type="sales_qualification",
        input_payload={"lead_id": 42},
    )
    assert state["task_id"] == "task-100"
    assert state["task_type"] == "sales_qualification"
    assert state["input_payload"] == {"lead_id": 42}
    assert state["classified_domain"] == ""
    assert state["execution_status"] == "PENDING"
    assert state["delegation_result"] is None
    assert state["error_message"] is None
    assert state["step"] == 0


def test_create_initial_orchestrator_state_default_payload() -> None:
    state = create_initial_orchestrator_state("task-101", "unknown_task")
    assert state["input_payload"] == {}
    assert state["step"] == 0


# =====================================================================
# Classifier Unit Tests
# =====================================================================


@pytest.mark.parametrize(
    ("task_type", "payload", "expected_domain"),
    [
        # Direct task_type prefixes
        ("sales_lead_scoring", {}, "sales"),
        ("marketing_newsletter", {}, "marketing"),
        ("customer_service_complaint", {}, "customer_service"),
        ("support_ticket_routing", {}, "customer_service"),
        ("data_export_csv", {}, "data"),
        # Pure keyword matching in task_type
        ("deal_negotiation", {}, "sales"),
        ("email_blast_promo", {}, "marketing"),
        ("refund_request", {}, "customer_service"),
        ("warehouse_cleanup", {}, "data"),
        # Keyword matching in payload fields
        ("generic_task", {"description": "Review new quote proposal for enterprise deal"}, "sales"),
        ("generic_task", {"content": "Launch summer campaign audience promotion"}, "marketing"),
        ("generic_task", {"subject": "Customer inquiry regarding billing ticket"}, "customer_service"),
        ("generic_task", {"action": "Run ETL sync and dedup migration"}, "data"),
        # Explicit domain override in payload
        ("arbitrary_job", {"target_domain": "sales"}, "sales"),
        ("arbitrary_job", {"domain": "marketing"}, "marketing"),
        ("arbitrary_job", {"target_domain": "customer_service"}, "customer_service"),
        ("arbitrary_job", {"domain": "data"}, "data"),
        # Fallbacks to unknown
        ("completely_unknown_action", {}, "unknown"),
        ("", {}, "unknown"),
        ("hello_world", {"action": "do_something_random"}, "unknown"),
    ],
)
def test_classify_domain(task_type: str, payload: dict, expected_domain: str) -> None:
    result = classify_domain(task_type, payload)
    assert result == expected_domain


def test_classifier_node_updates_state() -> None:
    initial_state = create_initial_orchestrator_state(
        task_id="t-1",
        task_type="lead_qualification",
    )
    update = classifier_node(initial_state)
    assert update["classified_domain"] == "sales"
    assert update["step"] == 1


def test_route_domain() -> None:
    state: OrchestratorState = {
        "task_id": "t-1",
        "task_type": "sales",
        "input_payload": {},
        "classified_domain": "sales",
        "execution_status": "PENDING",
        "delegation_result": None,
        "error_message": None,
        "step": 1,
    }
    assert route_domain(state) == "sales"

    empty_state: OrchestratorState = {
        "task_id": "t-2",
        "task_type": "none",
        "input_payload": {},
        "classified_domain": "",
        "execution_status": "PENDING",
        "delegation_result": None,
        "error_message": None,
        "step": 1,
    }
    # Empty string or missing domain routes to unknown
    assert route_domain(empty_state) == "" or route_domain(empty_state) == "unknown"


# =====================================================================
# Domain Handler Unit Tests
# =====================================================================


def test_sales_handler_node() -> None:
    state = create_initial_orchestrator_state("t-s", "sales_deal", {"amount": 5000})
    result = sales_handler_node(state)
    assert result["execution_status"] == "SUCCESS"
    assert result["step"] == 1
    delegation = result["delegation_result"]
    assert delegation["domain"] == "sales"
    assert delegation["handler"] == "sales_handler_node"
    assert delegation["delegation_status"] == "DELEGATED"
    assert delegation["task_id"] == "t-s"


def test_marketing_handler_node() -> None:
    state = create_initial_orchestrator_state("t-m", "campaign_launch")
    result = marketing_handler_node(state)
    assert result["execution_status"] == "SUCCESS"
    delegation = result["delegation_result"]
    assert delegation["domain"] == "marketing"
    assert delegation["delegation_status"] == "DELEGATED"


def test_customer_service_handler_node() -> None:
    state = create_initial_orchestrator_state("t-c", "support_ticket")
    result = customer_service_handler_node(state)
    assert result["execution_status"] == "SUCCESS"
    delegation = result["delegation_result"]
    assert delegation["domain"] == "customer_service"
    assert delegation["delegation_status"] == "DELEGATED"


def test_data_handler_node() -> None:
    state = create_initial_orchestrator_state("t-d", "data_sync")
    result = data_handler_node(state)
    assert result["execution_status"] == "SUCCESS"
    delegation = result["delegation_result"]
    assert delegation["domain"] == "data"
    assert delegation["delegation_status"] == "DELEGATED"


def test_unknown_handler_node() -> None:
    state = create_initial_orchestrator_state("t-u", "mystery_task")
    result = unknown_handler_node(state)
    assert result["execution_status"] == "SUCCESS"
    delegation = result["delegation_result"]
    assert delegation["domain"] == "unknown"
    assert delegation["delegation_status"] == "UNRESOLVED"


# =====================================================================
# LangGraph Execution & Routing Tests
# =====================================================================


@pytest.mark.parametrize(
    ("task_type", "payload", "expected_domain", "expected_handler"),
    [
        ("sales_pipeline_audit", {}, "sales", "sales_handler_node"),
        ("marketing_campaign_blast", {}, "marketing", "marketing_handler_node"),
        ("customer_service_escalation", {}, "customer_service", "customer_service_handler_node"),
        ("data_dedup_migration", {}, "data", "data_handler_node"),
        ("unrecognized_operation_foo", {}, "unknown", "unknown_handler_node"),
    ],
)
def test_orchestrator_graph_routing(
    task_type: str,
    payload: dict,
    expected_domain: str,
    expected_handler: str,
) -> None:
    graph = create_orchestrator_graph()
    initial_state = create_initial_orchestrator_state("test-task-1", task_type, payload)

    final_state = graph.invoke(initial_state)

    assert final_state["classified_domain"] == expected_domain
    assert final_state["execution_status"] == "SUCCESS"
    assert final_state["step"] == 2  # 1 (classifier) + 1 (handler)
    assert final_state["delegation_result"] is not None
    assert final_state["delegation_result"]["domain"] == expected_domain
    assert final_state["delegation_result"]["handler"] == expected_handler


# =====================================================================
# GrandparentOrchestrator Class Tests
# =====================================================================


def test_grandparent_orchestrator_sync_execution() -> None:
    orchestrator = GrandparentOrchestrator()
    result = orchestrator.execute(
        task_id="orch-101",
        task_type="sales_deal_close",
        input_payload={"deal_value": 100000},
    )

    assert result["task_id"] == "orch-101"
    assert result["classified_domain"] == "sales"
    assert result["execution_status"] == "SUCCESS"
    assert result["step"] == 2
    assert result["delegation_result"]["domain"] == "sales"
    assert result["delegation_result"]["delegation_status"] == "DELEGATED"


@pytest.mark.asyncio
async def test_grandparent_orchestrator_async_execution() -> None:
    orchestrator = GrandparentOrchestrator()
    result = await orchestrator.aexecute(
        task_id="orch-102",
        task_type="support_refund_request",
        input_payload={"ticket_id": "TCK-99"},
    )

    assert result["task_id"] == "orch-102"
    assert result["classified_domain"] == "customer_service"
    assert result["execution_status"] == "SUCCESS"
    assert result["step"] == 2
    assert result["delegation_result"]["domain"] == "customer_service"
    assert result["delegation_result"]["delegation_status"] == "DELEGATED"


def test_grandparent_orchestrator_fallback_execution() -> None:
    orchestrator = GrandparentOrchestrator()
    result = orchestrator.execute(
        task_id="orch-103",
        task_type="nonexistent_routine",
    )

    assert result["task_id"] == "orch-103"
    assert result["classified_domain"] == "unknown"
    assert result["execution_status"] == "SUCCESS"
    assert result["step"] == 2
    assert result["delegation_result"]["domain"] == "unknown"
    assert result["delegation_result"]["delegation_status"] == "UNRESOLVED"

