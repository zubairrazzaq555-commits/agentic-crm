r"""Iterative loop LangGraph implementation with termination safety.

Topology:
              START
                |
                v
        --> process_step
       |        |
       |  [check_completion]
       |   /     |         \
 [continue]      |          \
                 v           v
          finalize_target  finalize_max
                 \           /
                  v         v
                     END
"""

from typing import Any, Dict
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from src.graph.state import LoopState

DEFAULT_INCREMENT = 10
DEFAULT_MAX_ITERATIONS = 5


def process_step_node(state: LoopState) -> Dict[str, Any]:
    """Processing node executed on each iteration.

    Increments `current_value` by a deterministic step, advances the iteration
    counter, and records value history.
    """
    current_val = state.get("current_value", 0)
    new_val = current_val + DEFAULT_INCREMENT
    iterations = state.get("iterations", 0) + 1
    history = list(state.get("history", [])) + [new_val]

    return {
        "current_value": new_val,
        "iterations": iterations,
        "history": history,
    }


def check_completion(state: LoopState) -> str:
    """Conditional router that checks termination criteria and safety limits.

    Returns:
        "target_reached" if current_value >= target_value
        "max_iterations_reached" if iterations >= max_iterations
        "continue_loop" if further iterations are needed
    """
    val = state.get("current_value", 0)
    target = state.get("target_value", 0)
    iterations = state.get("iterations", 0)
    max_iter = state.get("max_iterations", DEFAULT_MAX_ITERATIONS)

    if val >= target:
        return "target_reached"
    if iterations >= max_iter:
        return "max_iterations_reached"
    return "continue_loop"


def finalize_target_node(state: LoopState) -> Dict[str, Any]:
    """Terminal node executed when the target value condition is successfully met."""
    return {
        "status": "TARGET_REACHED",
    }


def finalize_max_iter_node(state: LoopState) -> Dict[str, Any]:
    """Terminal safety node executed when maximum iterations ceiling is reached."""
    return {
        "status": "MAX_ITERATIONS_REACHED",
    }


def create_loop_graph() -> CompiledStateGraph:
    """Construct, connect, and compile the loop graph with termination safety.

    Returns:
        CompiledStateGraph with an edge cycling back to `process_step` until
        either the target value is reached or the iteration ceiling is hit.
    """
    builder = StateGraph(LoopState)

    # Register nodes
    builder.add_node("process_step", process_step_node)
    builder.add_node("finalize_target", finalize_target_node)
    builder.add_node("finalize_max", finalize_max_iter_node)

    # Connect START to initial process step
    builder.add_edge(START, "process_step")

    # Connect process_step with conditional edge (loop back or terminate)
    builder.add_conditional_edges(
        "process_step",
        check_completion,
        {
            "continue_loop": "process_step",  # Real graph cycle / loop
            "target_reached": "finalize_target",
            "max_iterations_reached": "finalize_max",
        },
    )

    # Terminate paths at END
    builder.add_edge("finalize_target", END)
    builder.add_edge("finalize_max", END)

    return builder.compile()


def run_loop_graph(
    start_value: int,
    target_value: int,
    max_iterations: int = DEFAULT_MAX_ITERATIONS,
) -> LoopState:
    """Convenience helper to compile and invoke the loop graph.

    Args:
        start_value: Starting numeric value.
        target_value: Goal threshold to terminate the loop.
        max_iterations: Maximum allowed iterations before emergency exit.

    Returns:
        Final LoopState with status, iterations, current_value, and history.
    """
    graph = create_loop_graph()
    initial_state: LoopState = {
        "current_value": start_value,
        "target_value": target_value,
        "iterations": 0,
        "max_iterations": max_iterations,
        "status": "",
        "history": [],
    }
    return graph.invoke(initial_state)
