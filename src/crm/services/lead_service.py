"""Agentic CRM — Lead Service.

Encapsulates business rules and validation for Lead management:
- Intake validation & deduplication
- Lead qualification workflows
- Lead conversion to Account, Contact, and Opportunity
"""

from __future__ import annotations

import re
from typing import Any, Optional

from src.crm.models import Lead, LeadStatus
from src.crm.repositories.account_repo import AccountRepository
from src.crm.repositories.contact_repo import ContactRepository
from src.crm.repositories.lead_repo import LeadRepository
from src.crm.repositories.opportunity_repo import OpportunityRepository
from src.database.connection import DatabaseManager

_EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class LeadService:
    """Business logic service for Lead operations."""

    def __init__(self, db: DatabaseManager) -> None:
        self._db = db
        self._lead_repo = LeadRepository(db)
        self._account_repo = AccountRepository(db)
        self._contact_repo = ContactRepository(db)
        self._opp_repo = OpportunityRepository(db)

    def _validate_lead_input(
        self,
        first_name: str,
        last_name: str,
        company: str,
        email: str,
        score: int = 0,
    ) -> None:
        """Validate lead input constraints."""
        if not first_name or not first_name.strip():
            raise ValueError("First name is required and cannot be empty.")
        if not last_name or not last_name.strip():
            raise ValueError("Last name is required and cannot be empty.")
        if not company or not company.strip():
            raise ValueError("Company name is required and cannot be empty.")
        if not email or not email.strip():
            raise ValueError("Email is required and cannot be empty.")
        if not _EMAIL_REGEX.match(email.strip()):
            raise ValueError(f"Invalid email address format: '{email}'.")
        if not (0 <= score <= 100):
            raise ValueError(f"Lead score must be between 0 and 100, got {score}.")

    async def create_lead(
        self,
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
    ) -> Lead:
        """Validate and persist a new Lead."""
        self._validate_lead_input(first_name, last_name, company, email, score)

        clean_email = email.strip().lower()
        existing = await self._lead_repo.get_by_email(clean_email)
        if existing:
            raise ValueError(f"A lead with email '{clean_email}' already exists (ID: {existing.id}).")

        lead = Lead(
            id="",
            first_name=first_name.strip(),
            last_name=last_name.strip(),
            company=company.strip(),
            email=clean_email,
            phone=phone.strip() if phone else None,
            title=title.strip() if title else None,
            status=LeadStatus.NEW.value,
            source=source.strip() if source else None,
            score=score,
            notes=notes.strip() if notes else None,
        )
        return await self._lead_repo.create(lead)

    async def get_lead(self, lead_id: str) -> Optional[Lead]:
        """Fetch lead by ID."""
        return await self._lead_repo.get_by_id(lead_id)

    async def update_lead(self, lead_id: str, **updates: Any) -> Optional[Lead]:
        """Validate and apply updates to a lead."""
        existing = await self._lead_repo.get_by_id(lead_id)
        if not existing:
            raise ValueError(f"Lead not found with ID '{lead_id}'.")

        if "email" in updates and updates["email"]:
            if not _EMAIL_REGEX.match(updates["email"].strip()):
                raise ValueError(f"Invalid email format: '{updates['email']}'.")
            updates["email"] = updates["email"].strip().lower()

        if "score" in updates and updates["score"] is not None:
            score = int(updates["score"])
            if not (0 <= score <= 100):
                raise ValueError(f"Score must be between 0 and 100, got {score}.")
            updates["score"] = score

        if "status" in updates and updates["status"]:
            valid_statuses = {s.value for s in LeadStatus}
            if updates["status"] not in valid_statuses:
                raise ValueError(
                    f"Invalid status '{updates['status']}'. Must be one of {valid_statuses}."
                )

        return await self._lead_repo.update(lead_id, updates)

    async def qualify_lead(
        self,
        lead_id: str,
        *,
        min_score: int = 50,
        force: bool = False,
        qualification_notes: Optional[str] = None,
    ) -> Lead:
        """
        Evaluate and qualify a lead.

        Rules:
        - If force is False, lead score must meet or exceed min_score.
        - Sets status to 'qualified' and appends qualification notes if provided.
        """
        lead = await self._lead_repo.get_by_id(lead_id)
        if not lead:
            raise ValueError(f"Lead not found with ID '{lead_id}'.")

        if lead.status == LeadStatus.CONVERTED.value:
            raise ValueError("Cannot qualify a lead that has already been converted.")

        if not force and lead.score < min_score:
            raise ValueError(
                f"Lead score ({lead.score}) does not meet the minimum qualification threshold ({min_score})."
            )

        updated_notes = lead.notes or ""
        if qualification_notes:
            updated_notes = (
                f"{updated_notes}\n[Qualification Note]: {qualification_notes}".strip()
            )

        updated = await self._lead_repo.update(
            lead_id,
            {
                "status": LeadStatus.QUALIFIED.value,
                "notes": updated_notes,
            },
        )
        assert updated is not None
        return updated

    async def convert_lead(
        self,
        lead_id: str,
        *,
        create_opportunity: bool = True,
        opportunity_name: Optional[str] = None,
        opportunity_amount: float = 0.0,
    ) -> dict[str, Any]:
        """
        Convert a qualified lead into Account, Contact, and Opportunity records.

        Rules:
        - Lead status must be QUALIFIED or will be marked QUALIFIED upon conversion.
        - Idempotently creates or reuses Account by company name.
        - Creates a Contact linked to the Account.
        - If create_opportunity is True, creates an Opportunity linked to the Account.
        - Sets lead status to 'converted'.
        """
        lead = await self._lead_repo.get_by_id(lead_id)
        if not lead:
            raise ValueError(f"Lead not found with ID '{lead_id}'.")

        if lead.status == LeadStatus.CONVERTED.value:
            raise ValueError(f"Lead '{lead_id}' has already been converted.")

        # 1. Resolve or create Account
        account = await self._account_repo.get_by_name(lead.company)
        if not account:
            account = await self._account_repo.create(
                {
                    "name": lead.company,
                    "phone": lead.phone,
                }
            )

        # 2. Create Contact under Account
        contact = await self._contact_repo.create(
            {
                "account_id": account.id,
                "first_name": lead.first_name,
                "last_name": lead.last_name,
                "email": lead.email,
                "phone": lead.phone,
                "title": lead.title,
                "is_primary": True,
            }
        )

        # 3. Create Opportunity if requested
        opp = None
        if create_opportunity:
            opp_name = opportunity_name or f"{account.name} — Initial Deal"
            opp = await self._opp_repo.create(
                {
                    "account_id": account.id,
                    "primary_contact_id": contact.id,
                    "name": opp_name,
                    "amount": opportunity_amount,
                }
            )

        # 4. Mark Lead converted
        updated_lead = await self._lead_repo.update(
            lead_id, {"status": LeadStatus.CONVERTED.value}
        )

        return {
            "lead": updated_lead,
            "account": account,
            "contact": contact,
            "opportunity": opp,
        }

    async def search_leads(
        self,
        query: str,
        *,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Lead]:
        """Search leads by text query."""
        return await self._lead_repo.search(query, status=status, limit=limit, offset=offset)

    async def list_leads(
        self,
        *,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Lead]:
        """List leads."""
        return await self._lead_repo.list(status=status, limit=limit, offset=offset)

    async def delete_lead(self, lead_id: str) -> bool:
        """Delete a lead."""
        return await self._lead_repo.delete(lead_id)

