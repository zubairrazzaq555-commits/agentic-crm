"""Agentic CRM — Contact Repository.

Provides database CRUD, search, and list operations for Contacts.
"""

from __future__ import annotations

import uuid
from typing import Any, Optional

from sqlalchemy import delete, insert, or_, select, update

from src.crm.models import Contact, _utcnow, contacts_table
from src.database.connection import DatabaseManager


class ContactRepository:
    """Async database repository for Contact entities."""

    def __init__(self, db: DatabaseManager) -> None:
        self._db = db

    async def create(self, contact_data: Contact | dict[str, Any]) -> Contact:
        """Create and persist a new Contact."""
        data = contact_data.to_dict() if isinstance(contact_data, Contact) else dict(contact_data)

        if not data.get("id"):
            data["id"] = str(uuid.uuid4())
        now = _utcnow()
        if not data.get("created_at"):
            data["created_at"] = now
        if not data.get("updated_at"):
            data["updated_at"] = now
        data["is_primary"] = bool(data.get("is_primary", False))

        async with self._db.connection() as conn:
            await conn.execute(insert(contacts_table).values(**data))
            await conn.commit()

        return Contact.from_row(data)

    async def get_by_id(self, contact_id: str) -> Optional[Contact]:
        """Fetch a single contact by its ID."""
        async with self._db.connection() as conn:
            stmt = select(contacts_table).where(contacts_table.c.id == contact_id)
            result = await conn.execute(stmt)
            row = result.mappings().first()
            return Contact.from_row(row) if row else None

    async def get_by_email(self, email: str) -> Optional[Contact]:
        """Fetch a single contact by its email address."""
        async with self._db.connection() as conn:
            stmt = select(contacts_table).where(contacts_table.c.email == email.strip().lower())
            result = await conn.execute(stmt)
            row = result.mappings().first()
            return Contact.from_row(row) if row else None

    async def list_by_account(self, account_id: str) -> list[Contact]:
        """Fetch all contacts associated with a given account."""
        async with self._db.connection() as conn:
            stmt = (
                select(contacts_table)
                .where(contacts_table.c.account_id == account_id)
                .order_by(contacts_table.c.is_primary.desc(), contacts_table.c.last_name.asc())
            )
            result = await conn.execute(stmt)
            return [Contact.from_row(row) for row in result.mappings().all()]

    async def update(self, contact_id: str, updates: dict[str, Any]) -> Optional[Contact]:
        """Update fields of an existing contact."""
        cleaned_updates = dict(updates)
        cleaned_updates.pop("id", None)
        cleaned_updates.pop("created_at", None)
        cleaned_updates["updated_at"] = _utcnow()
        if "is_primary" in cleaned_updates:
            cleaned_updates["is_primary"] = bool(cleaned_updates["is_primary"])

        async with self._db.connection() as conn:
            stmt = (
                update(contacts_table)
                .where(contacts_table.c.id == contact_id)
                .values(**cleaned_updates)
            )
            result = await conn.execute(stmt)
            await conn.commit()

            if result.rowcount == 0:
                return None

        return await self.get_by_id(contact_id)

    async def delete(self, contact_id: str) -> bool:
        """Delete a contact by its ID."""
        async with self._db.connection() as conn:
            stmt = delete(contacts_table).where(contacts_table.c.id == contact_id)
            result = await conn.execute(stmt)
            await conn.commit()
            return result.rowcount > 0

    async def search(
        self,
        query: str,
        *,
        account_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Contact]:
        """Search contacts by name, email, title, or department."""
        pattern = f"%{query}%"
        stmt = select(contacts_table).where(
            or_(
                contacts_table.c.first_name.ilike(pattern),
                contacts_table.c.last_name.ilike(pattern),
                contacts_table.c.email.ilike(pattern),
                contacts_table.c.title.ilike(pattern),
                contacts_table.c.department.ilike(pattern),
            )
        )
        if account_id:
            stmt = stmt.where(contacts_table.c.account_id == account_id)

        stmt = stmt.order_by(contacts_table.c.last_name.asc()).limit(limit).offset(offset)

        async with self._db.connection() as conn:
            result = await conn.execute(stmt)
            return [Contact.from_row(row) for row in result.mappings().all()]

    async def list(
        self,
        *,
        account_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Contact]:
        """List contacts with optional account filter."""
        stmt = select(contacts_table)
        if account_id:
            stmt = stmt.where(contacts_table.c.account_id == account_id)

        stmt = stmt.order_by(contacts_table.c.created_at.desc()).limit(limit).offset(offset)

        async with self._db.connection() as conn:
            result = await conn.execute(stmt)
            return [Contact.from_row(row) for row in result.mappings().all()]

