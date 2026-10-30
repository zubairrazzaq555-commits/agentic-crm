"""Basic sequential LangGraph implementation.

Core pattern:
    State -> Node -> Graph -> Edge -> Compile -> Invoke

Topology:
    START -> node_one -> node_two -> END
"""

from typing import Any, Dict
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from src.graph.state import BasicState


def node_one(state: BasicState) -> Dict[str, Any]:
    """First deterministic node in the graph.

    Reads `input` from state, applies initial transformation (uppercasing),
    and increments the step counter.
    """
    raw_input = state.get("input", "")
    processed = raw_input.strip().upper()
    current_step = state.get("step", 0)

    return {
        "output": f"STEP1:{processed}",
        "step": current_step + 1,
    }


def node_two(state: BasicState) -> Dict[str, Any]:
    """Second deterministic node in the graph.

    Reads accumulated `output` from state, applies secondary transformation,
    and increments the step counter.
    """
    current_output = state.get("output", "")
    current_step = state.get("step", 0)

    return {
        "output": f"{current_output} -> STEP2:PROCESSED",
        "step": current_step + 1,
    }


def create_basic_graph() -> CompiledStateGraph:
    """Construct, connect, and compile the basic sequential LangGraph.

    Returns:
        CompiledStateGraph ready for invocation.
    """
    # 1. State: initialize StateGraph with typed schema
    builder = StateGraph(BasicState)

    # 2. Nodes: register deterministic node functions
    builder.add_node("node_one", node_one)
    builder.add_node("node_two", node_two)

    # 3. Edges: define execution path: START -> node_one -> node_two -> END
    builder.add_edge(START, "node_one")
    builder.add_edge("node_one", "node_two")
    builder.add_edge("node_two", END)

    # 4. Compile: create executable graph
    return builder.compile()


def run_basic_graph(initial_input: str) -> BasicState:
    """Convenience helper to compile and invoke the basic graph.

    Args:
        initial_input: Text input to pass to the graph.

    Returns:
        Final BasicState dict after executing all nodes.
    """
    graph = create_basic_graph()
    initial_state: BasicState = {
        "input": initial_input,
        "output": "",
        "step": 0,
    }
    # 5. Invoke: execute the compiled graph
    return graph.invoke(initial_state)
