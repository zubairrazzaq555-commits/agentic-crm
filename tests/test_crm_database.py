"""Tests for CRM Database Foundation & Relationships (Milestone 5.4).

Verifies:
- Table creation and schema initialization for all CRM entities
- Foreign key constraint enforcement in SQLite
- Cascade deletes (Account -> Opportunity -> Deal)
- Set NULL on delete (Account -> Contact)
- Unique constraints
"""

from __future__ import annotations

from pathlib import Path
import pytest
from sqlalchemy import inspect, insert, select, text
from sqlalchemy.exc import IntegrityError

from src.crm.models import (
    accounts_table,
    contacts_table,
    deals_table,
    leads_table,
    opportunities_table,
)
from src.database.connection import DatabaseManager


@pytest.fixture()
async def crm_db(tmp_path: Path) -> DatabaseManager:
    """Provide an isolated, initialized database manager for CRM testing."""
    db_file = tmp_path / "crm_test.db"
    url = f"sqlite+aiosqlite:///{db_file.as_posix()}"
    manager = DatabaseManager(url)
    await manager.init_db()
    yield manager
    await manager.dispose()


class TestCRMDatabaseSchema:
    """Verify table creation and schema definitions."""

    async def test_all_crm_tables_created(self, crm_db: DatabaseManager) -> None:
        async with crm_db.connection() as conn:
            table_names = await conn.run_sync(
                lambda sync_conn: inspect(sync_conn).get_table_names()
            )
            assert "tasks" in table_names
            assert "leads" in table_names
            assert "accounts" in table_names
            assert "contacts" in table_names
            assert "opportunities" in table_names
            assert "deals" in table_names

    async def test_sqlite_foreign_keys_pragma_enabled(self, crm_db: DatabaseManager) -> None:
        async with crm_db.connection() as conn:
            result = await conn.execute(text("PRAGMA foreign_keys;"))
            fk_enabled = result.scalar()
            assert fk_enabled == 1

    async def test_account_unique_name_constraint(self, crm_db: DatabaseManager) -> None:
        async with crm_db.connection() as conn:
            await conn.execute(
                insert(accounts_table).values(
                    id="acc-1",
                    name="Acme Corp",
                    tier="enterprise",
                )
            )
            await conn.commit()

            with pytest.raises(IntegrityError):
                await conn.execute(
                    insert(accounts_table).values(
                        id="acc-2",
                        name="Acme Corp",  # Duplicate name
                        tier="smb",
                    )
                )
                await conn.commit()


class TestCRMRelationshipsAndCascades:
    """Verify foreign key enforcement and cascade behaviors."""

    async def test_contact_foreign_key_to_account_enforced(self, crm_db: DatabaseManager) -> None:
        async with crm_db.connection() as conn:
            with pytest.raises(IntegrityError):
                await conn.execute(
                    insert(contacts_table).values(
                        id="cnt-1",
                        account_id="nonexistent-account-id",
                        first_name="Jane",
                        last_name="Doe",
                        email="jane@example.com",
                    )
                )
                await conn.commit()

    async def test_opportunity_foreign_key_to_account_enforced(self, crm_db: DatabaseManager) -> None:
        async with crm_db.connection() as conn:
            with pytest.raises(IntegrityError):
                await conn.execute(
                    insert(opportunities_table).values(
                        id="opp-1",
                        account_id="nonexistent-account-id",
                        name="Cloud Migration",
                    )
                )
                await conn.commit()

    async def test_deal_foreign_key_to_opportunity_enforced(self, crm_db: DatabaseManager) -> None:
        async with crm_db.connection() as conn:
            with pytest.raises(IntegrityError):
                await conn.execute(
                    insert(deals_table).values(
                        id="deal-1",
                        opportunity_id="nonexistent-opp-id",
                        name="Standard Contract",
                    )
                )
                await conn.commit()

    async def test_cascade_delete_account_deletes_opportunity_and_deal(
        self, crm_db: DatabaseManager
    ) -> None:
        """Deleting an account must cascade-delete its opportunities and deals."""
        async with crm_db.connection() as conn:
            # 1. Insert Account
            await conn.execute(
                insert(accounts_table).values(
                    id="acc-cascade",
                    name="Cascade Corp",
                )
            )
            # 2. Insert Opportunity
            await conn.execute(
                insert(opportunities_table).values(
                    id="opp-cascade",
                    account_id="acc-cascade",
                    name="Big Deal",
                    amount=50000.0,
                )
            )
            # 3. Insert Deal
            await conn.execute(
                insert(deals_table).values(
                    id="deal-cascade",
                    opportunity_id="opp-cascade",
                    name="Q4 Contract",
                    deal_value=50000.0,
                    final_amount=50000.0,
                )
            )
            await conn.commit()

            # 4. Delete the account
            await conn.execute(
                text("DELETE FROM accounts WHERE id = 'acc-cascade'")
            )
            await conn.commit()

            # 5. Check opportunities and deals are deleted
            opp_res = await conn.execute(
                select(opportunities_table).where(opportunities_table.c.id == "opp-cascade")
            )
            assert opp_res.first() is None

            deal_res = await conn.execute(
                select(deals_table).where(deals_table.c.id == "deal-cascade")
            )
            assert deal_res.first() is None

    async def test_account_delete_sets_contact_account_id_null(
        self, crm_db: DatabaseManager
    ) -> None:
        """Deleting an account should set contact account_id to NULL, not delete the contact."""
        async with crm_db.connection() as conn:
            await conn.execute(
                insert(accounts_table).values(
                    id="acc-parent",
                    name="Parent Corp",
                )
            )
            await conn.execute(
                insert(contacts_table).values(
                    id="cnt-survive",
                    account_id="acc-parent",
                    first_name="Bob",
                    last_name="Smith",
                    email="bob@example.com",
                )
            )
            await conn.commit()

            await conn.execute(text("DELETE FROM accounts WHERE id = 'acc-parent'"))
            await conn.commit()

            contact_res = await conn.execute(
                select(contacts_table).where(contacts_table.c.id == "cnt-survive")
            )
            contact_row = contact_res.mappings().first()
            assert contact_row is not None
            assert contact_row["account_id"] is None

