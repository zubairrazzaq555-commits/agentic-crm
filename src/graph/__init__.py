"""Graph module for Agentic CRM powered by LangGraph.

Exposes execution topologies:
- Basic sequential workflow
- Conditional branching workflow
- Iterative loop workflow with termination safety
- Parallel branch execution with state aggregation
"""

from src.graph.basic_graph import (
    create_basic_graph,
    node_one,
    node_two,
    run_basic_graph,
)
from src.graph.conditional_graph import (
    create_conditional_graph,
    evaluate_node,
    fail_node,
    pass_node,
    route_by_score,
    run_conditional_graph,
)
from src.graph.loop_graph import (
    check_completion,
    create_loop_graph,
    finalize_max_iter_node,
    finalize_target_node,
    process_step_node,
    run_loop_graph,
)
from src.graph.parallel_graph import (
    aggregator_node,
    branch_category,
    branch_priority,
    branch_sentiment,
    create_parallel_graph,
    distribute_node,
    run_parallel_graph,
)
from src.graph.state import (
    BasicState,
    ConditionalState,
    LoopState,
    ParallelState,
)

__all__ = [
    # States
    "BasicState",
    "ConditionalState",
    "LoopState",
    "ParallelState",
    # Basic sequential
    "create_basic_graph",
    "node_one",
    "node_two",
    "run_basic_graph",
    # Conditional branching
    "create_conditional_graph",
    "evaluate_node",
    "route_by_score",
    "pass_node",
    "fail_node",
    "run_conditional_graph",
    # Loops
    "create_loop_graph",
    "process_step_node",
    "check_completion",
    "finalize_target_node",
    "finalize_max_iter_node",
    "run_loop_graph",
    # Parallel
    "create_parallel_graph",
    "distribute_node",
    "branch_sentiment",
    "branch_priority",
    "branch_category",
    "aggregator_node",
    "run_parallel_graph",
]
