"""Tests for CRM Repositories (Milestone 5.4).

Verifies CRUD, search, and list operations for:
- LeadRepository
- AccountRepository
- ContactRepository
- OpportunityRepository
- DealRepository
"""

from __future__ import annotations

from pathlib import Path
import pytest

from src.crm.models import (
    Account,
    AccountTier,
    Contact,
    Deal,
    DealStatus,
    Lead,
    LeadStatus,
    Opportunity,
    OpportunityStage,
)
from src.crm.repositories import (
    AccountRepository,
    ContactRepository,
    DealRepository,
    LeadRepository,
    OpportunityRepository,
)
from src.database.connection import DatabaseManager


@pytest.fixture()
async def crm_db(tmp_path: Path) -> DatabaseManager:
    """Provide an isolated, initialized database manager for CRM testing."""
    db_file = tmp_path / "crm_repo_test.db"
    url = f"sqlite+aiosqlite:///{db_file.as_posix()}"
    manager = DatabaseManager(url)
    await manager.init_db()
    yield manager
    await manager.dispose()


class TestLeadRepository:
    """Test LeadRepository CRUD, search, and list."""

    async def test_create_and_get_by_id(self, crm_db: DatabaseManager) -> None:
        repo = LeadRepository(crm_db)
        lead = await repo.create(
            {
                "first_name": "Alice",
                "last_name": "Wonder",
                "company": "Wonderland Inc",
                "email": "alice@wonderland.com",
                "score": 75,
            }
        )
        assert lead.id is not None
        assert lead.first_name == "Alice"
        assert lead.score == 75
        assert lead.status == LeadStatus.NEW.value

        fetched = await repo.get_by_id(lead.id)
        assert fetched is not None
        assert fetched.email == "alice@wonderland.com"

    async def test_get_by_email(self, crm_db: DatabaseManager) -> None:
        repo = LeadRepository(crm_db)
        await repo.create(
            {
                "first_name": "Bob",
                "last_name": "Builder",
                "company": "Build Corp",
                "email": "bob@build.com",
            }
        )
        fetched = await repo.get_by_email("bob@build.com")
        assert fetched is not None
        assert fetched.first_name == "Bob"

        assert await repo.get_by_email("nonexistent@build.com") is None

    async def test_update_lead(self, crm_db: DatabaseManager) -> None:
        repo = LeadRepository(crm_db)
        lead = await repo.create(
            {
                "first_name": "Charlie",
                "last_name": "Brown",
                "company": "Peanuts LLC",
                "email": "charlie@peanuts.com",
            }
        )
        updated = await repo.update(
            lead.id,
            {"status": LeadStatus.QUALIFIED.value, "score": 90},
        )
        assert updated is not None
        assert updated.status == LeadStatus.QUALIFIED.value
        assert updated.score == 90
        assert updated.updated_at is not None

        # Updating non-existent returns None
        assert await repo.update("bad-id", {"score": 50}) is None

    async def test_delete_lead(self, crm_db: DatabaseManager) -> None:
        repo = LeadRepository(crm_db)
        lead = await repo.create(
            {
                "first_name": "David",
                "last_name": "Copper",
                "company": "Magic Inc",
                "email": "david@magic.com",
            }
        )
        assert await repo.delete(lead.id) is True
        assert await repo.get_by_id(lead.id) is None
        assert await repo.delete(lead.id) is False

    async def test_search_and_list_leads(self, crm_db: DatabaseManager) -> None:
        repo = LeadRepository(crm_db)
        await repo.create({"first_name": "Emma", "last_name": "Stone", "company": "Hollywood", "email": "emma@film.com", "status": "new"})
        await repo.create({"first_name": "Liam", "last_name": "Neeson", "company": "Action", "email": "liam@action.com", "status": "qualified"})

        search_res = await repo.search("Hollywood")
        assert len(search_res) == 1
        assert search_res[0].first_name == "Emma"

        list_res = await repo.list(status="qualified")
        assert len(list_res) == 1
        assert list_res[0].first_name == "Liam"


class TestAccountRepository:
    """Test AccountRepository CRUD, search, and list."""

    async def test_create_and_get_account(self, crm_db: DatabaseManager) -> None:
        repo = AccountRepository(crm_db)
        account = await repo.create(
            {
                "name": "Global Tech Corp",
                "industry": "Software",
                "tier": AccountTier.ENTERPRISE.value,
                "annual_revenue": 5000000.0,
            }
        )
        assert account.id is not None
        assert account.name == "Global Tech Corp"
        assert account.annual_revenue == 5000000.0

        fetched = await repo.get_by_name("Global Tech Corp")
        assert fetched is not None
        assert fetched.id == account.id

    async def test_update_and_delete_account(self, crm_db: DatabaseManager) -> None:
        repo = AccountRepository(crm_db)
        account = await repo.create({"name": "Small Shop"})
        updated = await repo.update(account.id, {"tier": AccountTier.MID_MARKET.value, "annual_revenue": 100000.0})
        assert updated is not None
        assert updated.tier == AccountTier.MID_MARKET.value
        assert updated.annual_revenue == 100000.0

        deleted = await repo.delete(account.id)
        assert deleted is True
        assert await repo.get_by_id(account.id) is None


class TestContactRepository:
    """Test ContactRepository CRUD, search, and list."""

    async def test_create_and_list_by_account(self, crm_db: DatabaseManager) -> None:
        acc_repo = AccountRepository(crm_db)
        cnt_repo = ContactRepository(crm_db)

        account = await acc_repo.create({"name": "MegaCorp"})
        c1 = await cnt_repo.create(
            {
                "account_id": account.id,
                "first_name": "John",
                "last_name": "Doe",
                "email": "john@megacorp.com",
                "is_primary": True,
            }
        )
        c2 = await cnt_repo.create(
            {
                "account_id": account.id,
                "first_name": "Jane",
                "last_name": "Smith",
                "email": "jane@megacorp.com",
                "is_primary": False,
            }
        )

        contacts = await cnt_repo.list_by_account(account.id)
        assert len(contacts) == 2
        assert contacts[0].id == c1.id  # Primary contact first


class TestOpportunityRepository:
    """Test OpportunityRepository CRUD and queries."""

    async def test_create_and_update_opportunity(self, crm_db: DatabaseManager) -> None:
        acc_repo = AccountRepository(crm_db)
        opp_repo = OpportunityRepository(crm_db)

        acc = await acc_repo.create({"name": "FinTech Innovations"})
        opp = await opp_repo.create(
            {
                "account_id": acc.id,
                "name": "Cloud Infrastructure",
                "amount": 120000.0,
                "stage": OpportunityStage.PROSPECTING.value,
            }
        )
        assert opp.probability == 10  # Auto-assigned default

        updated = await opp_repo.update(
            opp.id,
            {"stage": OpportunityStage.PROPOSAL.value, "probability": 50},
        )
        assert updated is not None
        assert updated.stage == OpportunityStage.PROPOSAL.value
        assert updated.probability == 50


class TestDealRepository:
    """Test DealRepository CRUD, pricing calculation, and list."""

    async def test_create_deal_calculates_final_amount(self, crm_db: DatabaseManager) -> None:
        acc_repo = AccountRepository(crm_db)
        opp_repo = OpportunityRepository(crm_db)
        deal_repo = DealRepository(crm_db)

        acc = await acc_repo.create({"name": "Deal Corp"})
        opp = await opp_repo.create({"account_id": acc.id, "name": "Software License"})

        deal = await deal_repo.create(
            {
                "opportunity_id": opp.id,
                "name": "3-Year Enterprise Subscription",
                "deal_value": 100000.0,
                "discount_percentage": 15.0,
            }
        )
        assert deal.deal_value == 100000.0
        assert deal.discount_percentage == 15.0
        assert deal.final_amount == 85000.0  # 100000 - 15%

    async def test_update_deal_recalculates_final_amount(self, crm_db: DatabaseManager) -> None:
        acc_repo = AccountRepository(crm_db)
        opp_repo = OpportunityRepository(crm_db)
        deal_repo = DealRepository(crm_db)

        acc = await acc_repo.create({"name": "Discount Corp"})
        opp = await opp_repo.create({"account_id": acc.id, "name": "Support Contract"})
        deal = await deal_repo.create(
            {
                "opportunity_id": opp.id,
                "name": "Annual Support",
                "deal_value": 20000.0,
                "discount_percentage": 10.0,
            }
        )
        assert deal.final_amount == 18000.0

        updated = await deal_repo.update(deal.id, {"discount_percentage": 25.0})
        assert updated is not None
        assert updated.final_amount == 15000.0  # 20000 - 25%

