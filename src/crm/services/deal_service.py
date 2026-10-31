"""Agentic CRM — Deal Service.

Encapsulates business rules and calculations for Deal management:
- Automated discount calculation & final amount determination
- Deal closing & opportunity synchronization
- Contract date validations
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from src.crm.models import Deal, DealStatus, OpportunityStage, _utcnow
from src.crm.repositories.deal_repo import DealRepository
from src.crm.repositories.opportunity_repo import OpportunityRepository
from src.database.connection import DatabaseManager


class DealService:
    """Business logic service for Deal operations."""

    def __init__(self, db: DatabaseManager) -> None:
        self._db = db
        self._deal_repo = DealRepository(db)
        self._opp_repo = OpportunityRepository(db)

    async def create_deal(
        self,
        *,
        opportunity_id: str,
        name: str,
        deal_value: float,
        discount_percentage: float = 0.0,
        payment_terms: Optional[str] = None,
        contract_start_date: Optional[datetime] = None,
        contract_end_date: Optional[datetime] = None,
    ) -> Deal:
        """Validate, calculate discount, and create a Deal."""
        if not name or not name.strip():
            raise ValueError("Deal name is required and cannot be empty.")

        opp = await self._opp_repo.get_by_id(opportunity_id)
        if not opp:
            raise ValueError(f"Opportunity with ID '{opportunity_id}' does not exist.")

        if deal_value < 0:
            raise ValueError(f"Deal value cannot be negative, got {deal_value}.")

        if not (0.0 <= discount_percentage <= 100.0):
            raise ValueError(f"Discount percentage must be between 0 and 100, got {discount_percentage}.")

        if contract_start_date and contract_end_date:
            if contract_end_date < contract_start_date:
                raise ValueError("Contract end date cannot be earlier than contract start date.")

        final_amount = round(deal_value * (1.0 - (discount_percentage / 100.0)), 2)

        deal = Deal(
            id="",
            opportunity_id=opportunity_id,
            name=name.strip(),
            deal_value=float(deal_value),
            discount_percentage=float(discount_percentage),
            final_amount=final_amount,
            status=DealStatus.DRAFT.value,
            payment_terms=payment_terms.strip() if payment_terms else None,
            contract_start_date=contract_start_date,
            contract_end_date=contract_end_date,
        )
        return await self._deal_repo.create(deal)

    async def get_deal(self, deal_id: str) -> Optional[Deal]:
        """Fetch deal by ID."""
        return await self._deal_repo.get_by_id(deal_id)

    async def update_deal(self, deal_id: str, **updates: Any) -> Optional[Deal]:
        """Validate and apply updates to a deal."""
        existing = await self._deal_repo.get_by_id(deal_id)
        if not existing:
            raise ValueError(f"Deal not found with ID '{deal_id}'.")

        if "discount_percentage" in updates and updates["discount_percentage"] is not None:
            disc = float(updates["discount_percentage"])
            if not (0.0 <= disc <= 100.0):
                raise ValueError(f"Discount percentage must be between 0 and 100, got {disc}.")
            updates["discount_percentage"] = disc

        if "deal_value" in updates and updates["deal_value"] is not None:
            val = float(updates["deal_value"])
            if val < 0:
                raise ValueError("Deal value cannot be negative.")
            updates["deal_value"] = val

        if "status" in updates and updates["status"]:
            valid_statuses = {s.value for s in DealStatus}
            if updates["status"] not in valid_statuses:
                raise ValueError(f"Invalid status '{updates['status']}'. Must be one of {valid_statuses}.")

        return await self._deal_repo.update(deal_id, updates)

    async def apply_discount(self, deal_id: str, discount_percentage: float) -> Deal:
        """Apply a new discount percentage to a deal."""
        if not (0.0 <= discount_percentage <= 100.0):
            raise ValueError(f"Discount percentage must be between 0 and 100, got {discount_percentage}.")
        updated = await self.update_deal(deal_id, discount_percentage=discount_percentage)
        assert updated is not None
        return updated

    async def close_deal(self, deal_id: str, *, accepted: bool) -> Deal:
        """
        Close a deal.

        If accepted:
        - Sets deal status to 'accepted'.
        - Sets closed_at timestamp.
        - Automatically advances the associated Opportunity to 'closed_won'!

        If rejected:
        - Sets deal status to 'rejected'.
        - Sets closed_at timestamp.
        """
        deal = await self._deal_repo.get_by_id(deal_id)
        if not deal:
            raise ValueError(f"Deal not found with ID '{deal_id}'.")

        new_status = DealStatus.ACCEPTED.value if accepted else DealStatus.REJECTED.value
        now = _utcnow()

        updated_deal = await self._deal_repo.update(
            deal_id,
            {
                "status": new_status,
                "closed_at": now,
            },
        )
        assert updated_deal is not None

        if accepted:
            # Synchronize opportunity stage to closed_won
            await self._opp_repo.update(
                deal.opportunity_id,
                {
                    "stage": OpportunityStage.CLOSED_WON.value,
                    "probability": 100,
                    "amount": updated_deal.final_amount,
                },
            )

        return updated_deal

    async def list_deals_by_opportunity(self, opportunity_id: str) -> list[Deal]:
        """List deals for an opportunity."""
        return await self._deal_repo.list_by_opportunity(opportunity_id)

    async def search_deals(
        self,
        query: str,
        *,
        status: Optional[str] = None,
        opportunity_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Deal]:
        """Search deals."""
        return await self._deal_repo.search(query, status=status, opportunity_id=opportunity_id, limit=limit, offset=offset)

    async def list_deals(
        self,
        *,
        status: Optional[str] = None,
        opportunity_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Deal]:
        """List deals."""
        return await self._deal_repo.list(status=status, opportunity_id=opportunity_id, limit=limit, offset=offset)

    async def delete_deal(self, deal_id: str) -> bool:
        """Delete a deal."""
        return await self._deal_repo.delete(deal_id)

