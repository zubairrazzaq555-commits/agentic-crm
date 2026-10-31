"""Agentic CRM — Opportunity Service.

Encapsulates business rules and validation for Opportunity management:
- Pipeline stage progression
- Automated win-probability calculation
- Account & primary contact validation
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from src.crm.models import (
    Opportunity,
    OpportunityStage,
    STAGE_PROBABILITIES,
)
from src.crm.repositories.account_repo import AccountRepository
from src.crm.repositories.contact_repo import ContactRepository
from src.crm.repositories.opportunity_repo import OpportunityRepository
from src.database.connection import DatabaseManager


class OpportunityService:
    """Business logic service for Opportunity operations."""

    def __init__(self, db: DatabaseManager) -> None:
        self._db = db
        self._opp_repo = OpportunityRepository(db)
        self._account_repo = AccountRepository(db)
        self._contact_repo = ContactRepository(db)

    async def create_opportunity(
        self,
        *,
        account_id: str,
        name: str,
        stage: str = OpportunityStage.PROSPECTING.value,
        amount: float = 0.0,
        probability: Optional[int] = None,
        primary_contact_id: Optional[str] = None,
        close_date: Optional[datetime] = None,
    ) -> Opportunity:
        """Validate and create a new Opportunity."""
        if not name or not name.strip():
            raise ValueError("Opportunity name is required and cannot be empty.")

        account = await self._account_repo.get_by_id(account_id)
        if not account:
            raise ValueError(f"Account with ID '{account_id}' does not exist.")

        if primary_contact_id:
            contact = await self._contact_repo.get_by_id(primary_contact_id)
            if not contact:
                raise ValueError(f"Contact with ID '{primary_contact_id}' does not exist.")

        valid_stages = {s.value for s in OpportunityStage}
        if stage not in valid_stages:
            raise ValueError(f"Invalid stage '{stage}'. Must be one of {valid_stages}.")

        if amount < 0:
            raise ValueError(f"Opportunity amount cannot be negative, got {amount}.")

        if probability is None:
            prob = STAGE_PROBABILITIES.get(stage, 10)
        else:
            if not (0 <= probability <= 100):
                raise ValueError(f"Probability must be between 0 and 100, got {probability}.")
            prob = probability

        opp = Opportunity(
            id="",
            account_id=account_id,
            primary_contact_id=primary_contact_id,
            name=name.strip(),
            stage=stage,
            amount=float(amount),
            probability=prob,
            close_date=close_date,
        )
        return await self._opp_repo.create(opp)

    async def get_opportunity(self, opp_id: str) -> Optional[Opportunity]:
        """Fetch opportunity by ID."""
        return await self._opp_repo.get_by_id(opp_id)

    async def update_opportunity(self, opp_id: str, **updates: Any) -> Optional[Opportunity]:
        """Validate and apply updates to an opportunity."""
        existing = await self._opp_repo.get_by_id(opp_id)
        if not existing:
            raise ValueError(f"Opportunity not found with ID '{opp_id}'.")

        if "amount" in updates and updates["amount"] is not None:
            amt = float(updates["amount"])
            if amt < 0:
                raise ValueError("Amount cannot be negative.")
            updates["amount"] = amt

        if "stage" in updates and updates["stage"]:
            valid_stages = {s.value for s in OpportunityStage}
            if updates["stage"] not in valid_stages:
                raise ValueError(f"Invalid stage '{updates['stage']}'. Must be one of {valid_stages}.")
            # If probability was not explicitly supplied, update probability to match new stage
            if "probability" not in updates:
                updates["probability"] = STAGE_PROBABILITIES.get(updates["stage"], existing.probability)

        if "probability" in updates and updates["probability"] is not None:
            prob = int(updates["probability"])
            if not (0 <= prob <= 100):
                raise ValueError(f"Probability must be between 0 and 100, got {prob}.")
            updates["probability"] = prob

        if "primary_contact_id" in updates and updates["primary_contact_id"]:
            contact = await self._contact_repo.get_by_id(updates["primary_contact_id"])
            if not contact:
                raise ValueError(f"Contact with ID '{updates['primary_contact_id']}' does not exist.")

        return await self._opp_repo.update(opp_id, updates)

    async def advance_stage(self, opp_id: str, new_stage: str) -> Opportunity:
        """Advance an opportunity to a new stage, adjusting its win-probability."""
        updated = await self.update_opportunity(opp_id, stage=new_stage)
        assert updated is not None
        return updated

    async def list_opportunities_by_account(self, account_id: str) -> list[Opportunity]:
        """List opportunities for an account."""
        return await self._opp_repo.list_by_account(account_id)

    async def search_opportunities(
        self,
        query: str,
        *,
        stage: Optional[str] = None,
        account_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Opportunity]:
        """Search opportunities."""
        return await self._opp_repo.search(query, stage=stage, account_id=account_id, limit=limit, offset=offset)

    async def list_opportunities(
        self,
        *,
        stage: Optional[str] = None,
        account_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Opportunity]:
        """List opportunities."""
        return await self._opp_repo.list(stage=stage, account_id=account_id, limit=limit, offset=offset)

    async def delete_opportunity(self, opp_id: str) -> bool:
        """Delete an opportunity."""
        return await self._opp_repo.delete(opp_id)

