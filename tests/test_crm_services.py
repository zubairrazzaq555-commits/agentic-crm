"""Tests for CRM Business Logic Services (Milestone 5.4).

Verifies business rules, validation, and workflows for:
- LeadService (input validation, qualification thresholds, conversion workflow)
- AccountService (name uniqueness, tier validation, summary aggregation)
- ContactService (email validation, account verification)
- OpportunityService (stage progression, probability synchronization)
- DealService (discount math, closing sync with opportunity)
"""

from __future__ import annotations

from pathlib import Path
import pytest

from src.crm.models import DealStatus, LeadStatus, OpportunityStage
from src.crm.services import (
    AccountService,
    ContactService,
    DealService,
    LeadService,
    OpportunityService,
)
from src.database.connection import DatabaseManager


@pytest.fixture()
async def crm_db(tmp_path: Path) -> DatabaseManager:
    """Provide an isolated, initialized database manager for CRM testing."""
    db_file = tmp_path / "crm_services_test.db"
    url = f"sqlite+aiosqlite:///{db_file.as_posix()}"
    manager = DatabaseManager(url)
    await manager.init_db()
    yield manager
    await manager.dispose()


class TestLeadService:
    """Verify LeadService business logic and validation."""

    async def test_lead_validation_errors(self, crm_db: DatabaseManager) -> None:
        service = LeadService(crm_db)

        # Missing first name
        with pytest.raises(ValueError, match="First name is required"):
            await service.create_lead(
                first_name="",
                last_name="Smith",
                company="Acme",
                email="smith@acme.com",
            )

        # Invalid email
        with pytest.raises(ValueError, match="Invalid email address format"):
            await service.create_lead(
                first_name="John",
                last_name="Smith",
                company="Acme",
                email="not-an-email",
            )

        # Invalid score
        with pytest.raises(ValueError, match="score must be between 0 and 100"):
            await service.create_lead(
                first_name="John",
                last_name="Smith",
                company="Acme",
                email="smith@acme.com",
                score=150,
            )

    async def test_duplicate_lead_email_rejected(self, crm_db: DatabaseManager) -> None:
        service = LeadService(crm_db)
        await service.create_lead(
            first_name="Alice",
            last_name="Walker",
            company="Books Inc",
            email="alice@books.com",
        )
        with pytest.raises(ValueError, match="already exists"):
            await service.create_lead(
                first_name="Alice",
                last_name="Walker",
                company="Books Inc",
                email="ALICE@BOOKS.COM",  # Case insensitive duplicate check
            )

    async def test_qualify_lead_threshold(self, crm_db: DatabaseManager) -> None:
        service = LeadService(crm_db)
        lead = await service.create_lead(
            first_name="Low",
            last_name="Score",
            company="Cold Prospect",
            email="low@cold.com",
            score=30,
        )

        # Cannot qualify below threshold without force
        with pytest.raises(ValueError, match="does not meet the minimum qualification threshold"):
            await service.qualify_lead(lead.id, min_score=50, force=False)

        # Can qualify with force=True
        qualified = await service.qualify_lead(lead.id, min_score=50, force=True, qualification_notes="Executive override")
        assert qualified.status == LeadStatus.QUALIFIED.value
        assert "Executive override" in (qualified.notes or "")

    async def test_convert_lead_workflow(self, crm_db: DatabaseManager) -> None:
        """Test converting a qualified lead into Account, Contact, and Opportunity."""
        service = LeadService(crm_db)
        lead = await service.create_lead(
            first_name="Samantha",
            last_name="Fox",
            company="Fox Media Group",
            email="samantha@foxmedia.com",
            phone="555-0199",
            title="VP Marketing",
            score=85,
        )

        res = await service.convert_lead(
            lead.id,
            create_opportunity=True,
            opportunity_name="Fox Media Expansion",
            opportunity_amount=75000.0,
        )

        account = res["account"]
        contact = res["contact"]
        opp = res["opportunity"]
        converted_lead = res["lead"]

        assert account is not None
        assert account.name == "Fox Media Group"

        assert contact is not None
        assert contact.first_name == "Samantha"
        assert contact.email == "samantha@foxmedia.com"
        assert contact.account_id == account.id
        assert contact.is_primary is True

        assert opp is not None
        assert opp.name == "Fox Media Expansion"
        assert opp.account_id == account.id
        assert opp.amount == 75000.0

        assert converted_lead.status == LeadStatus.CONVERTED.value

        # Attempting to re-convert raises an error
        with pytest.raises(ValueError, match="already been converted"):
            await service.convert_lead(lead.id)


class TestAccountService:
    """Verify AccountService business logic."""

    async def test_account_creation_validation(self, crm_db: DatabaseManager) -> None:
        service = AccountService(crm_db)

        with pytest.raises(ValueError, match="Account name is required"):
            await service.create_account(name="  ")

        with pytest.raises(ValueError, match="Invalid account tier"):
            await service.create_account(name="Test Corp", tier="mega_enterprise")

        with pytest.raises(ValueError, match="Annual revenue cannot be negative"):
            await service.create_account(name="Negative Rev", annual_revenue=-100.0)

    async def test_account_summary_metrics(self, crm_db: DatabaseManager) -> None:
        acc_service = AccountService(crm_db)
        cnt_service = ContactService(crm_db)
        opp_service = OpportunityService(crm_db)

        account = await acc_service.create_account(name="Analytics Corp", annual_revenue=1000000.0)

        # Add 2 contacts
        await cnt_service.create_contact(account_id=account.id, first_name="A", last_name="B", email="ab@analytics.com")
        await cnt_service.create_contact(account_id=account.id, first_name="C", last_name="D", email="cd@analytics.com")

        # Add opportunities: 1 in proposal, 1 won
        await opp_service.create_opportunity(
            account_id=account.id,
            name="Pipeline Opp",
            amount=40000.0,
            stage=OpportunityStage.PROPOSAL.value,
        )
        await opp_service.create_opportunity(
            account_id=account.id,
            name="Won Opp",
            amount=60000.0,
            stage=OpportunityStage.CLOSED_WON.value,
        )

        summary = await acc_service.get_account_summary(account.id)
        assert summary["contact_count"] == 2
        assert summary["opportunity_count"] == 2
        assert summary["total_pipeline_value"] == 100000.0
        assert summary["won_opportunity_count"] == 1
        assert summary["won_revenue"] == 60000.0


class TestOpportunityService:
    """Verify OpportunityService business rules."""

    async def test_advance_stage_updates_probability(self, crm_db: DatabaseManager) -> None:
        acc_service = AccountService(crm_db)
        opp_service = OpportunityService(crm_db)

        account = await acc_service.create_account(name="Stage Corp")
        opp = await opp_service.create_opportunity(
            account_id=account.id,
            name="Software Deal",
            stage=OpportunityStage.PROSPECTING.value,
            amount=50000.0,
        )
        assert opp.probability == 10

        # Advance to Proposal -> probability should become 50
        advanced = await opp_service.advance_stage(opp.id, OpportunityStage.PROPOSAL.value)
        assert advanced.stage == OpportunityStage.PROPOSAL.value
        assert advanced.probability == 50

        # Advance to Closed Won -> probability should become 100
        won = await opp_service.advance_stage(opp.id, OpportunityStage.CLOSED_WON.value)
        assert won.stage == OpportunityStage.CLOSED_WON.value
        assert won.probability == 100


class TestDealService:
    """Verify DealService business rules and opportunity synchronization."""

    async def test_close_deal_accept_syncs_opportunity_closed_won(
        self, crm_db: DatabaseManager
    ) -> None:
        acc_service = AccountService(crm_db)
        opp_service = OpportunityService(crm_db)
        deal_service = DealService(crm_db)

        account = await acc_service.create_account(name="Sync Corp")
        opp = await opp_service.create_opportunity(
            account_id=account.id,
            name="Deal Sync Opportunity",
            stage=OpportunityStage.NEGOTIATION.value,
            amount=50000.0,
        )

        deal = await deal_service.create_deal(
            opportunity_id=opp.id,
            name="Final Pricing Agreement",
            deal_value=50000.0,
            discount_percentage=10.0,  # final_amount = 45000.0
        )
        assert deal.status == DealStatus.DRAFT.value
        assert deal.final_amount == 45000.0

        # Close deal as accepted
        closed_deal = await deal_service.close_deal(deal.id, accepted=True)
        assert closed_deal.status == DealStatus.ACCEPTED.value
        assert closed_deal.closed_at is not None

        # Verify associated opportunity is now CLOSED_WON with the negotiated final_amount
        synced_opp = await opp_service.get_opportunity(opp.id)
        assert synced_opp is not None
        assert synced_opp.stage == OpportunityStage.CLOSED_WON.value
        assert synced_opp.probability == 100
        assert synced_opp.amount == 45000.0

    async def test_close_deal_rejected(self, crm_db: DatabaseManager) -> None:
        acc_service = AccountService(crm_db)
        opp_service = OpportunityService(crm_db)
        deal_service = DealService(crm_db)

        account = await acc_service.create_account(name="Reject Corp")
        opp = await opp_service.create_opportunity(
            account_id=account.id,
            name="Reject Deal Opp",
            stage=OpportunityStage.NEGOTIATION.value,
        )

        deal = await deal_service.create_deal(
            opportunity_id=opp.id,
            name="Unaccepted Quote",
            deal_value=30000.0,
        )

        rejected = await deal_service.close_deal(deal.id, accepted=False)
        assert rejected.status == DealStatus.REJECTED.value
        assert rejected.closed_at is not None

        # Opportunity remains at current stage
        opp_after = await opp_service.get_opportunity(opp.id)
        assert opp_after.stage == OpportunityStage.NEGOTIATION.value

