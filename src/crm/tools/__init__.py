"""Agentic CRM — Sales Tools package."""

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

