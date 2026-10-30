"""State definitions for LangGraph workflows in Agentic CRM.

Includes typed state representations for:
- Basic sequential workflows (BasicState)
- Conditional branching workflows (ConditionalState)
- Iterative loop workflows with termination safety (LoopState)
- Parallel execution with state reduction (ParallelState)
"""

import operator
from typing import Annotated, List, TypedDict


class BasicState(TypedDict, total=False):
    """Minimal typed state for basic sequential workflows.

    Attributes:
        input: Initial input string.
        output: Processed output string accumulated across nodes.
        step: Step counter incremented by each executing node.
    """

    input: str
    output: str
    step: int


class ConditionalState(TypedDict, total=False):
    """State for conditional branching workflows.

    Attributes:
        input_score: Integer score to evaluate.
        decision: Evaluated routing decision ("APPROVED" or "REJECTED").
        feedback: Explanation message from the terminal branch node.
        step: Step counter tracking execution sequence.
    """

    input_score: int
    decision: str
    feedback: str
    step: int


class LoopState(TypedDict, total=False):
    """State for iterative loop workflows with termination conditions.

    Attributes:
        current_value: Numeric value incremented each iteration.
        target_value: Value threshold that triggers successful loop termination.
        iterations: Number of loop iterations executed.
        max_iterations: Safety ceiling to prevent infinite loops.
        status: Final status ("TARGET_REACHED" or "MAX_ITERATIONS_REACHED").
        history: Chronological list of values recorded at each iteration.
    """

    current_value: int
    target_value: int
    iterations: int
    max_iterations: int
    status: str
    history: List[int]


class ParallelState(TypedDict, total=False):
    """State for parallel branch execution with fan-out and fan-in.

    Attributes:
        topic: Input subject or entity to process across branches.
        branch_results: Accumulated list of branch results using `operator.add`
            as the state reducer to prevent parallel update conflicts.
        aggregated_summary: Final synthesized result produced by the aggregator node.
    """

    topic: str
    branch_results: Annotated[List[str], operator.add]
    aggregated_summary: str
