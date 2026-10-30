"""Focused unit tests for LangGraph Core & State Patterns (Milestone 3.1).

Verifies:
1. State creation with typed attributes
2. Deterministic node execution and partial state updates
3. Graph compilation
4. End-to-end execution flow: START -> node_one -> node_two -> END
5. Deterministic execution without external API or network dependencies
"""

from langgraph.graph.state import CompiledStateGraph

from src.graph.basic_graph import (
    create_basic_graph,
    node_one,
    node_two,
    run_basic_graph,
)
from src.graph.state import BasicState


def test_basic_state_creation():
    """Verify that BasicState can be instantiated as a typed dict."""
    state: BasicState = {"input": "test input", "output": "", "step": 0}
    assert state["input"] == "test input"
    assert state["output"] == ""
    assert state["step"] == 0


def test_node_functions_isolation():
    """Verify nodes independently receive state and return expected updates."""
    # Test node_one
    initial_state: BasicState = {"input": "  lead qualify  ", "output": "", "step": 0}
    update_one = node_one(initial_state)

    assert update_one["output"] == "STEP1:LEAD QUALIFY"
    assert update_one["step"] == 1

    # Test node_two receiving state updated by node_one
    intermediate_state: BasicState = {
        "input": initial_state["input"],
        "output": update_one["output"],
        "step": update_one["step"],
    }
    update_two = node_two(intermediate_state)

    assert update_two["output"] == "STEP1:LEAD QUALIFY -> STEP2:PROCESSED"
    assert update_two["step"] == 2


def test_graph_compilation():
    """Verify that the StateGraph compiles successfully into an executable graph."""
    graph = create_basic_graph()
    assert isinstance(graph, CompiledStateGraph)
    # Ensure nodes are registered in the compiled graph
    assert "node_one" in graph.nodes
    assert "node_two" in graph.nodes


def test_graph_invocation_end_to_end():
    """Verify the complete execution: START -> node_one -> node_two -> END."""
    graph = create_basic_graph()
    initial_state: BasicState = {
        "input": "agentic crm",
        "output": "",
        "step": 0,
    }

    final_state = graph.invoke(initial_state)

    # 1. Input is preserved
    assert final_state["input"] == "agentic crm"
    # 2. Sequential transformations occurred in exact order
    assert final_state["output"] == "STEP1:AGENTIC CRM -> STEP2:PROCESSED"
    # 3. Step counter reflects execution of both nodes
    assert final_state["step"] == 2


def test_run_basic_graph_helper():
    """Verify the convenience invocation helper function."""
    result = run_basic_graph("pipeline test")

    assert result["input"] == "pipeline test"
    assert result["output"] == "STEP1:PIPELINE TEST -> STEP2:PROCESSED"
    assert result["step"] == 2
