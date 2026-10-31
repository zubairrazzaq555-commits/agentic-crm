"""Agentic CRM — Deal Repository.

Provides database CRUD, search, and list operations for Deals.
"""

from __future__ import annotations

import uuid
from typing import Any, Optional

from sqlalchemy import delete, insert, or_, select, update

from src.crm.models import Deal, DealStatus, _utcnow, deals_table
from src.database.connection import DatabaseManager


class DealRepository:
    """Async database repository for Deal entities."""

    def __init__(self, db: DatabaseManager) -> None:
        self._db = db

    async def create(self, deal_data: Deal | dict[str, Any]) -> Deal:
        """Create and persist a new Deal."""
        data = deal_data.to_dict() if isinstance(deal_data, Deal) else dict(deal_data)

        if not data.get("id"):
            data["id"] = str(uuid.uuid4())
        now = _utcnow()
        if not data.get("created_at"):
            data["created_at"] = now
        if not data.get("updated_at"):
            data["updated_at"] = now
        if not data.get("status"):
            data["status"] = DealStatus.DRAFT.value

        deal_val = float(data.get("deal_value") or 0.0)
        discount = float(data.get("discount_percentage") or 0.0)
        data["deal_value"] = deal_val
        data["discount_percentage"] = discount
        if "final_amount" not in data or data["final_amount"] is None or data["final_amount"] == 0.0:
            data["final_amount"] = round(deal_val * (1.0 - (discount / 100.0)), 2)
        else:
            data["final_amount"] = float(data["final_amount"])

        async with self._db.connection() as conn:
            await conn.execute(insert(deals_table).values(**data))
            await conn.commit()

        return Deal.from_row(data)

    async def get_by_id(self, deal_id: str) -> Optional[Deal]:
        """Fetch a single deal by its ID."""
        async with self._db.connection() as conn:
            stmt = select(deals_table).where(deals_table.c.id == deal_id)
            result = await conn.execute(stmt)
            row = result.mappings().first()
            return Deal.from_row(row) if row else None

    async def list_by_opportunity(self, opportunity_id: str) -> list[Deal]:
        """Fetch all deals associated with a given opportunity."""
        async with self._db.connection() as conn:
            stmt = (
                select(deals_table)
                .where(deals_table.c.opportunity_id == opportunity_id)
                .order_by(deals_table.c.created_at.desc())
            )
            result = await conn.execute(stmt)
            return [Deal.from_row(row) for row in result.mappings().all()]

    async def update(self, deal_id: str, updates: dict[str, Any]) -> Optional[Deal]:
        """Update fields of an existing deal."""
        cleaned_updates = dict(updates)
        cleaned_updates.pop("id", None)
        cleaned_updates.pop("opportunity_id", None)
        cleaned_updates.pop("created_at", None)
        cleaned_updates["updated_at"] = _utcnow()

        # Recalculate final_amount if deal_value or discount_percentage is updated
        existing = await self.get_by_id(deal_id)
        if not existing:
            return None

        deal_val = (
            float(cleaned_updates["deal_value"])
            if "deal_value" in cleaned_updates and cleaned_updates["deal_value"] is not None
            else existing.deal_value
        )
        discount = (
            float(cleaned_updates["discount_percentage"])
            if "discount_percentage" in cleaned_updates and cleaned_updates["discount_percentage"] is not None
            else existing.discount_percentage
        )
        if "deal_value" in cleaned_updates:
            cleaned_updates["deal_value"] = deal_val
        if "discount_percentage" in cleaned_updates:
            cleaned_updates["discount_percentage"] = discount

        if "final_amount" not in cleaned_updates:
            cleaned_updates["final_amount"] = round(deal_val * (1.0 - (discount / 100.0)), 2)
        else:
            cleaned_updates["final_amount"] = float(cleaned_updates["final_amount"])

        async with self._db.connection() as conn:
            stmt = (
                update(deals_table)
                .where(deals_table.c.id == deal_id)
                .values(**cleaned_updates)
            )
            result = await conn.execute(stmt)
            await conn.commit()

            if result.rowcount == 0:
                return None

        return await self.get_by_id(deal_id)

    async def delete(self, deal_id: str) -> bool:
        """Delete a deal by its ID."""
        async with self._db.connection() as conn:
            stmt = delete(deals_table).where(deals_table.c.id == deal_id)
            result = await conn.execute(stmt)
            await conn.commit()
            return result.rowcount > 0

    async def search(
        self,
        query: str,
        *,
        status: Optional[str] = None,
        opportunity_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Deal]:
        """Search deals by name or payment terms."""
        pattern = f"%{query}%"
        stmt = select(deals_table).where(
            or_(
                deals_table.c.name.ilike(pattern),
                deals_table.c.payment_terms.ilike(pattern),
            )
        )
        if status:
            stmt = stmt.where(deals_table.c.status == status)
        if opportunity_id:
            stmt = stmt.where(deals_table.c.opportunity_id == opportunity_id)

        stmt = stmt.order_by(deals_table.c.created_at.desc()).limit(limit).offset(offset)

        async with self._db.connection() as conn:
            result = await conn.execute(stmt)
            return [Deal.from_row(row) for row in result.mappings().all()]

    async def list(
        self,
        *,
        status: Optional[str] = None,
        opportunity_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Deal]:
        """List deals with optional status and opportunity filters."""
        stmt = select(deals_table)
        if status:
            stmt = stmt.where(deals_table.c.status == status)
        if opportunity_id:
            stmt = stmt.where(deals_table.c.opportunity_id == opportunity_id)

        stmt = stmt.order_by(deals_table.c.created_at.desc()).limit(limit).offset(offset)

        async with self._db.connection() as conn:
            result = await conn.execute(stmt)
            return [Deal.from_row(row) for row in result.mappings().all()]

