"""Sales Domain Agent graph and coordinator class.

The Sales Domain Agent is responsible for receiving sales tasks from the
Grandparent Orchestrator, determining the appropriate sales subdomain, and
routing execution to the designated subdomain handler.
"""

from typing import Any, Dict, Optional
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from src.agents.sales.classifier import (
    route_sales_category,
    sales_classifier_node,
)
from src.agents.sales.handlers import (
    deal_management_handler,
    general_sales_handler,
    lead_management_handler,
    opportunity_management_handler,
)
from src.agents.sales.state import (
    SalesAgentState,
    create_initial_sales_state,
)


def create_sales_agent_graph() -> CompiledStateGraph:
    r"""Construct, connect, and compile the Sales Domain Agent LangGraph.

    Topology:
                    START
                      |
                      v
             sales_classifier_node
                      |
            [conditional routing]
          /     /          \     \
         v     v            v     v
       lead opportunity   deal  general
         \     \            /     /
          \_____\__________/_____/
                     |
                     v
                    END

    Returns:
        CompiledStateGraph for sales subdomain routing and execution.
    """
    builder = StateGraph(SalesAgentState)

    # Register classification node
    builder.add_node("classifier", sales_classifier_node)

    # Register subdomain handlers
    builder.add_node("lead_handler", lead_management_handler)
    builder.add_node("opportunity_handler", opportunity_management_handler)
    builder.add_node("deal_handler", deal_management_handler)
    builder.add_node("general_handler", general_sales_handler)

    # Entry edge
    builder.add_edge(START, "classifier")

    # Conditional branching
    builder.add_conditional_edges(
        "classifier",
        route_sales_category,
        {
            "lead_management": "lead_handler",
            "opportunity_management": "opportunity_handler",
            "deal_management": "deal_handler",
            "general_sales": "general_handler",
        },
    )

    # All branches route to END
    builder.add_edge("lead_handler", END)
    builder.add_edge("opportunity_handler", END)
    builder.add_edge("deal_handler", END)
    builder.add_edge("general_handler", END)

    return builder.compile()


class SalesDomainAgent:
    """High-level domain agent coordinator for all sales operations."""

    def __init__(self, graph: Optional[CompiledStateGraph] = None) -> None:
        """Initialize the SalesDomainAgent with an optional compiled graph."""
        self._graph = graph or create_sales_agent_graph()

    @property
    def graph(self) -> CompiledStateGraph:
        """Access the underlying compiled LangGraph."""
        return self._graph

    def execute(
        self,
        task_id: str,
        task_type: str,
        input_payload: Optional[Dict[str, Any]] = None,
    ) -> SalesAgentState:
        """Synchronously execute sales task processing.

        Args:
            task_id: Unique task identifier.
            task_type: Specific sales task type or action.
            input_payload: Optional payload dictionary.

        Returns:
            Final SalesAgentState.
        """
        initial_state = create_initial_sales_state(
            task_id=task_id,
            task_type=task_type,
            input_payload=input_payload,
        )
        return self._graph.invoke(initial_state)

    async def aexecute(
        self,
        task_id: str,
        task_type: str,
        input_payload: Optional[Dict[str, Any]] = None,
    ) -> SalesAgentState:
        """Asynchronously execute sales task processing.

        Args:
            task_id: Unique task identifier.
            task_type: Specific sales task type or action.
            input_payload: Optional payload dictionary.

        Returns:
            Final SalesAgentState after asynchronous execution.
        """
        initial_state = create_initial_sales_state(
            task_id=task_id,
            task_type=task_type,
            input_payload=input_payload,
        )
        return await self._graph.ainvoke(initial_state)
