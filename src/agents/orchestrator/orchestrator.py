"""Grandparent Orchestrator graph and runner.

The Grandparent Orchestrator serves as the top-level dispatching coordinator
in the hierarchical agent architecture. It ingests an incoming task,
classifies its business domain, and conditionally routes it to the designated
domain handler.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
from typing import Any, Dict, Optional
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from src.agents.orchestrator.classifier import (
    classifier_node,
    create_classifier_node,
    route_domain,
)
from src.agents.orchestrator.handlers import (
    customer_service_handler_node,
    data_handler_node,
    marketing_handler_node,
    sales_handler_node,
    unknown_handler_node,
)
from src.agents.orchestrator.state import (
    OrchestratorState,
    create_initial_orchestrator_state,
)


def create_orchestrator_graph(
    provider_manager: Optional[Any] = None,
) -> CompiledStateGraph:
    r"""Construct, connect, and compile the Grandparent Orchestrator LangGraph.

    When *provider_manager* is supplied, the classifier node gains an optional
    LLM-assisted classification fallback for ambiguous tasks. When omitted
    (the default), classification is purely deterministic.

    Topology:
                    START
                      |
                      v
                  classifier
                      |
             [conditional routing]
          /     /        |       \      \
         v     v         v        v      v
      sales marketing  service   data  unknown
         \     \         |        /      /
          \_____\________v_______/______/
                         |
                         v
                        END

    Args:
        provider_manager: Optional ProviderManager instance enabling
            LLM-assisted classification when deterministic classifier is uncertain.

    Returns:
        CompiledStateGraph ready for synchronous or asynchronous invocation.
    """
    builder = StateGraph(OrchestratorState)

    # Register classification node (deterministic or LLM-assisted)
    if provider_manager is not None:
        builder.add_node("classifier", create_classifier_node(provider_manager))
    else:
        builder.add_node("classifier", classifier_node)

    # Register decoupled domain handler nodes
    builder.add_node("sales_handler", sales_handler_node)
    builder.add_node("marketing_handler", marketing_handler_node)
    builder.add_node("customer_service_handler", customer_service_handler_node)
    builder.add_node("data_handler", data_handler_node)
    builder.add_node("unknown_handler", unknown_handler_node)

    # Graph entrypoint: START -> classifier
    builder.add_edge(START, "classifier")

    # Conditional routing based on classified domain
    builder.add_conditional_edges(
        "classifier",
        route_domain,
        {
            "sales": "sales_handler",
            "marketing": "marketing_handler",
            "customer_service": "customer_service_handler",
            "data": "data_handler",
            "unknown": "unknown_handler",
        },
    )

    # Terminal edges: all domain handlers transition to END
    builder.add_edge("sales_handler", END)
    builder.add_edge("marketing_handler", END)
    builder.add_edge("customer_service_handler", END)
    builder.add_edge("data_handler", END)
    builder.add_edge("unknown_handler", END)

    return builder.compile()


class GrandparentOrchestrator:
    """High-level orchestrator class wrapping the compiled StateGraph."""

    def __init__(
        self,
        graph: Optional[CompiledStateGraph] = None,
        provider_manager: Optional[Any] = None,
    ) -> None:
        """Initialize the orchestrator with an optional precompiled graph.

        Args:
            graph: Optional pre-compiled LangGraph. If omitted, creates a new one.
            provider_manager: Optional ProviderManager instance enabling
                LLM-assisted classification when deterministic classifier is uncertain.
        """
        self._provider_manager = provider_manager
        self._graph = graph or create_orchestrator_graph(provider_manager=provider_manager)

    @property
    def graph(self) -> CompiledStateGraph:
        """Access the underlying compiled LangGraph."""
        return self._graph

    @property
    def provider_manager(self) -> Optional[Any]:
        """Access the configured ProviderManager, if any."""
        return self._provider_manager

    def execute(
        self,
        task_id: str,
        task_type: str,
        input_payload: Optional[Dict[str, Any]] = None,
    ) -> OrchestratorState:
        """Synchronously execute orchestration for an incoming task.

        Args:
            task_id: Unique task identifier.
            task_type: Task category/type string.
            input_payload: Optional payload dictionary.

        Returns:
            Final OrchestratorState after graph execution.
        """
        initial_state = create_initial_orchestrator_state(
            task_id=task_id,
            task_type=task_type,
            input_payload=input_payload,
        )
        try:
            return self._graph.invoke(initial_state)
        except TypeError as exc:
            # LangGraph raises TypeError when invoke() is called on an async node.
            # Fall back to running ainvoke() in an event loop.
            if "No synchronous function provided" in str(exc) or "async API" in str(exc):
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    loop = None

                if loop and loop.is_running():
                    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                        return pool.submit(asyncio.run, self._graph.ainvoke(initial_state)).result()
                else:
                    return asyncio.run(self._graph.ainvoke(initial_state))
            raise

    async def aexecute(
        self,
        task_id: str,
        task_type: str,
        input_payload: Optional[Dict[str, Any]] = None,
    ) -> OrchestratorState:
        """Asynchronously execute orchestration for an incoming task.

        Args:
            task_id: Unique task identifier.
            task_type: Task category/type string.
            input_payload: Optional payload dictionary.

        Returns:
            Final OrchestratorState after asynchronous graph execution.
        """
        initial_state = create_initial_orchestrator_state(
            task_id=task_id,
            task_type=task_type,
            input_payload=input_payload,
        )
        return await self._graph.ainvoke(initial_state)
