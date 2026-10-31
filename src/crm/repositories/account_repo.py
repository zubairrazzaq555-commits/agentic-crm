"""Agentic CRM — Account Repository.

Provides database CRUD, search, and list operations for Accounts.
"""

from __future__ import annotations

import uuid
from typing import Any, Optional

from sqlalchemy import delete, insert, or_, select, update

from src.crm.models import Account, AccountStatus, AccountTier, _utcnow, accounts_table
from src.database.connection import DatabaseManager


class AccountRepository:
    """Async database repository for Account entities."""

    def __init__(self, db: DatabaseManager) -> None:
        self._db = db

    async def create(self, account_data: Account | dict[str, Any]) -> Account:
        """Create and persist a new Account."""
        data = account_data.to_dict() if isinstance(account_data, Account) else dict(account_data)

        if not data.get("id"):
            data["id"] = str(uuid.uuid4())
        now = _utcnow()
        if not data.get("created_at"):
            data["created_at"] = now
        if not data.get("updated_at"):
            data["updated_at"] = now
        if not data.get("tier"):
            data["tier"] = AccountTier.SMB.value
        if not data.get("status"):
            data["status"] = AccountStatus.ACTIVE.value
        if "annual_revenue" in data and data["annual_revenue"] is not None:
            data["annual_revenue"] = float(data["annual_revenue"])
        else:
            data["annual_revenue"] = 0.0

        async with self._db.connection() as conn:
            await conn.execute(insert(accounts_table).values(**data))
            await conn.commit()

        return Account.from_row(data)

    async def get_by_id(self, account_id: str) -> Optional[Account]:
        """Fetch a single account by ID."""
        async with self._db.connection() as conn:
            stmt = select(accounts_table).where(accounts_table.c.id == account_id)
            result = await conn.execute(stmt)
            row = result.mappings().first()
            return Account.from_row(row) if row else None

    async def get_by_name(self, name: str) -> Optional[Account]:
        """Fetch a single account by its unique company name."""
        async with self._db.connection() as conn:
            stmt = select(accounts_table).where(accounts_table.c.name == name.strip())
            result = await conn.execute(stmt)
            row = result.mappings().first()
            return Account.from_row(row) if row else None

    async def update(self, account_id: str, updates: dict[str, Any]) -> Optional[Account]:
        """Update fields of an existing account."""
        cleaned_updates = dict(updates)
        cleaned_updates.pop("id", None)
        cleaned_updates.pop("created_at", None)
        cleaned_updates["updated_at"] = _utcnow()
        if "annual_revenue" in cleaned_updates and cleaned_updates["annual_revenue"] is not None:
            cleaned_updates["annual_revenue"] = float(cleaned_updates["annual_revenue"])

        async with self._db.connection() as conn:
            stmt = (
                update(accounts_table)
                .where(accounts_table.c.id == account_id)
                .values(**cleaned_updates)
            )
            result = await conn.execute(stmt)
            await conn.commit()

            if result.rowcount == 0:
                return None

        return await self.get_by_id(account_id)

    async def delete(self, account_id: str) -> bool:
        """Delete an account by its ID."""
        async with self._db.connection() as conn:
            stmt = delete(accounts_table).where(accounts_table.c.id == account_id)
            result = await conn.execute(stmt)
            await conn.commit()
            return result.rowcount > 0

    async def search(
        self,
        query: str,
        *,
        tier: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Account]:
        """Search accounts by name, industry, website, or city."""
        pattern = f"%{query}%"
        stmt = select(accounts_table).where(
            or_(
                accounts_table.c.name.ilike(pattern),
                accounts_table.c.industry.ilike(pattern),
                accounts_table.c.website.ilike(pattern),
                accounts_table.c.billing_city.ilike(pattern),
            )
        )
        if tier:
            stmt = stmt.where(accounts_table.c.tier == tier)
        if status:
            stmt = stmt.where(accounts_table.c.status == status)

        stmt = stmt.order_by(accounts_table.c.name.asc()).limit(limit).offset(offset)

        async with self._db.connection() as conn:
            result = await conn.execute(stmt)
            return [Account.from_row(row) for row in result.mappings().all()]

    async def list(
        self,
        *,
        tier: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Account]:
        """List accounts with optional filters."""
        stmt = select(accounts_table)
        if tier:
            stmt = stmt.where(accounts_table.c.tier == tier)
        if status:
            stmt = stmt.where(accounts_table.c.status == status)

        stmt = stmt.order_by(accounts_table.c.created_at.desc()).limit(limit).offset(offset)

        async with self._db.connection() as conn:
            result = await conn.execute(stmt)
            return [Account.from_row(row) for row in result.mappings().all()]

