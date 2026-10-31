"""Subdomain handlers for the Sales Domain Agent with real CRM execution.

Handles execution for the 5 Sales subdomains:
- Lead Management: intake, qualification, conversion, search
- Contact Management: creation, lookup, account association
- Account Management: creation, summary metrics, lookup
- Opportunity Management: pipeline creation, stage progression, forecasting
- Deal Management: creation, pricing calculation, closing & opportunity sync
- General Sales: fallback and reporting
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import re
from typing import Any, Dict, Optional

from src.agents.sales.intent import extract_sales_intent
from src.agents.sales.state import SalesAgentState
from src.config import get_settings
from src.crm.repositories import (
    AccountRepository,
    ContactRepository,
    DealRepository,
    LeadRepository,
    OpportunityRepository,
)
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
    update_opportunity_stage_tool,
)
from src.database.connection import DatabaseManager


def _run_async(coro: Any) -> Any:
    """Safely execute a coroutine from synchronous context."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, coro).result()
    else:
        return asyncio.run(coro)


async def _get_db(state: SalesAgentState) -> DatabaseManager:
    """Retrieve or initialize DatabaseManager from state payload."""
    payload = state.get("input_payload") or {}
    db = payload.get("_db")
    db_url = payload.get("db_url") or (db.database_url if isinstance(db, DatabaseManager) else None) or get_settings().database_url

    if isinstance(db, DatabaseManager):
        try:
            curr_loop = asyncio.get_running_loop()
            engine_loop = getattr(db.engine.sync_engine.pool, "_loop", None) if db.engine else None
            if engine_loop is None or engine_loop is curr_loop:
                if db.engine is None:
                    await db.init_db()
                return db
        except Exception:
            pass

    fresh_db = DatabaseManager(db_url)
    await fresh_db.init_db()
    return fresh_db


def _build_handler_result(
    category: str,
    handler_name: str,
    state: SalesAgentState,
    details: str,
    operation: str = "general_operation",
    success: bool = True,
    record_id: Optional[str] = None,
    data: Optional[Any] = None,
    error: Optional[str] = None,
) -> Dict[str, Any]:
    """Helper to build consistent, structured subdomain handler results."""
    return {
        "category": category,
        "handler": handler_name,
        "status": "COMPLETED" if success else "FAILED",
        "task_id": state.get("task_id", ""),
        "task_type": state.get("task_type", ""),
        "input_payload": state.get("input_payload", {}),
        "operation": operation,
        "success": success,
        "record_id": record_id,
        "data": data,
        "error": error,
        "details": details,
    }


# ===========================================================================
# 1. Lead Management Handler
# ===========================================================================


async def _async_lead_management(state: SalesAgentState) -> Dict[str, Any]:
    intent = extract_sales_intent(state.get("task_type", ""), state.get("input_payload"))
    op = intent.get("operation")
    params = intent.get("params", {})

    # Legacy default fallback
    if op == "legacy_default":
        return {
            "execution_status": "SUCCESS",
            "handler_result": _build_handler_result(
                category="lead_management",
                handler_name="lead_management_handler",
                state=state,
                details="Lead processed successfully by Lead Management Handler.",
                operation="legacy_default",
                success=True,
            ),
            "step": state.get("step", 0) + 1,
        }

    # Unsupported / ambiguous
    if op == "unsupported_or_ambiguous":
        err = intent.get("error", "Ambiguous or unsupported lead request.")
        return {
            "execution_status": "FAILED",
            "handler_result": _build_handler_result(
                category="lead_management",
                handler_name="lead_management_handler",
                state=state,
                details=err,
                operation="unsupported_or_ambiguous",
                success=False,
                error=err,
            ),
            "error_message": err,
            "step": state.get("step", 0) + 1,
        }

    db = await _get_db(state)

    try:
        if op == "create_lead":
            res = await create_lead_tool(
                db,
                first_name=params.get("first_name", ""),
                last_name=params.get("last_name", ""),
                company=params.get("company", ""),
                email=params.get("email", ""),
                phone=params.get("phone"),
                title=params.get("title"),
                source=params.get("source"),
                score=int(params.get("score") or 0),
                notes=params.get("notes"),
            )
            lead = res["lead"]
            details = f"Created lead {lead['first_name']} {lead['last_name']} at {lead['company']}."
            return {
                "execution_status": "SUCCESS",
                "handler_result": _build_handler_result(
                    category="lead_management",
                    handler_name="lead_management_handler",
                    state=state,
                    details=details,
                    operation="create_lead",
                    success=True,
                    record_id=lead["id"],
                    data=lead,
                ),
                "step": state.get("step", 0) + 1,
            }

        elif op == "search_leads":
            query = params.get("query", "")
            res = await search_leads_tool(db, query=query, status=params.get("status"))
            details = f"Found {res['count']} lead(s) matching '{query}'."
            return {
                "execution_status": "SUCCESS",
                "handler_result": _build_handler_result(
                    category="lead_management",
                    handler_name="lead_management_handler",
                    state=state,
                    details=details,
                    operation="search_leads",
                    success=True,
                    data=res["leads"],
                ),
                "step": state.get("step", 0) + 1,
            }

        elif op == "qualify_lead":
            lead_id = params.get("lead_id")
            lead_repo = LeadRepository(db)
            if not lead_id:
                query = params.get("email") or params.get("first_name") or params.get("name") or params.get("contact") or params.get("query")
                if query:
                    found = await lead_repo.search(str(query))
                    if found:
                        lead_id = found[0].id

            # If still not found and a person name or contact is given (e.g. CLI qualification "Qualify lead John Doe")
            if not lead_id:
                first_name = params.get("first_name")
                last_name = params.get("last_name")
                full_text = f"{state.get('task_type', '')} {params.get('description', '')}".strip()
                if not first_name or not last_name:
                    name_m = re.search(r"lead\s+([A-Za-z]+)\s+([A-Za-z]+)", full_text, re.IGNORECASE)
                    if name_m:
                        first_name = first_name or name_m.group(1).strip()
                        last_name = last_name or name_m.group(2).strip()

                if first_name and last_name:
                    email = params.get("contact") or params.get("email") or f"{first_name.lower()}.{last_name.lower()}@example.com"
                    new_lead = await lead_repo.create({
                        "first_name": first_name,
                        "last_name": last_name,
                        "email": email,
                        "company": params.get("company") or "Unknown",
                        "score": int(params.get("score") or 75),
                    })
                    lead_id = new_lead.id

            if not lead_id:
                return {
                    "execution_status": "FAILED",
                    "handler_result": _build_handler_result(
                        category="lead_management",
                        handler_name="lead_management_handler",
                        state=state,
                        details="Missing required parameter: lead_id (lead not found).",
                        operation="qualify_lead",
                        success=False,
                        error="Missing required parameter: lead_id",
                    ),
                    "error_message": "Missing required parameter: lead_id",
                    "step": state.get("step", 0) + 1,
                }

            if params.get("score") is not None:
                await lead_repo.update(lead_id, {"score": int(params["score"])})
            res = await qualify_lead_tool(
                db,
                lead_id,
                min_score=int(params.get("min_score") or 50),
                force=bool(params.get("force", False)),
                notes=params.get("notes"),
            )
            lead = res["lead"]
            details = f"Qualified lead {lead['first_name']} {lead['last_name']} (score: {lead['score']})."
            return {
                "execution_status": "SUCCESS",
                "handler_result": _build_handler_result(
                    category="lead_management",
                    handler_name="lead_management_handler",
                    state=state,
                    details=details,
                    operation="qualify_lead",
                    success=True,
                    record_id=lead["id"],
                    data=lead,
                ),
                "step": state.get("step", 0) + 1,
            }

        elif op == "convert_lead":
            lead_id = params.get("lead_id")
            lead_repo = LeadRepository(db)
            if not lead_id:
                query = params.get("email") or params.get("first_name") or params.get("name") or params.get("company")
                if query:
                    found = await lead_repo.search(str(query))
                    if found:
                        lead_id = found[0].id

            if not lead_id:
                return {
                    "execution_status": "FAILED",
                    "handler_result": _build_handler_result(
                        category="lead_management",
                        handler_name="lead_management_handler",
                        state=state,
                        details="Missing required parameter: lead_id (lead not found).",
                        operation="convert_lead",
                        success=False,
                        error="Missing required parameter: lead_id",
                    ),
                    "error_message": "Missing required parameter: lead_id",
                    "step": state.get("step", 0) + 1,
                }

            res = await convert_lead_tool(
                db,
                lead_id,
                create_opportunity=params.get("create_opportunity", True),
                opportunity_name=params.get("opportunity_name"),
                opportunity_amount=float(params.get("opportunity_amount") or 0.0),
            )
            details = f"Converted lead into Account '{res['account']['name']}' and Contact '{res['contact']['email']}'."
            return {
                "execution_status": "SUCCESS",
                "handler_result": _build_handler_result(
                    category="lead_management",
                    handler_name="lead_management_handler",
                    state=state,
                    details=details,
                    operation="convert_lead",
                    success=True,
                    record_id=res["lead"]["id"],
                    data=res,
                ),
                "step": state.get("step", 0) + 1,
            }

        else:
            raise ValueError(f"Unknown lead operation: '{op}'")

    except Exception as exc:
        err_msg = str(exc)
        return {
            "execution_status": "FAILED",
            "handler_result": _build_handler_result(
                category="lead_management",
                handler_name="lead_management_handler",
                state=state,
                details=f"Lead operation failed: {err_msg}",
                operation=op or "unknown",
                success=False,
                error=err_msg,
            ),
            "error_message": err_msg,
            "step": state.get("step", 0) + 1,
        }


def lead_management_handler(state: SalesAgentState) -> Dict[str, Any]:
    """Synchronous entry point for Lead Management Handler."""
    return _run_async(_async_lead_management(state))


# ===========================================================================
# 2. Contact Management Handler
# ===========================================================================


async def _async_contact_management(state: SalesAgentState) -> Dict[str, Any]:
    intent = extract_sales_intent(state.get("task_type", ""), state.get("input_payload"))
    op = intent.get("operation")
    params = intent.get("params", {})

    if op == "legacy_default":
        return {
            "execution_status": "SUCCESS",
            "handler_result": _build_handler_result(
                category="contact_management",
                handler_name="contact_management_handler",
                state=state,
                details="Contact processed successfully by Contact Management Handler.",
                operation="legacy_default",
                success=True,
            ),
            "step": state.get("step", 0) + 1,
        }

    if op == "unsupported_or_ambiguous":
        err = intent.get("error", "Ambiguous or unsupported contact request.")
        return {
            "execution_status": "FAILED",
            "handler_result": _build_handler_result(
                category="contact_management",
                handler_name="contact_management_handler",
                state=state,
                details=err,
                operation="unsupported_or_ambiguous",
                success=False,
                error=err,
            ),
            "error_message": err,
            "step": state.get("step", 0) + 1,
        }

    db = await _get_db(state)

    try:
        if op == "create_contact":
            account_id = params.get("account_id")
            company = params.get("company")
            if not account_id and company:
                acc_repo = AccountRepository(db)
                acc = await acc_repo.get_by_name(company)
                if not acc:
                    acc = await acc_repo.create({"name": company})
                account_id = acc.id

            res = await create_contact_tool(
                db,
                first_name=params.get("first_name", ""),
                last_name=params.get("last_name", ""),
                email=params.get("email", ""),
                account_id=account_id,
                phone=params.get("phone"),
                title=params.get("title"),
                department=params.get("department"),
                is_primary=bool(params.get("is_primary", False)),
            )
            contact = res["contact"]
            details = f"Created contact {contact['first_name']} {contact['last_name']} ({contact['email']})."
            return {
                "execution_status": "SUCCESS",
                "handler_result": _build_handler_result(
                    category="contact_management",
                    handler_name="contact_management_handler",
                    state=state,
                    details=details,
                    operation="create_contact",
                    success=True,
                    record_id=contact["id"],
                    data=contact,
                ),
                "step": state.get("step", 0) + 1,
            }

        elif op == "search_contacts":
            query = params.get("query", "")
            cnt_repo = ContactRepository(db)
            contacts = await cnt_repo.search(query=query)
            if not contacts and query:
                acc_repo = AccountRepository(db)
                matching_accs = await acc_repo.search(query=query)
                if matching_accs:
                    for acc in matching_accs:
                        acc_contacts = await cnt_repo.list_by_account(acc.id)
                        contacts.extend(acc_contacts)

            details = f"Found {len(contacts)} contact(s) matching '{query}'."
            return {
                "execution_status": "SUCCESS",
                "handler_result": _build_handler_result(
                    category="contact_management",
                    handler_name="contact_management_handler",
                    state=state,
                    details=details,
                    operation="search_contacts",
                    success=True,
                    data=[c.to_dict() for c in contacts],
                ),
                "step": state.get("step", 0) + 1,
            }

        else:
            raise ValueError(f"Unknown contact operation: '{op}'")

    except Exception as exc:
        err_msg = str(exc)
        return {
            "execution_status": "FAILED",
            "handler_result": _build_handler_result(
                category="contact_management",
                handler_name="contact_management_handler",
                state=state,
                details=f"Contact operation failed: {err_msg}",
                operation=op or "unknown",
                success=False,
                error=err_msg,
            ),
            "error_message": err_msg,
            "step": state.get("step", 0) + 1,
        }


def contact_management_handler(state: SalesAgentState) -> Dict[str, Any]:
    """Synchronous entry point for Contact Management Handler."""
    return _run_async(_async_contact_management(state))


# ===========================================================================
# 3. Account Management Handler
# ===========================================================================


async def _async_account_management(state: SalesAgentState) -> Dict[str, Any]:
    intent = extract_sales_intent(state.get("task_type", ""), state.get("input_payload"))
    op = intent.get("operation")
    params = intent.get("params", {})

    if op == "legacy_default":
        return {
            "execution_status": "SUCCESS",
            "handler_result": _build_handler_result(
                category="account_management",
                handler_name="account_management_handler",
                state=state,
                details="Account processed successfully by Account Management Handler.",
                operation="legacy_default",
                success=True,
            ),
            "step": state.get("step", 0) + 1,
        }

    if op == "unsupported_or_ambiguous":
        err = intent.get("error", "Ambiguous or unsupported account request.")
        return {
            "execution_status": "FAILED",
            "handler_result": _build_handler_result(
                category="account_management",
                handler_name="account_management_handler",
                state=state,
                details=err,
                operation="unsupported_or_ambiguous",
                success=False,
                error=err,
            ),
            "error_message": err,
            "step": state.get("step", 0) + 1,
        }

    db = await _get_db(state)

    try:
        if op == "create_account":
            res = await create_account_tool(
                db,
                name=params.get("name", ""),
                industry=params.get("industry"),
                website=params.get("website"),
                phone=params.get("phone"),
                tier=params.get("tier", "smb"),
                annual_revenue=float(params.get("annual_revenue") or 0.0),
                billing_city=params.get("billing_city"),
                billing_country=params.get("billing_country"),
            )
            acc = res["account"]
            details = f"Created account '{acc['name']}' (Tier: {acc['tier']})."
            return {
                "execution_status": "SUCCESS",
                "handler_result": _build_handler_result(
                    category="account_management",
                    handler_name="account_management_handler",
                    state=state,
                    details=details,
                    operation="create_account",
                    success=True,
                    record_id=acc["id"],
                    data=acc,
                ),
                "step": state.get("step", 0) + 1,
            }

        elif op == "search_accounts":
            query = params.get("query", "")
            acc_repo = AccountRepository(db)
            accounts = await acc_repo.search(query=query)
            details = f"Found {len(accounts)} account(s) matching '{query}'."
            return {
                "execution_status": "SUCCESS",
                "handler_result": _build_handler_result(
                    category="account_management",
                    handler_name="account_management_handler",
                    state=state,
                    details=details,
                    operation="search_accounts",
                    success=True,
                    data=[a.to_dict() for a in accounts],
                ),
                "step": state.get("step", 0) + 1,
            }

        elif op == "account_summary":
            acc_id = params.get("account_id")
            acc_name = params.get("name")
            acc_repo = AccountRepository(db)
            if not acc_id and acc_name:
                acc = await acc_repo.get_by_name(acc_name)
                if acc:
                    acc_id = acc.id
            if not acc_id:
                raise ValueError("Missing required account_id or account name.")
            res = await get_account_summary_tool(db, account_id=acc_id)
            details = f"Account '{res['account']['name']}' summary: {res['opportunity_count']} opps, pipeline: ${res['total_pipeline_value']}."
            return {
                "execution_status": "SUCCESS",
                "handler_result": _build_handler_result(
                    category="account_management",
                    handler_name="account_management_handler",
                    state=state,
                    details=details,
                    operation="account_summary",
                    success=True,
                    record_id=acc_id,
                    data=res,
                ),
                "step": state.get("step", 0) + 1,
            }

        else:
            raise ValueError(f"Unknown account operation: '{op}'")

    except Exception as exc:
        err_msg = str(exc)
        return {
            "execution_status": "FAILED",
            "handler_result": _build_handler_result(
                category="account_management",
                handler_name="account_management_handler",
                state=state,
                details=f"Account operation failed: {err_msg}",
                operation=op or "unknown",
                success=False,
                error=err_msg,
            ),
            "error_message": err_msg,
            "step": state.get("step", 0) + 1,
        }


def account_management_handler(state: SalesAgentState) -> Dict[str, Any]:
    """Synchronous entry point for Account Management Handler."""
    return _run_async(_async_account_management(state))


# ===========================================================================
# 4. Opportunity Management Handler
# ===========================================================================


async def _async_opportunity_management(state: SalesAgentState) -> Dict[str, Any]:
    intent = extract_sales_intent(state.get("task_type", ""), state.get("input_payload"))
    op = intent.get("operation")
    params = intent.get("params", {})

    if op == "legacy_default":
        return {
            "execution_status": "SUCCESS",
            "handler_result": _build_handler_result(
                category="opportunity_management",
                handler_name="opportunity_management_handler",
                state=state,
                details="Opportunity processed successfully by Opportunity Management Handler.",
                operation="legacy_default",
                success=True,
            ),
            "step": state.get("step", 0) + 1,
        }

    if op == "unsupported_or_ambiguous":
        err = intent.get("error", "Ambiguous or unsupported opportunity request.")
        return {
            "execution_status": "FAILED",
            "handler_result": _build_handler_result(
                category="opportunity_management",
                handler_name="opportunity_management_handler",
                state=state,
                details=err,
                operation="unsupported_or_ambiguous",
                success=False,
                error=err,
            ),
            "error_message": err,
            "step": state.get("step", 0) + 1,
        }

    db = await _get_db(state)

    try:
        if op == "create_opportunity":
            acc_id = params.get("account_id")
            acc_name = params.get("account_name")
            acc_repo = AccountRepository(db)
            if not acc_id and acc_name:
                acc = await acc_repo.get_by_name(acc_name)
                if not acc:
                    acc = await acc_repo.create({"name": acc_name})
                acc_id = acc.id

            if not acc_id:
                accs = await acc_repo.list(limit=1)
                if accs:
                    acc_id = accs[0].id
                else:
                    new_acc = await acc_repo.create({"name": "Standard Account"})
                    acc_id = new_acc.id

            raw_stage = str(params.get("stage", "prospecting")).strip().lower().replace(" ", "_")
            stg = "prospecting" if raw_stage in ("discovery", "init", "start", "new") else raw_stage
            res = await create_opportunity_tool(
                db,
                account_id=acc_id,
                name=params.get("name", "New Opportunity"),
                stage=stg,
                amount=float(params.get("amount") or 0.0),
                probability=int(params["probability"]) if params.get("probability") is not None else None,
            )
            opp = res["opportunity"]
            details = f"Created opportunity '{opp['name']}' worth ${opp['amount']} (Stage: {opp['stage']})."
            return {
                "execution_status": "SUCCESS",
                "handler_result": _build_handler_result(
                    category="opportunity_management",
                    handler_name="opportunity_management_handler",
                    state=state,
                    details=details,
                    operation="create_opportunity",
                    success=True,
                    record_id=opp["id"],
                    data=opp,
                ),
                "step": state.get("step", 0) + 1,
            }

        elif op == "search_opportunities":
            query = params.get("query", "")
            opp_repo = OpportunityRepository(db)
            opps = await opp_repo.search(query=query)
            if not opps and query:
                acc_repo = AccountRepository(db)
                accs = await acc_repo.search(query=query)
                if accs:
                    for a in accs:
                        acc_opps = await opp_repo.list_by_account(a.id)
                        opps.extend(acc_opps)

            details = f"Found {len(opps)} opportunity/opportunities matching '{query}'."
            return {
                "execution_status": "SUCCESS",
                "handler_result": _build_handler_result(
                    category="opportunity_management",
                    handler_name="opportunity_management_handler",
                    state=state,
                    details=details,
                    operation="search_opportunities",
                    success=True,
                    data=[o.to_dict() for o in opps],
                ),
                "step": state.get("step", 0) + 1,
            }

        elif op == "advance_stage":
            opp_id = params.get("opp_id") or params.get("opportunity_id")
            raw_stage = str(params.get("new_stage") or params.get("stage") or "").strip().lower().replace(" ", "_")
            new_stage = "prospecting" if raw_stage in ("discovery", "init", "start", "new") else raw_stage
            if not opp_id or not new_stage:
                raise ValueError("Missing opp_id or new_stage for stage advancement.")
            res = await update_opportunity_stage_tool(db, opp_id=opp_id, new_stage=new_stage)
            opp = res["opportunity"]
            details = f"Advanced opportunity '{opp['name']}' to stage '{opp['stage']}' (Prob: {opp['probability']}%)."
            return {
                "execution_status": "SUCCESS",
                "handler_result": _build_handler_result(
                    category="opportunity_management",
                    handler_name="opportunity_management_handler",
                    state=state,
                    details=details,
                    operation="advance_stage",
                    success=True,
                    record_id=opp["id"],
                    data=opp,
                ),
                "step": state.get("step", 0) + 1,
            }

        else:
            raise ValueError(f"Unknown opportunity operation: '{op}'")

    except Exception as exc:
        err_msg = str(exc)
        return {
            "execution_status": "FAILED",
            "handler_result": _build_handler_result(
                category="opportunity_management",
                handler_name="opportunity_management_handler",
                state=state,
                details=f"Opportunity operation failed: {err_msg}",
                operation=op or "unknown",
                success=False,
                error=err_msg,
            ),
            "error_message": err_msg,
            "step": state.get("step", 0) + 1,
        }


def opportunity_management_handler(state: SalesAgentState) -> Dict[str, Any]:
    """Synchronous entry point for Opportunity Management Handler."""
    return _run_async(_async_opportunity_management(state))


# ===========================================================================
# 5. Deal Management Handler
# ===========================================================================


async def _async_deal_management(state: SalesAgentState) -> Dict[str, Any]:
    intent = extract_sales_intent(state.get("task_type", ""), state.get("input_payload"))
    op = intent.get("operation")
    params = intent.get("params", {})

    if op == "legacy_default":
        return {
            "execution_status": "SUCCESS",
            "handler_result": _build_handler_result(
                category="deal_management",
                handler_name="deal_management_handler",
                state=state,
                details="Deal processed successfully by Deal Management Handler.",
                operation="legacy_default",
                success=True,
            ),
            "step": state.get("step", 0) + 1,
        }

    if op == "unsupported_or_ambiguous":
        err = intent.get("error", "Ambiguous or unsupported deal request.")
        return {
            "execution_status": "FAILED",
            "handler_result": _build_handler_result(
                category="deal_management",
                handler_name="deal_management_handler",
                state=state,
                details=err,
                operation="unsupported_or_ambiguous",
                success=False,
                error=err,
            ),
            "error_message": err,
            "step": state.get("step", 0) + 1,
        }

    db = await _get_db(state)

    try:
        if op == "create_deal":
            opp_id = params.get("opportunity_id")
            if not opp_id:
                opp_repo = OpportunityRepository(db)
                opps = await opp_repo.list(limit=1)
                if opps:
                    opp_id = opps[0].id
                else:
                    acc_repo = AccountRepository(db)
                    acc = await acc_repo.create({"name": "Standard Client"})
                    opp = await opp_repo.create({"account_id": acc.id, "name": "General Deal Opportunity"})
                    opp_id = opp.id

            deal_val = float(params.get("deal_value") or params.get("amount") or 0.0)
            res = await create_deal_tool(
                db,
                opportunity_id=opp_id,
                name=params.get("name", "New Deal"),
                deal_value=deal_val,
                discount_percentage=float(params.get("discount_percentage") or 0.0),
                payment_terms=params.get("payment_terms"),
            )
            deal = res["deal"]
            details = f"Created deal '{deal['name']}' worth ${deal['deal_value']} (Final: ${deal['final_amount']})."
            return {
                "execution_status": "SUCCESS",
                "handler_result": _build_handler_result(
                    category="deal_management",
                    handler_name="deal_management_handler",
                    state=state,
                    details=details,
                    operation="create_deal",
                    success=True,
                    record_id=deal["id"],
                    data=deal,
                ),
                "step": state.get("step", 0) + 1,
            }

        elif op == "close_deal":
            deal_id = params.get("deal_id")
            if not deal_id:
                raise ValueError("Missing required parameter: deal_id")
            accepted = bool(params.get("accepted", True))
            res = await close_deal_tool(db, deal_id=deal_id, accepted=accepted)
            deal = res["deal"]
            status_label = "accepted" if accepted else "rejected"
            details = f"Closed deal '{deal['name']}' as {status_label}."
            return {
                "execution_status": "SUCCESS",
                "handler_result": _build_handler_result(
                    category="deal_management",
                    handler_name="deal_management_handler",
                    state=state,
                    details=details,
                    operation="close_deal",
                    success=True,
                    record_id=deal["id"],
                    data=deal,
                ),
                "step": state.get("step", 0) + 1,
            }

        elif op == "search_deals":
            query = params.get("query", "")
            deal_repo = DealRepository(db)
            deals = await deal_repo.search(query=query)
            details = f"Found {len(deals)} deal(s) matching '{query}'."
            return {
                "execution_status": "SUCCESS",
                "handler_result": _build_handler_result(
                    category="deal_management",
                    handler_name="deal_management_handler",
                    state=state,
                    details=details,
                    operation="search_deals",
                    success=True,
                    data=[d.to_dict() for d in deals],
                ),
                "step": state.get("step", 0) + 1,
            }

        else:
            raise ValueError(f"Unknown deal operation: '{op}'")

    except Exception as exc:
        err_msg = str(exc)
        return {
            "execution_status": "FAILED",
            "handler_result": _build_handler_result(
                category="deal_management",
                handler_name="deal_management_handler",
                state=state,
                details=f"Deal operation failed: {err_msg}",
                operation=op or "unknown",
                success=False,
                error=err_msg,
            ),
            "error_message": err_msg,
            "step": state.get("step", 0) + 1,
        }


def deal_management_handler(state: SalesAgentState) -> Dict[str, Any]:
    """Synchronous entry point for Deal Management Handler."""
    return _run_async(_async_deal_management(state))


# ===========================================================================
# 6. General Sales Fallback Handler
# ===========================================================================


def general_sales_handler(state: SalesAgentState) -> Dict[str, Any]:
    """Fallback handler for broad sales operations or reporting."""
    step = state.get("step", 0)
    intent = extract_sales_intent(state.get("task_type", ""), state.get("input_payload"))
    op = intent.get("operation")

    if op == "unsupported_or_ambiguous":
        err = intent.get(
            "error",
            "Ambiguous or unsupported sales request. Supported: lead, contact, account, opportunity, deal.",
        )
        return {
            "execution_status": "FAILED",
            "handler_result": _build_handler_result(
                category="general_sales",
                handler_name="general_sales_handler",
                state=state,
                details=err,
                operation="unsupported_or_ambiguous",
                success=False,
                error=err,
            ),
            "error_message": err,
            "step": step + 1,
        }

    # Legacy / default
    result = _build_handler_result(
        category="general_sales",
        handler_name="general_sales_handler",
        state=state,
        details="Task processed by General Sales Handler.",
        operation="legacy_default",
        success=True,
    )
    return {
        "execution_status": "SUCCESS",
        "handler_result": result,
        "step": step + 1,
    }


# Async handler aliases for direct coroutine usage
lead_management_handler_async = _async_lead_management
contact_management_handler_async = _async_contact_management
account_management_handler_async = _async_account_management
opportunity_management_handler_async = _async_opportunity_management
deal_management_handler_async = _async_deal_management

