"""Sales Domain Agent package."""

from src.agents.sales.agent import (
    SalesDomainAgent,
    create_sales_agent_graph,
)
from src.agents.sales.classifier import (
    SALES_CATEGORY_KEYWORDS,
    classify_sales_task,
    route_sales_category,
    sales_classifier_node,
)
from src.agents.sales.handlers import (
    account_management_handler,
    account_management_handler_async,
    contact_management_handler,
    contact_management_handler_async,
    deal_management_handler,
    deal_management_handler_async,
    general_sales_handler,
    lead_management_handler,
    lead_management_handler_async,
    opportunity_management_handler,
    opportunity_management_handler_async,
)
from src.agents.sales.intent import extract_sales_intent
from src.agents.sales.state import (
    SUPPORTED_SALES_CATEGORIES,
    SalesAgentState,
    create_initial_sales_state,
)
from src.crm.tools.sales_tools import (
    close_deal_tool,
    convert_lead_tool,
    create_account_tool,
    create_contact_tool,
    create_deal_tool,
    create_lead_tool,
    create_opportunity_tool,
    get_account_summary_tool,
    qualify_lead_tool,
    search_leads_tool,
    update_lead_tool,
    update_opportunity_stage_tool,
)

__all__ = [
    "SALES_CATEGORY_KEYWORDS",
    "SUPPORTED_SALES_CATEGORIES",
    "SalesAgentState",
    "SalesDomainAgent",
    "account_management_handler",
    "account_management_handler_async",
    "classify_sales_task",
    "contact_management_handler",
    "contact_management_handler_async",
    "create_initial_sales_state",
    "create_sales_agent_graph",
    "deal_management_handler",
    "deal_management_handler_async",
    "extract_sales_intent",
    "general_sales_handler",
    "lead_management_handler",
    "lead_management_handler_async",
    "opportunity_management_handler",
    "opportunity_management_handler_async",
    "route_sales_category",
    "sales_classifier_node",
    "create_lead_tool",
    "update_lead_tool",
    "search_leads_tool",
    "qualify_lead_tool",
    "convert_lead_tool",
    "create_account_tool",
    "get_account_summary_tool",
    "create_contact_tool",
    "create_opportunity_tool",
    "update_opportunity_stage_tool",
    "create_deal_tool",
    "close_deal_tool",
]

