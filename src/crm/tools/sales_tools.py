"""Agentic CRM — Deterministic Sales Python Tools.

These reusable functions serve as deterministic Level 4 tool implementations
for future specialist agents. They handle CRUD and core business logic without
any LLM or cognitive overhead.

Tools included:
- create_lead_tool
- update_lead_tool
- search_leads_tool
- qualify_lead_tool
- convert_lead_tool
- create_account_tool
- get_account_summary_tool
- create_contact_tool
- create_opportunity_tool
- update_opportunity_stage_tool
- create_deal_tool
- close_deal_tool
"""

from __future__ import annotations

from typing import Any, Optional

from src.crm.services.account_service import AccountService
from src.crm.services.contact_service import ContactService
from src.crm.services.deal_service import DealService
from src.crm.services.lead_service import LeadService
from src.crm.services.opportunity_service import OpportunityService
from src.database.connection import DatabaseManager


async def create_lead_tool(
    db: DatabaseManager,
    *,
    first_name: str,
    last_name: str,
    company: str,
    email: str,
    phone: Optional[str] = None,
    title: Optional[str] = None,
    source: Optional[str] = None,
    score: int = 0,
    notes: Optional[str] = None,
) -> dict[str, Any]:
    """Deterministic tool to create and score a new lead."""
    service = LeadService(db)
    lead = await service.create_lead(
        first_name=first_name,
        last_name=last_name,
        company=company,
        email=email,
        phone=phone,
        title=title,
        source=source,
        score=score,
        notes=notes,
    )
    return {"success": True, "lead": lead.to_dict()}


async def update_lead_tool(
    db: DatabaseManager,
    lead_id: str,
    **updates: Any,
) -> dict[str, Any]:
    """Deterministic tool to update an existing lead."""
    service = LeadService(db)
    updated = await service.update_lead(lead_id, **updates)
    if not updated:
        return {"success": False, "error": f"Lead '{lead_id}' not found"}
    return {"success": True, "lead": updated.to_dict()}


async def search_leads_tool(
    db: DatabaseManager,
    query: str,
    *,
    status: Optional[str] = None,
    limit: int = 50,
) -> dict[str, Any]:
    """Deterministic tool to search leads."""
    service = LeadService(db)
    leads = await service.search_leads(query, status=status, limit=limit)
    return {"success": True, "leads": [l.to_dict() for l in leads], "count": len(leads)}


async def qualify_lead_tool(
    db: DatabaseManager,
    lead_id: str,
    *,
    min_score: int = 50,
    force: bool = False,
    notes: Optional[str] = None,
) -> dict[str, Any]:
    """Deterministic tool to qualify a lead based on score threshold."""
    service = LeadService(db)
    lead = await service.qualify_lead(
        lead_id, min_score=min_score, force=force, qualification_notes=notes
    )
    return {"success": True, "lead": lead.to_dict()}


async def convert_lead_tool(
    db: DatabaseManager,
    lead_id: str,
    *,
    create_opportunity: bool = True,
    opportunity_name: Optional[str] = None,
    opportunity_amount: float = 0.0,
) -> dict[str, Any]:
    """Deterministic tool to convert a qualified lead into Account, Contact, and Opportunity."""
    service = LeadService(db)
    result = await service.convert_lead(
        lead_id,
        create_opportunity=create_opportunity,
        opportunity_name=opportunity_name,
        opportunity_amount=opportunity_amount,
    )
    return {
        "success": True,
        "lead": result["lead"].to_dict() if result["lead"] else None,
        "account": result["account"].to_dict() if result["account"] else None,
        "contact": result["contact"].to_dict() if result["contact"] else None,
        "opportunity": result["opportunity"].to_dict() if result["opportunity"] else None,
    }


async def create_account_tool(
    db: DatabaseManager,
    *,
    name: str,
    industry: Optional[str] = None,
    website: Optional[str] = None,
    phone: Optional[str] = None,
    tier: str = "smb",
    annual_revenue: float = 0.0,
    billing_city: Optional[str] = None,
    billing_country: Optional[str] = None,
) -> dict[str, Any]:
    """Deterministic tool to create an account."""
    service = AccountService(db)
    account = await service.create_account(
        name=name,
        industry=industry,
        website=website,
        phone=phone,
        tier=tier,
        annual_revenue=annual_revenue,
        billing_city=billing_city,
        billing_country=billing_country,
    )
    return {"success": True, "account": account.to_dict()}


async def get_account_summary_tool(
    db: DatabaseManager,
    account_id: str,
) -> dict[str, Any]:
    """Deterministic tool to compute aggregated financial & pipeline metrics for an account."""
    service = AccountService(db)
    summary = await service.get_account_summary(account_id)
    summary["account"] = summary["account"].to_dict()
    summary["success"] = True
    return summary


async def create_contact_tool(
    db: DatabaseManager,
    *,
    first_name: str,
    last_name: str,
    email: str,
    account_id: Optional[str] = None,
    phone: Optional[str] = None,
    title: Optional[str] = None,
    department: Optional[str] = None,
    is_primary: bool = False,
) -> dict[str, Any]:
    """Deterministic tool to create a contact."""
    service = ContactService(db)
    contact = await service.create_contact(
        first_name=first_name,
        last_name=last_name,
        email=email,
        account_id=account_id,
        phone=phone,
        title=title,
        department=department,
        is_primary=is_primary,
    )
    return {"success": True, "contact": contact.to_dict()}


async def create_opportunity_tool(
    db: DatabaseManager,
    *,
    account_id: str,
    name: str,
    stage: str = "prospecting",
    amount: float = 0.0,
    probability: Optional[int] = None,
    primary_contact_id: Optional[str] = None,
) -> dict[str, Any]:
    """Deterministic tool to create an opportunity."""
    service = OpportunityService(db)
    opp = await service.create_opportunity(
        account_id=account_id,
        name=name,
        stage=stage,
        amount=amount,
        probability=probability,
        primary_contact_id=primary_contact_id,
    )
    return {"success": True, "opportunity": opp.to_dict()}


async def update_opportunity_stage_tool(
    db: DatabaseManager,
    opp_id: str,
    new_stage: str,
) -> dict[str, Any]:
    """Deterministic tool to advance an opportunity's stage and probability."""
    service = OpportunityService(db)
    opp = await service.advance_stage(opp_id, new_stage)
    return {"success": True, "opportunity": opp.to_dict()}


async def create_deal_tool(
    db: DatabaseManager,
    *,
    opportunity_id: str,
    name: str,
    deal_value: float,
    discount_percentage: float = 0.0,
    payment_terms: Optional[str] = None,
) -> dict[str, Any]:
    """Deterministic tool to create a deal with automated pricing calculations."""
    service = DealService(db)
    deal = await service.create_deal(
        opportunity_id=opportunity_id,
        name=name,
        deal_value=deal_value,
        discount_percentage=discount_percentage,
        payment_terms=payment_terms,
    )
    return {"success": True, "deal": deal.to_dict()}


async def close_deal_tool(
    db: DatabaseManager,
    deal_id: str,
    *,
    accepted: bool,
) -> dict[str, Any]:
    """Deterministic tool to close a deal and automatically sync the opportunity."""
    service = DealService(db)
    deal = await service.close_deal(deal_id, accepted=accepted)
    return {"success": True, "deal": deal.to_dict()}

