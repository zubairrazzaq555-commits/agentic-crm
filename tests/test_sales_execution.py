"""Tests for Sales Agent Execution & CRM Integration (Milestone 5.5).

Verifies that the Sales Domain Agent and Grandparent Orchestrator execute
real CRM operations through CRM services, repositories, and deterministic Python tools
against an initialized SQLite database.
"""

import pytest
import pytest_asyncio

from src.agents.orchestrator import GrandparentOrchestrator
from src.agents.sales.agent import SalesDomainAgent
from src.agents.sales.handlers import (
    account_management_handler,
    contact_management_handler,
    deal_management_handler,
    general_sales_handler,
    lead_management_handler,
    opportunity_management_handler,
)
from src.agents.sales.intent import extract_sales_intent
from src.agents.sales.state import create_initial_sales_state
from src.cli.intake import format_task_output, submit_task
from src.core.task import TaskStatus, get_task
from src.crm.models import DealStatus, LeadStatus, OpportunityStage
from src.crm.repositories import (
    AccountRepository,
    ContactRepository,
    DealRepository,
    LeadRepository,
    OpportunityRepository,
)
from src.database.connection import DatabaseManager


@pytest_asyncio.fixture
async def crm_db(tmp_path):
    """Provide an isolated, initialized SQLite database for tests."""
    db_file = tmp_path / "crm_exec_test.db"
    db_url = f"sqlite+aiosqlite:///{db_file}"
    db = DatabaseManager(db_url)
    await db.init_db()
    try:
        yield db
    finally:
        await db.dispose()


# =====================================================================
# 1. Intent Extraction Tests
# =====================================================================


def test_intent_extraction_create_lead():
    intent = extract_sales_intent(
        "Create lead for Alice Smith at Acme Corp email alice@acme.com phone 555-1234"
    )
    assert intent["operation"] == "create_lead"
    assert intent["category"] == "lead_management"
    assert intent["params"].get("first_name") == "Alice"
    assert intent["params"].get("last_name") == "Smith"
    assert intent["params"].get("company") == "Acme Corp"
    assert intent["params"].get("email") == "alice@acme.com"
    assert intent["params"].get("phone") == "555-1234"


def test_intent_extraction_create_account():
    intent = extract_sales_intent(
        "Create account named Initech in Technology with revenue 5000000"
    )
    assert intent["operation"] == "create_account"
    assert intent["category"] == "account_management"
    assert intent["params"].get("name") == "Initech"
    assert intent["params"].get("industry") == "Technology"
    assert intent["params"].get("annual_revenue") == 5000000.0


def test_intent_extraction_create_contact():
    intent = extract_sales_intent(
        "Create contact for Bob Jones email bob@initech.com title VP of Sales"
    )
    assert intent["operation"] == "create_contact"
    assert intent["category"] == "contact_management"
    assert intent["params"].get("first_name") == "Bob"
    assert intent["params"].get("last_name") == "Jones"
    assert intent["params"].get("email") == "bob@initech.com"
    assert intent["params"].get("title") == "VP of Sales"


def test_intent_extraction_create_deal():
    intent = extract_sales_intent(
        "Create deal Enterprise Tier for 100000 with discount 15"
    )
    assert intent["operation"] == "create_deal"
    assert intent["category"] == "deal_management"
    assert intent["params"].get("name") == "Enterprise Tier"
    assert intent["params"].get("deal_value") == 100000.0
    assert intent["params"].get("discount_percentage") == 15.0


def test_intent_extraction_ambiguous():
    intent = extract_sales_intent("Do something vague with no CRM entity")
    assert intent["category"] == "general_sales"
    assert intent["operation"] in ("unsupported_or_ambiguous", "legacy_default")


# =====================================================================
# 2. Individual Subdomain Handlers Tests
# =====================================================================


@pytest.mark.asyncio
async def test_lead_management_handler_create_and_qualify(crm_db):
    # 1. Create Lead via handler
    create_state = create_initial_sales_state(
        task_id="t-lead-1",
        task_type="create_lead",
        input_payload={
            "description": "Create a new lead for Carol Danvers at Marvel Inc email carol@marvel.com",
            "_db": crm_db,
        },
    )
    result = lead_management_handler(create_state)
    hr = result["handler_result"]
    assert hr["success"] is True
    assert hr["operation"] == "create_lead"
    lead_id = hr["record_id"]
    assert lead_id is not None
    assert hr["data"]["first_name"] == "Carol"
    assert hr["data"]["company"] == "Marvel Inc"

    # Verify directly in DB
    lead_repo = LeadRepository(crm_db)
    lead_in_db = await lead_repo.get_by_id(lead_id)
    assert lead_in_db is not None
    assert lead_in_db.status == LeadStatus.NEW.value

    # 2. Qualify Lead via handler
    qual_state = create_initial_sales_state(
        task_id="t-lead-2",
        task_type="qualify_lead",
        input_payload={
            "description": f"Qualify lead {lead_id} with score 85",
            "lead_id": lead_id,
            "score": 85,
            "_db": crm_db,
        },
    )
    qual_result = lead_management_handler(qual_state)
    q_hr = qual_result["handler_result"]
    assert q_hr["success"] is True
    assert q_hr["operation"] == "qualify_lead"
    assert q_hr["data"]["status"] == "qualified"
    assert q_hr["data"]["score"] == 85


@pytest.mark.asyncio
async def test_lead_management_handler_convert(crm_db):
    # Create lead first
    lead_repo = LeadRepository(crm_db)
    lead = await lead_repo.create(
        {
            "first_name": "Diana",
            "last_name": "Prince",
            "email": "diana@themyscira.org",
            "company": "Themyscira Enterprises",
        }
    )

    convert_state = create_initial_sales_state(
        task_id="t-convert-1",
        task_type="convert_lead",
        input_payload={
            "description": f"Convert lead {lead.id} to account and deal",
            "lead_id": lead.id,
            "deal_name": "Themyscira Expansion",
            "deal_value": 50000.0,
            "_db": crm_db,
        },
    )
    conv_result = lead_management_handler(convert_state)
    c_hr = conv_result["handler_result"]
    assert c_hr["success"] is True
    assert c_hr["operation"] == "convert_lead"
    data = c_hr["data"]
    assert data["account"]["id"] is not None
    assert data["contact"]["id"] is not None
    assert data["opportunity"]["id"] is not None

    # Check lead updated in DB to converted
    updated_lead = await lead_repo.get_by_id(lead.id)
    assert updated_lead.status == LeadStatus.CONVERTED.value


@pytest.mark.asyncio
async def test_contact_management_handler_flow(crm_db):
    state = create_initial_sales_state(
        task_id="t-contact-1",
        task_type="create_contact",
        input_payload={
            "description": "Create contact for Clark Kent email clark@dailyplanet.com title Reporter",
            "_db": crm_db,
        },
    )
    res = contact_management_handler(state)
    hr = res["handler_result"]
    assert hr["success"] is True
    assert hr["operation"] == "create_contact"
    contact_id = hr["record_id"]
    assert contact_id is not None
    assert hr["data"]["first_name"] == "Clark"
    assert hr["data"]["title"] == "Reporter"

    # Search contacts
    search_state = create_initial_sales_state(
        task_id="t-contact-2",
        task_type="search_contacts",
        input_payload={
            "description": "Search contacts matching Clark",
            "query": "Clark",
            "_db": crm_db,
        },
    )
    s_res = contact_management_handler(search_state)
    s_hr = s_res["handler_result"]
    assert s_hr["success"] is True
    assert len(s_hr["data"]) >= 1
    assert s_hr["data"][0]["email"] == "clark@dailyplanet.com"


@pytest.mark.asyncio
async def test_account_management_handler_flow(crm_db):
    create_state = create_initial_sales_state(
        task_id="t-account-1",
        task_type="create_account",
        input_payload={
            "description": "Create account named Wayne Enterprises industry Defense revenue 10000000",
            "_db": crm_db,
        },
    )
    res = account_management_handler(create_state)
    hr = res["handler_result"]
    assert hr["success"] is True
    assert hr["operation"] == "create_account"
    account_id = hr["record_id"]
    assert account_id is not None
    assert hr["data"]["name"] == "Wayne Enterprises"
    assert hr["data"]["annual_revenue"] == 10000000.0

    # Summary
    summary_state = create_initial_sales_state(
        task_id="t-account-2",
        task_type="account_summary",
        input_payload={
            "description": f"Get account summary for account {account_id}",
            "account_id": account_id,
            "_db": crm_db,
        },
    )
    s_res = account_management_handler(summary_state)
    s_hr = s_res["handler_result"]
    assert s_hr["success"] is True
    assert s_hr["operation"] == "account_summary"
    assert s_hr["data"]["account"]["name"] == "Wayne Enterprises"
    assert s_hr["data"]["opportunity_count"] == 0


@pytest.mark.asyncio
async def test_opportunity_management_handler_flow(crm_db):
    # Create an account first
    acc_repo = AccountRepository(crm_db)
    acc = await acc_repo.create({"name": "Stark Industries"})

    create_state = create_initial_sales_state(
        task_id="t-opp-1",
        task_type="create_opportunity",
        input_payload={
            "description": f"Create opportunity Arc Reactor Upgrade for account {acc.id} amount 250000 stage Discovery",
            "account_id": acc.id,
            "name": "Arc Reactor Upgrade",
            "amount": 250000.0,
            "stage": "Discovery",
            "_db": crm_db,
        },
    )
    res = opportunity_management_handler(create_state)
    hr = res["handler_result"]
    assert hr["success"] is True
    assert hr["operation"] == "create_opportunity"
    opp_id = hr["record_id"]
    assert opp_id is not None
    assert hr["data"]["name"] == "Arc Reactor Upgrade"
    assert hr["data"]["stage"] == "prospecting"

    # Advance stage
    adv_state = create_initial_sales_state(
        task_id="t-opp-2",
        task_type="advance_stage",
        input_payload={
            "description": f"Advance opportunity {opp_id} stage to Proposal",
            "opportunity_id": opp_id,
            "new_stage": "Proposal",
            "_db": crm_db,
        },
    )
    adv_res = opportunity_management_handler(adv_state)
    adv_hr = adv_res["handler_result"]
    assert adv_hr["success"] is True
    assert adv_hr["operation"] == "advance_stage"
    assert adv_hr["data"]["stage"] == "proposal"


@pytest.mark.asyncio
async def test_deal_management_handler_flow(crm_db):
    # Create account and opportunity
    acc_repo = AccountRepository(crm_db)
    acc = await acc_repo.create({"name": "Cyberdyne Systems"})
    opp_repo = OpportunityRepository(crm_db)
    opp = await opp_repo.create(
        {
            "account_id": acc.id,
            "name": "Neural Net Defense System",
            "amount": 500000.0,
        }
    )

    create_state = create_initial_sales_state(
        task_id="t-deal-1",
        task_type="create_deal",
        input_payload={
            "description": f"Create deal Skynet Defense for 500000 with discount 10",
            "opportunity_id": opp.id,
            "name": "Skynet Defense",
            "amount": 500000.0,
            "discount_percentage": 10.0,
            "_db": crm_db,
        },
    )
    res = deal_management_handler(create_state)
    hr = res["handler_result"]
    assert hr["success"] is True
    assert hr["operation"] == "create_deal"
    deal_id = hr["record_id"]
    assert deal_id is not None
    assert hr["data"]["final_amount"] == 450000.0

    # Close deal
    close_state = create_initial_sales_state(
        task_id="t-deal-2",
        task_type="close_deal",
        input_payload={
            "description": f"Close deal {deal_id} as Won",
            "deal_id": deal_id,
            "accepted": True,
            "_db": crm_db,
        },
    )
    c_res = deal_management_handler(close_state)
    c_hr = c_res["handler_result"]
    assert c_hr["success"] is True
    assert c_hr["operation"] == "close_deal"
    assert c_hr["data"]["status"] == DealStatus.ACCEPTED.value

    # Verify opportunity stage also advanced to closed_won
    updated_opp = await opp_repo.get_by_id(opp.id)
    assert updated_opp.stage == OpportunityStage.CLOSED_WON.value


# =====================================================================
# 3. Error Handling and Edge Cases
# =====================================================================


@pytest.mark.asyncio
async def test_handler_error_missing_required_fields(crm_db):
    # Attempt to create lead without name or email
    state = create_initial_sales_state(
        task_id="t-err-1",
        task_type="create_lead",
        input_payload={
            "description": "Create lead",
            "first_name": "",
            "last_name": "",
            "_db": crm_db,
        },
    )
    res = lead_management_handler(state)
    hr = res["handler_result"]
    assert hr["success"] is False
    assert hr["status"] == "FAILED"
    assert res["execution_status"] == "FAILED"
    assert hr["error"] is not None


@pytest.mark.asyncio
async def test_handler_error_nonexistent_record_id(crm_db):
    state = create_initial_sales_state(
        task_id="t-err-2",
        task_type="qualify_lead",
        input_payload={
            "description": "Qualify lead non-existent-id-9999",
            "lead_id": "non-existent-id-9999",
            "_db": crm_db,
        },
    )
    res = lead_management_handler(state)
    hr = res["handler_result"]
    assert hr["success"] is False
    assert hr["status"] == "FAILED"
    assert res["execution_status"] == "FAILED"
    assert "not found" in hr["error"].lower()


@pytest.mark.asyncio
async def test_general_sales_unsupported_task(crm_db):
    state = create_initial_sales_state(
        task_id="t-unsupp-1",
        task_type="general_sales",
        input_payload={
            "description": "Totally unsupported sales intent with bizarre keywords",
            "_db": crm_db,
        },
    )
    res = general_sales_handler(state)
    hr = res["handler_result"]
    assert hr["success"] is False
    assert hr["status"] == "FAILED"
    assert res["execution_status"] == "FAILED"
    assert "unsupported" in hr["details"].lower() or "unsupported" in (hr.get("error") or "").lower()


# =====================================================================
# 4. End-to-End Orchestrator & CLI Intake Execution
# =====================================================================


@pytest.mark.asyncio
async def test_end_to_end_sales_execution_via_submit_task(crm_db):
    """Verify full hierarchical execution from CLI intake to DB persistence."""
    description = "Create a new lead for Tony Stark at Stark Enterprises with email tony@stark.com"
    summary = await submit_task(
        description=description,
        db=crm_db,
    )

    assert summary["status"] == "completed"
    assert summary["classified_domain"] == "sales"
    delegation = summary["delegation_result"]
    assert delegation["domain"] == "sales"

    sales_res = delegation["sales_agent_result"]
    assert sales_res["sales_task_category"] == "lead_management"

    hr = sales_res["handler_result"]
    assert hr["success"] is True
    assert hr["operation"] == "create_lead"
    record_id = hr["record_id"]
    assert record_id is not None
    assert hr["data"]["first_name"] == "Tony"

    # Verify task queue entry in SQLite
    task_id = summary["task_id"]
    db_task = await get_task(crm_db, task_id)
    assert db_task is not None
    assert db_task["status"] == TaskStatus.COMPLETED.value
    assert db_task["result"] is not None

    # Verify formatting output
    output_text = format_task_output(summary)
    assert f"Task ID:           {task_id}" in output_text
    assert "Classified Domain: sales" in output_text
    assert "Sales Subdomain: lead_management" in output_text
    assert "Operation:       create_lead" in output_text
    assert "Operation Outcome: SUCCESS" in output_text
    assert f"Record ID:       {record_id}" in output_text


@pytest.mark.asyncio
async def test_end_to_end_account_creation_via_submit_task(crm_db):
    summary = await submit_task(
        description="Create account named Wonka Industries in Confectionery with revenue 8000000",
        db=crm_db,
    )

    assert summary["status"] == "completed"
    assert summary["classified_domain"] == "sales"
    sales_res = summary["delegation_result"]["sales_agent_result"]
    assert sales_res["sales_task_category"] == "account_management"
    hr = sales_res["handler_result"]
    assert hr["success"] is True
    assert hr["operation"] == "create_account"
    assert hr["data"]["name"] == "Wonka Industries"