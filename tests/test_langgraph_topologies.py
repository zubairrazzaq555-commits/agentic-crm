"""Focused unit tests for LangGraph Execution Topologies (Milestone 3.2).

Verifies:
1. Conditional Branching:
   - Both PASS and FAIL routing paths work based on state predicates
   - Correct final state and feedback returned
2. Graph Loops with Termination Safety:
   - Iteration counter increases and graph cycles back
   - Graph terminates when target value is achieved
   - Maximum iteration ceiling prevents infinite execution
3. Parallel Execution with Fan-out and Fan-in:
   - All three parallel branches execute
   - Results merge cleanly via state reducer without conflict
   - Aggregator receives and synthesizes all branch outputs
"""

from langgraph.graph.state import CompiledStateGraph

from src.graph.conditional_graph import (
    create_conditional_graph,
    route_by_score,
    run_conditional_graph,
)
from src.graph.loop_graph import (
    create_loop_graph,
    run_loop_graph,
)
from src.graph.parallel_graph import (
    branch_category,
    branch_priority,
    branch_sentiment,
    create_parallel_graph,
    run_parallel_graph,
)
from src.graph.state import (
    ConditionalState,
    LoopState,
    ParallelState,
)


# ==============================================================================
# Part A: Conditional Branching Tests
# ==============================================================================


def test_conditional_routing_function_isolation():
    """Verify route_by_score predicate directly against state thresholds."""
    assert route_by_score({"input_score": 50}) == "pass_path"
    assert route_by_score({"input_score": 85}) == "pass_path"
    assert route_by_score({"input_score": 49}) == "fail_path"
    assert route_by_score({"input_score": 0}) == "fail_path"


def test_conditional_graph_pass_path():
    """Verify full graph execution along the APPROVED branch."""
    graph = create_conditional_graph()
    assert isinstance(graph, CompiledStateGraph)

    result = run_conditional_graph(score=75)

    assert result["input_score"] == 75
    assert result["decision"] == "APPROVED"
    assert "meets or exceeds threshold" in result["feedback"]
    assert result["step"] == 2  # evaluate (1) -> pass_node (2)


def test_conditional_graph_fail_path():
    """Verify full graph execution along the REJECTED branch."""
    result = run_conditional_graph(score=30)

    assert result["input_score"] == 30
    assert result["decision"] == "REJECTED"
    assert "below threshold" in result["feedback"]
    assert result["step"] == 2  # evaluate (1) -> fail_node (2)


# ==============================================================================
# Part B: Loops with Termination Conditions Tests
# ==============================================================================


def test_loop_graph_target_reached():
    """Verify loop repeats until the target value threshold is met."""
    graph = create_loop_graph()
    assert isinstance(graph, CompiledStateGraph)

    # Start 0, target 30 -> requires 3 iterations of +10
    result = run_loop_graph(start_value=0, target_value=30, max_iterations=10)

    assert result["status"] == "TARGET_REACHED"
    assert result["current_value"] == 30
    assert result["iterations"] == 3
    assert result["history"] == [10, 20, 30]


def test_loop_graph_max_iterations_safety():
    """Verify emergency exit when target is unreachable within max_iterations."""
    # Target 500 would require 50 iterations, but safety cap is 3
    result = run_loop_graph(start_value=0, target_value=500, max_iterations=3)

    assert result["status"] == "MAX_ITERATIONS_REACHED"
    assert result["current_value"] == 30
    assert result["iterations"] == 3
    assert result["history"] == [10, 20, 30]


# ==============================================================================
# Part C: Parallel Execution with Fan-out & Fan-in Tests
# ==============================================================================


def test_parallel_branch_nodes_isolation():
    """Verify parallel branch nodes independently produce expected list payloads."""
    test_state: ParallelState = {"topic": "Enterprise Lead"}

    res_sentiment = branch_sentiment(test_state)
    res_priority = branch_priority(test_state)
    res_category = branch_category(test_state)

    assert res_sentiment["branch_results"] == ["SENTIMENT:Positive[Enterprise Lead]"]
    assert res_priority["branch_results"] == ["PRIORITY:High[Enterprise Lead]"]
    assert res_category["branch_results"] == ["CATEGORY:Enterprise[Enterprise Lead]"]


def test_parallel_graph_fan_out_and_fan_in():
    """Verify parallel execution executes all 3 branches and aggregates cleanly."""
    graph = create_parallel_graph()
    assert isinstance(graph, CompiledStateGraph)

    result = run_parallel_graph(topic="Lead #42")

    assert result["topic"] == "Lead #42"

    # All three parallel branch results must be merged via operator.add
    results = result["branch_results"]
    assert len(results) == 3
    assert any("SENTIMENT" in r for r in results)
    assert any("PRIORITY" in r for r in results)
    assert any("CATEGORY" in r for r in results)

    # Aggregator synthesized all outputs into the final summary
    assert "SUMMARY:" in result["aggregated_summary"]
    assert "CATEGORY:Enterprise[Lead #42]" in result["aggregated_summary"]
    assert "PRIORITY:High[Lead #42]" in result["aggregated_summary"]
    assert "SENTIMENT:Positive[Lead #42]" in result["aggregated_summary"]
