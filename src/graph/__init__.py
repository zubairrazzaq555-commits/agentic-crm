"""Graph module for Agentic CRM powered by LangGraph."""

from src.graph.basic_graph import (
    create_basic_graph,
    node_one,
    node_two,
    run_basic_graph,
)
from src.graph.state import BasicState

__all__ = [
    "BasicState",
    "create_basic_graph",
    "node_one",
    "node_two",
    "run_basic_graph",
]
