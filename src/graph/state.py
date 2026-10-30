"""State definitions for foundational LangGraph workflows."""

from typing import TypedDict


class BasicState(TypedDict, total=False):
    """Minimal typed state for LangGraph workflows.

    Attributes:
        input: Initial input string.
        output: Processed output string accumulated across nodes.
        step: Step counter incremented by each executing node.
    """

    input: str
    output: str
    step: int
