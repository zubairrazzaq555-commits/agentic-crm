"""Agentic CRM — Repositories package."""

from src.crm.repositories.account_repo import AccountRepository
from src.crm.repositories.contact_repo import ContactRepository
from src.crm.repositories.deal_repo import DealRepository
from src.crm.repositories.lead_repo import LeadRepository
from src.crm.repositories.opportunity_repo import OpportunityRepository

__all__ = [
    "LeadRepository",
    "AccountRepository",
    "ContactRepository",
    "OpportunityRepository",
    "DealRepository",
]

