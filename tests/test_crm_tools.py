"""Tests for Deterministic Python CRM Tools and SalesDomainAgent Integration (Milestone 5.4).

Verifies:
- All deterministic tools operate cleanly against DatabaseManager
- SalesDomainAgent integration with services and database
"""

from __future__ import annotations

from pathlib import Path
import pytest

from src.agents.sales import SalesDomainAgent
from src.crm.tools.sales_tools import (
    close_deal_tool,
    convert_lead_tool,
    create_account_tool,
    create_contact_tool,
    create_deal_tool,
    create_lead_tool,
    create_opportunity_tool,
    get_account_summary_tool,
    qualify_lead_tool,
    search_leads_tool,
    update_lead_tool,
    update_opportunity_stage_tool,
)
from src.database.connection import DatabaseManager


@pytest.fixture()
async def crm_db(tmp_path: Path) -> DatabaseManager:
    """Provide an isolated, initialized database manager for CRM testing."""
    db_file = tmp_path / "crm_tools_test.db"
    url = f"sqlite+aiosqlite:///{db_file.as_posix()}"
    manager = DatabaseManager(url)
    await manager.init_db()
    yield manager
    await manager.dispose()


class TestCRMDeterministicTools:
    """Test all Python functions/tools."""

    async def test_lead_tools_lifecycle(self, crm_db: DatabaseManager) -> None:
        # 1. create_lead_tool
        res = await create_lead_tool(
            crm_db,
            first_name="Diana",
            last_name="Prince",
            company="Themyscira Exports",
            email="diana@amazon.com",
            score=40,
        )
        assert res["success"] is True
        lead_id = res["lead"]["id"]

        # 2. update_lead_tool
        upd = await update_lead_tool(crm_db, lead_id, score=85)
        assert upd["success"] is True
        assert upd["lead"]["score"] == 85

        # 3. search_leads_tool
        srch = await search_leads_tool(crm_db, "Themyscira")
        assert srch["success"] is True
        assert srch["count"] == 1

        # 4. qualify_lead_tool
        qual = await qualify_lead_tool(crm_db, lead_id, min_score=50)
        assert qual["success"] is True
        assert qual["lead"]["status"] == "qualified"

        # 5. convert_lead_tool
        conv = await convert_lead_tool(
            crm_db,
            lead_id,
            create_opportunity=True,
            opportunity_name="Amazon Relics Supply",
            opportunity_amount=150000.0,
        )
        assert conv["success"] is True
        assert conv["lead"]["status"] == "converted"
        assert conv["account"]["name"] == "Themyscira Exports"
        assert conv["contact"]["email"] == "diana@amazon.com"
        assert conv["opportunity"]["amount"] == 150000.0

    async def test_account_and_contact_tools(self, crm_db: DatabaseManager) -> None:
        # Create account tool
        acc_res = await create_account_tool(
            crm_db,
            name="Stark Industries",
            industry="Defense & Energy",
            tier="enterprise",
            annual_revenue=10000000.0,
        )
        assert acc_res["success"] is True
        account_id = acc_res["account"]["id"]

        # Create contact tool
        cnt_res = await create_contact_tool(
            crm_db,
            account_id=account_id,
            first_name="Tony",
            last_name="Stark",
            email="tony@stark.com",
            title="CEO",
            is_primary=True,
        )
        assert cnt_res["success"] is True
        assert cnt_res["contact"]["account_id"] == account_id

        # Account summary tool
        summary = await get_account_summary_tool(crm_db, account_id)
        assert summary["success"] is True
        assert summary["contact_count"] == 1

    async def test_opportunity_and_deal_tools(self, crm_db: DatabaseManager) -> None:
        acc_res = await create_account_tool(crm_db, name="Wayne Enterprises")
        acc_id = acc_res["account"]["id"]

        # create_opportunity_tool
        opp_res = await create_opportunity_tool(
            crm_db,
            account_id=acc_id,
            name="Batmobile Tech License",
            amount=500000.0,
            stage="prospecting",
        )
        assert opp_res["success"] is True
        opp_id = opp_res["opportunity"]["id"]
        assert opp_res["opportunity"]["probability"] == 10

        # update_opportunity_stage_tool
        stage_res = await update_opportunity_stage_tool(crm_db, opp_id, "proposal")
        assert stage_res["success"] is True
        assert stage_res["opportunity"]["probability"] == 50

        # create_deal_tool
        deal_res = await create_deal_tool(
            crm_db,
            opportunity_id=opp_id,
            name="Contract v1",
            deal_value=500000.0,
            discount_percentage=10.0,
        )
        assert deal_res["success"] is True
        deal_id = deal_res["deal"]["id"]
        assert deal_res["deal"]["final_amount"] == 450000.0

        # close_deal_tool (accepted)
        close_res = await close_deal_tool(crm_db, deal_id, accepted=True)
        assert close_res["success"] is True
        assert close_res["deal"]["status"] == "accepted"


class TestSalesDomainAgentArchitectureIntegration:
    """Verify SalesDomainAgent database and service bindings."""

    def test_sales_agent_with_db(self, crm_db: DatabaseManager) -> None:
        agent = SalesDomainAgent(db=crm_db)
        assert agent.db is crm_db
        assert agent.lead_service is not None
        assert agent.account_service is not None
        assert agent.contact_service is not None
        assert agent.opportunity_service is not None
        assert agent.deal_service is not None

    def test_sales_agent_without_db(self) -> None:
        agent = SalesDomainAgent()
        assert agent.db is None
        assert agent.lead_service is None
        assert agent.account_service is None

