"""Agentic CRM — Opportunity Repository.

Provides database CRUD, search, and list operations for Opportunities.
"""

from __future__ import annotations

import uuid
from typing import Any, Optional

from sqlalchemy import delete, insert, or_, select, update

from src.crm.models import (
    Opportunity,
    OpportunityStage,
    STAGE_PROBABILITIES,
    _utcnow,
    opportunities_table,
)
from src.database.connection import DatabaseManager


class OpportunityRepository:
    """Async database repository for Opportunity entities."""

    def __init__(self, db: DatabaseManager) -> None:
        self._db = db

    async def create(self, opp_data: Opportunity | dict[str, Any]) -> Opportunity:
        """Create and persist a new Opportunity."""
        data = opp_data.to_dict() if isinstance(opp_data, Opportunity) else dict(opp_data)

        if not data.get("id"):
            data["id"] = str(uuid.uuid4())
        now = _utcnow()
        if not data.get("created_at"):
            data["created_at"] = now
        if not data.get("updated_at"):
            data["updated_at"] = now
        if not data.get("stage"):
            data["stage"] = OpportunityStage.PROSPECTING.value
        if "amount" in data and data["amount"] is not None:
            data["amount"] = float(data["amount"])
        else:
            data["amount"] = 0.0

        if "probability" not in data or data["probability"] is None:
            data["probability"] = STAGE_PROBABILITIES.get(data["stage"], 10)
        else:
            data["probability"] = int(data["probability"])

        async with self._db.connection() as conn:
            await conn.execute(insert(opportunities_table).values(**data))
            await conn.commit()

        return Opportunity.from_row(data)

    async def get_by_id(self, opp_id: str) -> Optional[Opportunity]:
        """Fetch a single opportunity by its ID."""
        async with self._db.connection() as conn:
            stmt = select(opportunities_table).where(opportunities_table.c.id == opp_id)
            result = await conn.execute(stmt)
            row = result.mappings().first()
            return Opportunity.from_row(row) if row else None

    async def list_by_account(self, account_id: str) -> list[Opportunity]:
        """Fetch all opportunities associated with a given account."""
        async with self._db.connection() as conn:
            stmt = (
                select(opportunities_table)
                .where(opportunities_table.c.account_id == account_id)
                .order_by(opportunities_table.c.created_at.desc())
            )
            result = await conn.execute(stmt)
            return [Opportunity.from_row(row) for row in result.mappings().all()]

    async def update(self, opp_id: str, updates: dict[str, Any]) -> Optional[Opportunity]:
        """Update fields of an existing opportunity."""
        cleaned_updates = dict(updates)
        cleaned_updates.pop("id", None)
        cleaned_updates.pop("account_id", None)  # Prevent orphan re-parenting via simple update
        cleaned_updates.pop("created_at", None)
        cleaned_updates["updated_at"] = _utcnow()

        if "amount" in cleaned_updates and cleaned_updates["amount"] is not None:
            cleaned_updates["amount"] = float(cleaned_updates["amount"])
        if "probability" in cleaned_updates and cleaned_updates["probability"] is not None:
            cleaned_updates["probability"] = int(cleaned_updates["probability"])

        async with self._db.connection() as conn:
            stmt = (
                update(opportunities_table)
                .where(opportunities_table.c.id == opp_id)
                .values(**cleaned_updates)
            )
            result = await conn.execute(stmt)
            await conn.commit()

            if result.rowcount == 0:
                return None

        return await self.get_by_id(opp_id)

    async def delete(self, opp_id: str) -> bool:
        """Delete an opportunity by its ID."""
        async with self._db.connection() as conn:
            stmt = delete(opportunities_table).where(opportunities_table.c.id == opp_id)
            result = await conn.execute(stmt)
            await conn.commit()
            return result.rowcount > 0

    async def search(
        self,
        query: str,
        *,
        stage: Optional[str] = None,
        account_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Opportunity]:
        """Search opportunities by name."""
        pattern = f"%{query}%"
        stmt = select(opportunities_table).where(opportunities_table.c.name.ilike(pattern))
        if stage:
            stmt = stmt.where(opportunities_table.c.stage == stage)
        if account_id:
            stmt = stmt.where(opportunities_table.c.account_id == account_id)

        stmt = stmt.order_by(opportunities_table.c.created_at.desc()).limit(limit).offset(offset)

        async with self._db.connection() as conn:
            result = await conn.execute(stmt)
            return [Opportunity.from_row(row) for row in result.mappings().all()]

    async def list(
        self,
        *,
        stage: Optional[str] = None,
        account_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Opportunity]:
        """List opportunities with optional stage and account filters."""
        stmt = select(opportunities_table)
        if stage:
            stmt = stmt.where(opportunities_table.c.stage == stage)
        if account_id:
            stmt = stmt.where(opportunities_table.c.account_id == account_id)

        stmt = stmt.order_by(opportunities_table.c.created_at.desc()).limit(limit).offset(offset)

        async with self._db.connection() as conn:
            result = await conn.execute(stmt)
            return [Opportunity.from_row(row) for row in result.mappings().all()]

