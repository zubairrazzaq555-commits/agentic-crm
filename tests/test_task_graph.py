"""Focused tests for LangGraph Task Execution Graph (Milestone 3.3).

Verifies:
1. Task dictionary mapping to TaskExecutionState
2. Graph state extraction into task result dictionary
3. Graph execution through ProviderManager with MockProvider
4. Structured error handling for missing, unavailable, and failing providers
"""

from __future__ import annotations

import pytest
from langgraph.graph.state import CompiledStateGraph

from src.graph.task_graph import create_task_graph
from src.graph.task_state import (
    graph_state_to_task_result,
    task_to_graph_state,
)
from src.providers.manager import ProviderManager
from src.providers.mock_provider import MockProvider


def test_task_state_mapping() -> None:
    """Verify task dictionary converts cleanly to TaskExecutionState and back to result."""
    task_dict = {
        "id": "test-task-123",
        "task_type": "qualify_lead",
        "payload": {"company": "Acme Corp", "score": 85, "prompt": "Qualify lead Acme"},
        "status": "pending",
    }

    state = task_to_graph_state(task_dict, default_provider="mock_llm")

    assert state["task_id"] == "test-task-123"
    assert state["task_type"] == "qualify_lead"
    assert state["prompt"] == "Qualify lead Acme"
    assert state["selected_provider"] == "mock_llm"
    assert state["execution_status"] == "PENDING"
    assert state["step"] == 0

    # Test conversion of success state to task result
    state["execution_status"] = "SUCCESS"
    state["generated_output"] = "Lead Acme is qualified"
    state["provider_result"] = {"tokens": 15}
    state["step"] = 2

    success_result = graph_state_to_task_result(state)
    assert success_result["status"] == "success"
    assert success_result["output"] == "Lead Acme is qualified"
    assert success_result["provider"] == "mock_llm"
    assert success_result["steps"] == 2

    # Test conversion of failed state to task result
    state["execution_status"] = "FAILED"
    state["error_message"] = "Connection refused"

    failed_result = graph_state_to_task_result(state)
    assert failed_result["status"] == "failed"
    assert failed_result["error"] == "Connection refused"


@pytest.mark.asyncio
async def test_task_graph_execution_success() -> None:
    """Verify end-to-end task graph execution with MockProvider."""
    pm = ProviderManager(allow_paid=False)
    mock = MockProvider(name="mock_agent", custom_response="QUALIFIED: Acme Corp")
    pm.register(mock)

    graph = create_task_graph(pm)
    assert isinstance(graph, CompiledStateGraph)

    initial_state = {
        "task_id": "task-001",
        "task_type": "lead_analysis",
        "prompt": "Evaluate Acme Corp",
        "selected_provider": "mock_agent",
        "input_payload": {"company": "Acme Corp"},
    }

    final_state = await graph.ainvoke(initial_state)

    assert final_state["execution_status"] == "SUCCESS"
    assert final_state["generated_output"] == "QUALIFIED: Acme Corp"
    assert final_state["error_message"] is None
    assert final_state["step"] == 2
    assert final_state["provider_result"] is not None
    assert final_state["provider_result"]["provider_name"] == "mock_agent"
    assert final_state["provider_result"]["model"] == "mock-model-v1"


@pytest.mark.asyncio
async def test_task_graph_missing_provider_handling() -> None:
    """Verify structured failure when the requested provider is not registered."""
    pm = ProviderManager(allow_paid=False)
    graph = create_task_graph(pm)

    initial_state = {
        "task_id": "task-002",
        "task_type": "lead_analysis",
        "prompt": "Evaluate Acme Corp",
        "selected_provider": "nonexistent_provider",
    }

    final_state = await graph.ainvoke(initial_state)

    assert final_state["execution_status"] == "FAILED"
    assert "not registered" in str(final_state["error_message"])
    assert final_state["generated_output"] == ""


@pytest.mark.asyncio
async def test_task_graph_provider_unavailable_handling() -> None:
    """Verify structured failure when provider is marked unavailable."""
    pm = ProviderManager(allow_paid=False)
    mock = MockProvider(name="mock_offline", available=False)
    pm.register(mock)
    pm.mark_unavailable("mock_offline")

    graph = create_task_graph(pm)

    initial_state = {
        "task_id": "task-003",
        "task_type": "lead_analysis",
        "prompt": "Evaluate Acme Corp",
        "selected_provider": "mock_offline",
    }

    final_state = await graph.ainvoke(initial_state)

    assert final_state["execution_status"] == "FAILED"
    assert "unavailable" in str(final_state["error_message"]).lower()


@pytest.mark.asyncio
async def test_task_graph_provider_failure_handling() -> None:
    """Verify error propagation and circuit breaker failure recording on provider error."""
    pm = ProviderManager(allow_paid=False)
    mock = MockProvider(name="mock_failing", simulate_failure=True)
    pm.register(mock)

    graph = create_task_graph(pm)

    initial_state = {
        "task_id": "task-004",
        "task_type": "lead_analysis",
        "prompt": "Evaluate Acme Corp",
        "selected_provider": "mock_failing",
    }

    final_state = await graph.ainvoke(initial_state)

    assert final_state["execution_status"] == "FAILED"
    assert "Simulated mock provider failure" in str(final_state["error_message"])

    # Circuit breaker should have recorded the failure
    cb = pm.get_circuit_breaker("mock_failing")
    assert cb.consecutive_failures == 1
