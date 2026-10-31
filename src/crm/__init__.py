"""Agentic CRM — Sales Domain Core CRM Package."""

from src.crm.models import (
    Account,
    AccountStatus,
    AccountTier,
    Contact,
    Deal,
    DealStatus,
    Lead,
    LeadStatus,
    Opportunity,
    OpportunityStage,
    STAGE_PROBABILITIES,
    accounts_table,
    contacts_table,
    deals_table,
    leads_table,
    opportunities_table,
)

__all__ = [
    "Lead",
    "Account",
    "Contact",
    "Opportunity",
    "Deal",
    "LeadStatus",
    "AccountTier",
    "AccountStatus",
    "OpportunityStage",
    "DealStatus",
    "STAGE_PROBABILITIES",
    "leads_table",
    "accounts_table",
    "contacts_table",
    "opportunities_table",
    "deals_table",
]

