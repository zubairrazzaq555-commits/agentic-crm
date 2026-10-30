r"""Parallel execution LangGraph implementation with state fan-in aggregation.

Topology:
                  START
                    |
                    v
             distribute_node
             /      |      \
            v       v       v
      branch_a   branch_b  branch_c
       (sentiment)(priority)(category)
            \       |       /
             v      v      v
              aggregator
                    |
                    v
                   END
"""

from typing import Any, Dict
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from src.graph.state import ParallelState


def distribute_node(state: ParallelState) -> Dict[str, Any]:
    """Distribution node preparing topic input for parallel evaluation branches."""
    # Initialize branch_results to empty list if not present
    return {
        "branch_results": [],
    }


def branch_sentiment(state: ParallelState) -> Dict[str, Any]:
    """Parallel branch A: Deterministically evaluates sentiment for the topic."""
    topic = state.get("topic", "")
    return {
        "branch_results": [f"SENTIMENT:Positive[{topic}]"],
    }


def branch_priority(state: ParallelState) -> Dict[str, Any]:
    """Parallel branch B: Deterministically evaluates priority for the topic."""
    topic = state.get("topic", "")
    return {
        "branch_results": [f"PRIORITY:High[{topic}]"],
    }


def branch_category(state: ParallelState) -> Dict[str, Any]:
    """Parallel branch C: Deterministically evaluates category for the topic."""
    topic = state.get("topic", "")
    return {
        "branch_results": [f"CATEGORY:Enterprise[{topic}]"],
    }


def aggregator_node(state: ParallelState) -> Dict[str, Any]:
    """Aggregator node receiving merged results from all parallel branches."""
    results = state.get("branch_results", [])
    # Sort for deterministic string aggregation
    merged_summary = " | ".join(sorted(results))
    return {
        "aggregated_summary": f"SUMMARY: {merged_summary}",
    }


def create_parallel_graph() -> CompiledStateGraph:
    """Construct, connect, and compile the parallel execution graph.

    Uses `operator.add` reducer defined on `ParallelState.branch_results`
    to merge parallel node outputs cleanly without state update conflicts.

    Returns:
        CompiledStateGraph executing 3 parallel branches with fan-in aggregation.
    """
    builder = StateGraph(ParallelState)

    # Register nodes
    builder.add_node("distribute", distribute_node)
    builder.add_node("branch_sentiment", branch_sentiment)
    builder.add_node("branch_priority", branch_priority)
    builder.add_node("branch_category", branch_category)
    builder.add_node("aggregator", aggregator_node)

    # Fan-out: distribute -> all 3 branches
    builder.add_edge(START, "distribute")
    builder.add_edge("distribute", "branch_sentiment")
    builder.add_edge("distribute", "branch_priority")
    builder.add_edge("distribute", "branch_category")

    # Fan-in: all 3 branches -> aggregator
    builder.add_edge("branch_sentiment", "aggregator")
    builder.add_edge("branch_priority", "aggregator")
    builder.add_edge("branch_category", "aggregator")

    # Terminate after aggregator
    builder.add_edge("aggregator", END)

    return builder.compile()


def run_parallel_graph(topic: str) -> ParallelState:
    """Convenience helper to compile and invoke the parallel execution graph.

    Args:
        topic: Input subject to evaluate across parallel branches.

    Returns:
        Final ParallelState containing all branch results and the aggregated summary.
    """
    graph = create_parallel_graph()
    initial_state: ParallelState = {
        "topic": topic,
        "branch_results": [],
        "aggregated_summary": "",
    }
    return graph.invoke(initial_state)
