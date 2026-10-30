r"""Conditional branching LangGraph implementation.

Topology:
              START
                |
                v
          evaluate_node
                |
        [conditional router]
         /              \
        v                v
    pass_node        fail_node
        \                /
         v              v
               END
"""

from typing import Any, Dict
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from src.graph.state import ConditionalState

PASS_THRESHOLD = 50


def evaluate_node(state: ConditionalState) -> Dict[str, Any]:
    """Decision preparation node that logs the start of evaluation."""
    current_step = state.get("step", 0)
    return {
        "step": current_step + 1,
    }


def route_by_score(state: ConditionalState) -> str:
    """Routing function returning path key based on `input_score`.

    Returns:
        "pass_path" if input_score >= PASS_THRESHOLD, else "fail_path".
    """
    score = state.get("input_score", 0)
    if score >= PASS_THRESHOLD:
        return "pass_path"
    return "fail_path"


def pass_node(state: ConditionalState) -> Dict[str, Any]:
    """Terminal node executed when input score meets or exceeds threshold."""
    score = state.get("input_score", 0)
    current_step = state.get("step", 0)
    return {
        "decision": "APPROVED",
        "feedback": f"Score {score} meets or exceeds threshold of {PASS_THRESHOLD}.",
        "step": current_step + 1,
    }


def fail_node(state: ConditionalState) -> Dict[str, Any]:
    """Terminal node executed when input score falls below threshold."""
    score = state.get("input_score", 0)
    current_step = state.get("step", 0)
    return {
        "decision": "REJECTED",
        "feedback": f"Score {score} is below threshold of {PASS_THRESHOLD}.",
        "step": current_step + 1,
    }


def create_conditional_graph() -> CompiledStateGraph:
    """Construct, connect, and compile the conditional branching graph.

    Returns:
        CompiledStateGraph with dynamic routing based on state predicates.
    """
    builder = StateGraph(ConditionalState)

    # Register nodes
    builder.add_node("evaluate", evaluate_node)
    builder.add_node("pass_node", pass_node)
    builder.add_node("fail_node", fail_node)

    # Connect START to evaluate
    builder.add_edge(START, "evaluate")

    # Connect evaluate to pass_node or fail_node conditionally
    builder.add_conditional_edges(
        "evaluate",
        route_by_score,
        {
            "pass_path": "pass_node",
            "fail_path": "fail_node",
        },
    )

    # Both branch paths terminate at END
    builder.add_edge("pass_node", END)
    builder.add_edge("fail_node", END)

    return builder.compile()


def run_conditional_graph(score: int) -> ConditionalState:
    """Convenience helper to compile and invoke the conditional graph.

    Args:
        score: The numeric score to evaluate.

    Returns:
        Final ConditionalState with decision, feedback, and step count.
    """
    graph = create_conditional_graph()
    initial_state: ConditionalState = {
        "input_score": score,
        "decision": "",
        "feedback": "",
        "step": 0,
    }
    return graph.invoke(initial_state)
