"""Agentic CRM — Services package."""

from src.crm.services.account_service import AccountService
from src.crm.services.contact_service import ContactService
from src.crm.services.deal_service import DealService
from src.crm.services.lead_service import LeadService
from src.crm.services.opportunity_service import OpportunityService

__all__ = [
    "LeadService",
    "AccountService",
    "ContactService",
    "OpportunityService",
    "DealService",
]

