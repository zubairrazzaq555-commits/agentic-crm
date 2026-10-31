"""Agentic CRM — Lead Repository.

Provides database CRUD, search, and list operations for Leads.
"""

from __future__ import annotations

import uuid
from typing import Any, Optional

from sqlalchemy import delete, insert, or_, select, update

from src.crm.models import Lead, LeadStatus, _utcnow, leads_table
from src.database.connection import DatabaseManager


class LeadRepository:
    """Async database repository for Lead entities."""

    def __init__(self, db: DatabaseManager) -> None:
        self._db = db

    async def create(self, lead_data: Lead | dict[str, Any]) -> Lead:
        """Create and persist a new Lead."""
        data = lead_data.to_dict() if isinstance(lead_data, Lead) else dict(lead_data)

        if not data.get("id"):
            data["id"] = str(uuid.uuid4())
        now = _utcnow()
        if not data.get("created_at"):
            data["created_at"] = now
        if not data.get("updated_at"):
            data["updated_at"] = now
        if not data.get("status"):
            data["status"] = LeadStatus.NEW.value

        async with self._db.connection() as conn:
            await conn.execute(insert(leads_table).values(**data))
            await conn.commit()

        return Lead.from_row(data)

    async def get_by_id(self, lead_id: str) -> Optional[Lead]:
        """Fetch a single lead by its ID."""
        async with self._db.connection() as conn:
            stmt = select(leads_table).where(leads_table.c.id == lead_id)
            result = await conn.execute(stmt)
            row = result.mappings().first()
            return Lead.from_row(row) if row else None

    async def get_by_email(self, email: str) -> Optional[Lead]:
        """Fetch a single lead by its email address."""
        async with self._db.connection() as conn:
            stmt = select(leads_table).where(leads_table.c.email == email.strip().lower())
            result = await conn.execute(stmt)
            row = result.mappings().first()
            return Lead.from_row(row) if row else None

    async def update(self, lead_id: str, updates: dict[str, Any]) -> Optional[Lead]:
        """Update fields of an existing lead."""
        cleaned_updates = dict(updates)
        cleaned_updates.pop("id", None)
        cleaned_updates.pop("created_at", None)
        cleaned_updates["updated_at"] = _utcnow()

        async with self._db.connection() as conn:
            stmt = (
                update(leads_table)
                .where(leads_table.c.id == lead_id)
                .values(**cleaned_updates)
            )
            result = await conn.execute(stmt)
            await conn.commit()

            if result.rowcount == 0:
                return None

        return await self.get_by_id(lead_id)

    async def delete(self, lead_id: str) -> bool:
        """Delete a lead by its ID."""
        async with self._db.connection() as conn:
            stmt = delete(leads_table).where(leads_table.c.id == lead_id)
            result = await conn.execute(stmt)
            await conn.commit()
            return result.rowcount > 0

    async def search(
        self,
        query: str,
        *,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Lead]:
        """Search leads by name, email, company, or title."""
        pattern = f"%{query}%"
        stmt = select(leads_table).where(
            or_(
                leads_table.c.first_name.ilike(pattern),
                leads_table.c.last_name.ilike(pattern),
                leads_table.c.email.ilike(pattern),
                leads_table.c.company.ilike(pattern),
                leads_table.c.title.ilike(pattern),
            )
        )
        if status:
            stmt = stmt.where(leads_table.c.status == status)

        stmt = stmt.order_by(leads_table.c.created_at.desc()).limit(limit).offset(offset)

        async with self._db.connection() as conn:
            result = await conn.execute(stmt)
            return [Lead.from_row(row) for row in result.mappings().all()]

    async def list(
        self,
        *,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Lead]:
        """List leads with optional status filter, sorted by created_at descending."""
        stmt = select(leads_table)
        if status:
            stmt = stmt.where(leads_table.c.status == status)

        stmt = stmt.order_by(leads_table.c.created_at.desc()).limit(limit).offset(offset)

        async with self._db.connection() as conn:
            result = await conn.execute(stmt)
            return [Lead.from_row(row) for row in result.mappings().all()]

