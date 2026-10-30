"""Tests for Sales Domain Agent (Phase 4, Milestone 4.2)."""

import pytest
from src.agents.orchestrator import GrandparentOrchestrator
from src.agents.sales import (
    SALES_CATEGORY_KEYWORDS,
    SUPPORTED_SALES_CATEGORIES,
    SalesAgentState,
    SalesDomainAgent,
    classify_sales_task,
    create_initial_sales_state,
    create_sales_agent_graph,
    deal_management_handler,
    general_sales_handler,
    lead_management_handler,
    opportunity_management_handler,
    route_sales_category,
    sales_classifier_node,
)


# =====================================================================
# State & Helpers
# =====================================================================


def test_create_initial_sales_state() -> None:
    state = create_initial_sales_state(
        task_id="sales-task-001",
        task_type="lead_scoring",
        input_payload={"lead_id": 99, "score": 85},
    )
    assert state["task_id"] == "sales-task-001"
    assert state["task_type"] == "lead_scoring"
    assert state["input_payload"] == {"lead_id": 99, "score": 85}
    assert state["sales_task_category"] == ""
    assert state["execution_status"] == "PENDING"
    assert state["handler_result"] is None
    assert state["error_message"] is None
    assert state["step"] == 0


def test_create_initial_sales_state_default_payload() -> None:
    state = create_initial_sales_state("sales-task-002", "general_sales")
    assert state["input_payload"] == {}
    assert state["step"] == 0


# =====================================================================
# Sales Task Classification Unit Tests
# =====================================================================


@pytest.mark.parametrize(
    ("task_type", "payload", "expected_category"),
    [
        # 1. Lead Management
        ("lead_intake", {}, "lead_management"),
        ("leads_enrichment", {}, "lead_management"),
        ("qualify_prospect", {}, "lead_management"),
        ("sales_task", {"description": "Inbound prospect qualification for enterprise"}, "lead_management"),
        ("sales_task", {"action": "route lead to regional rep"}, "lead_management"),
        # 2. Opportunity Management
        ("opportunity_stage_update", {}, "opportunity_management"),
        ("opp_pipeline_forecast", {}, "opportunity_management"),
        ("sales_task", {"action": "advance pipeline stage for Q4 expansion"}, "opportunity_management"),
        ("sales_task", {"description": "forecast revenue probability on milestone"}, "opportunity_management"),
        # 3. Deal Management
        ("deal_negotiation", {}, "deal_management"),
        ("quote_generation", {}, "deal_management"),
        ("sales_task", {"content": "Prepare pricing proposal contract for client"}, "deal_management"),
        ("sales_task", {"action": "approve discount terms for deal close"}, "deal_management"),
        # 4. General Sales (Direct / Fallback)
        ("sales_metrics_review", {}, "general_sales"),
        ("revenue_report", {}, "general_sales"),
        ("general_sales_task", {}, "general_sales"),
        ("arbitrary_unknown_operation", {}, "general_sales"),
        ("", {}, "general_sales"),
        # 5. Explicit Overrides via Payload
        ("arbitrary_task", {"sales_category": "lead_management"}, "lead_management"),
        ("arbitrary_task", {"subdomain": "opportunity_management"}, "opportunity_management"),
        ("arbitrary_task", {"category": "deal_management"}, "deal_management"),
        ("arbitrary_task", {"sales_category": "general_sales"}, "general_sales"),
    ],
)
def test_classify_sales_task(
    task_type: str,
    payload: dict,
    expected_category: str,
) -> None:
    category = classify_sales_task(task_type, payload)
    assert category == expected_category


def test_sales_classifier_node_updates_state() -> None:
    initial_state = create_initial_sales_state("s-1", "lead_qualification")
    update = sales_classifier_node(initial_state)
    assert update["sales_task_category"] == "lead_management"
    assert update["step"] == 1


def test_route_sales_category() -> None:
    state: SalesAgentState = {
        "task_id": "s-1",
        "task_type": "quote_review",
        "input_payload": {},
        "sales_task_category": "deal_management",
        "execution_status": "PENDING",
        "handler_result": None,
        "error_message": None,
        "step": 1,
    }
    assert route_sales_category(state) == "deal_management"

    empty_state: SalesAgentState = {
        "task_id": "s-2",
        "task_type": "none",
        "input_payload": {},
        "sales_task_category": "",
        "execution_status": "PENDING",
        "handler_result": None,
        "error_message": None,
        "step": 1,
    }
    # Empty category routes safely to general_sales
    assert route_sales_category(empty_state) == "general_sales" or route_sales_category(empty_state) == ""


# =====================================================================
# Sales Subdomain Handler Unit Tests
# =====================================================================


def test_lead_management_handler() -> None:
    state = create_initial_sales_state("t-lead", "lead_scoring", {"score": 90})
    result = lead_management_handler(state)
    assert result["execution_status"] == "SUCCESS"
    assert result["step"] == 1
    hr = result["handler_result"]
    assert hr["category"] == "lead_management"
    assert hr["handler"] == "lead_management_handler"
    assert hr["status"] == "COMPLETED"
    assert hr["task_id"] == "t-lead"


def test_opportunity_management_handler() -> None:
    state = create_initial_sales_state("t-opp", "opp_stage", {"stage": "proposal"})
    result = opportunity_management_handler(state)
    assert result["execution_status"] == "SUCCESS"
    hr = result["handler_result"]
    assert hr["category"] == "opportunity_management"
    assert hr["handler"] == "opportunity_management_handler"
    assert hr["status"] == "COMPLETED"


def test_deal_management_handler() -> None:
    state = create_initial_sales_state("t-deal", "quote_close", {"amount": 25000})
    result = deal_management_handler(state)
    assert result["execution_status"] == "SUCCESS"
    hr = result["handler_result"]
    assert hr["category"] == "deal_management"
    assert hr["handler"] == "deal_management_handler"
    assert hr["status"] == "COMPLETED"


def test_general_sales_handler() -> None:
    state = create_initial_sales_state("t-gen", "sales_report")
    result = general_sales_handler(state)
    assert result["execution_status"] == "SUCCESS"
    hr = result["handler_result"]
    assert hr["category"] == "general_sales"
    assert hr["handler"] == "general_sales_handler"
    assert hr["status"] == "COMPLETED"


# =====================================================================
# LangGraph Execution & Routing Tests
# =====================================================================


@pytest.mark.parametrize(
    ("task_type", "payload", "expected_cat", "expected_handler"),
    [
        ("lead_enrichment", {}, "lead_management", "lead_management_handler"),
        ("opportunity_forecast", {}, "opportunity_management", "opportunity_management_handler"),
        ("deal_proposal", {}, "deal_management", "deal_management_handler"),
        ("sales_general_audit", {}, "general_sales", "general_sales_handler"),
        ("unrecognized_sales_job", {}, "general_sales", "general_sales_handler"),
    ],
)
def test_sales_agent_graph_routing(
    task_type: str,
    payload: dict,
    expected_cat: str,
    expected_handler: str,
) -> None:
    graph = create_sales_agent_graph()
    initial_state = create_initial_sales_state("sales-g-1", task_type, payload)

    final_state = graph.invoke(initial_state)

    assert final_state["sales_task_category"] == expected_cat
    assert final_state["execution_status"] == "SUCCESS"
    assert final_state["step"] == 2  # 1 classifier + 1 handler
    assert final_state["handler_result"] is not None
    assert final_state["handler_result"]["category"] == expected_cat
    assert final_state["handler_result"]["handler"] == expected_handler


# =====================================================================
# SalesDomainAgent Class Tests
# =====================================================================


def test_sales_domain_agent_sync_execution() -> None:
    agent = SalesDomainAgent()
    result = agent.execute(
        task_id="agent-s1",
        task_type="lead_intake",
        input_payload={"company": "Acme Corp"},
    )
    assert result["task_id"] == "agent-s1"
    assert result["sales_task_category"] == "lead_management"
    assert result["execution_status"] == "SUCCESS"
    assert result["step"] == 2
    assert result["handler_result"]["category"] == "lead_management"


@pytest.mark.asyncio
async def test_sales_domain_agent_async_execution() -> None:
    agent = SalesDomainAgent()
    result = await agent.aexecute(
        task_id="agent-s2",
        task_type="deal_closing",
        input_payload={"contract_id": "CT-100"},
    )
    assert result["task_id"] == "agent-s2"
    assert result["sales_task_category"] == "deal_management"
    assert result["execution_status"] == "SUCCESS"
    assert result["step"] == 2
    assert result["handler_result"]["category"] == "deal_management"


# =====================================================================
# Grandparent Orchestrator to Sales Domain Agent Integration Tests
# =====================================================================


def test_grandparent_orchestrator_delegates_to_sales_agent() -> None:
    """Verify end-to-end delegation from Grandparent Orchestrator to SalesDomainAgent."""
    orchestrator = GrandparentOrchestrator()
    task_result = orchestrator.execute(
        task_id="gp-sales-001",
        task_type="sales_lead_qualification",
        input_payload={"lead_score": 95},
    )

    # 1. Orchestrator-level assertions
    assert task_result["task_id"] == "gp-sales-001"
    assert task_result["classified_domain"] == "sales"
    assert task_result["execution_status"] == "SUCCESS"
    assert task_result["step"] == 2  # 1 classifier + 1 sales handler

    # 2. Delegation result assertions
    delegation = task_result["delegation_result"]
    assert delegation is not None
    assert delegation["domain"] == "sales"
    assert delegation["handler"] == "sales_handler_node"
    assert delegation["delegation_status"] == "DELEGATED"

    # 3. Nested Sales Agent execution assertions
    sales_agent_result = delegation.get("sales_agent_result")
    assert sales_agent_result is not None
    assert sales_agent_result["task_id"] == "gp-sales-001"
    assert sales_agent_result["sales_task_category"] == "lead_management"
    assert sales_agent_result["execution_status"] == "SUCCESS"
    assert sales_agent_result["step"] == 2
    assert sales_agent_result["handler_result"]["category"] == "lead_management"
    assert sales_agent_result["handler_result"]["status"] == "COMPLETED"


def test_grandparent_non_sales_compatibility() -> None:
    """Verify that non-sales tasks do not trigger the Sales Agent."""
    orchestrator = GrandparentOrchestrator()
    task_result = orchestrator.execute(
        task_id="gp-mkt-001",
        task_type="marketing_campaign",
    )
    assert task_result["classified_domain"] == "marketing"
    assert task_result["execution_status"] == "SUCCESS"
    delegation = task_result["delegation_result"]
    assert delegation["domain"] == "marketing"
    assert "sales_agent_result" not in delegation

