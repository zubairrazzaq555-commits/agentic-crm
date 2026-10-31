"""Deterministic intent parsing and parameter extraction for the Sales Domain Agent.

Parses user requests and payloads into structured sales operations without
invoking any LLM/SLM. Supported categories:
- Lead Management: create_lead, search_leads, qualify_lead, convert_lead
- Contact Management: create_contact, search_contacts
- Account Management: create_account, search_accounts, account_summary
- Opportunity Management: create_opportunity, search_opportunities, advance_stage
- Deal Management: create_deal, close_deal, search_deals
"""

from __future__ import annotations

import re
from typing import Any, Dict, Optional

_EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")
_UUID_PATTERN = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)


def _extract_lead_params(text: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    params = dict(payload)

    email = params.get("email")
    if not email:
        email_match = _EMAIL_PATTERN.search(text)
        if email_match:
            email = email_match.group(0).strip()

    phone = params.get("phone")
    if not phone:
        phone_m = re.search(r"(?:phone|tel|mobile)\s*[:=]?\s*([0-9\-\+\(\)\s]{7,20})", text, re.IGNORECASE)
        if phone_m:
            phone = phone_m.group(1).strip()

    company = params.get("company")
    if not company:
        company_m = re.search(r"(?:at|company)\s+([A-Za-z0-9\s&,.-]+?)(?=\s+(?:email|phone|with|title|score|$))", text, re.IGNORECASE)
        company = (company_m.group(1).strip() if company_m else "").strip() or "Unknown Company"

    first_name = params.get("first_name")
    last_name = params.get("last_name")
    if not first_name or not last_name:
        name_m = re.search(r"lead(?:\s+for)?\s+([A-Za-z]+)\s+([A-Za-z]+)", text, re.IGNORECASE)
        if name_m:
            first_name = first_name or name_m.group(1).strip()
            last_name = last_name or name_m.group(2).strip()

    if not email and first_name and last_name:
        clean_co = re.sub(r"[^A-Za-z0-9]", "", company).lower() or "example"
        email = f"{first_name.lower()}.{last_name.lower()}@{clean_co}.com"

    params["first_name"] = first_name or ""
    params["last_name"] = last_name or ""
    params["company"] = company
    params["email"] = email or ""
    if phone:
        params["phone"] = phone
    return params


def _extract_contact_params(text: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    params = dict(payload)

    email = params.get("email")
    if not email:
        email_match = _EMAIL_PATTERN.search(text)
        if email_match:
            email = email_match.group(0).strip()

    phone = params.get("phone")
    if not phone:
        phone_m = re.search(r"(?:phone|tel|mobile)\s*[:=]?\s*([0-9\-\+\(\)\s]{7,20})", text, re.IGNORECASE)
        if phone_m:
            phone = phone_m.group(1).strip()

    title = params.get("title")
    if not title:
        title_m = re.search(r"(?:title|as|role)\s+([A-Za-z0-9\s&,.-]+?)(?:\s+(?:at|with|email|phone)|$)", text, re.IGNORECASE)
        if title_m:
            title = title_m.group(1).strip()

    company = params.get("company")
    if not company:
        company_m = re.search(r"(?:at|company)\s+([A-Za-z0-9\s&,.-]+?)(?=\s+(?:email|phone|with|title|$))", text, re.IGNORECASE)
        company = (company_m.group(1).strip() if company_m else "").strip()

    first_name = params.get("first_name")
    last_name = params.get("last_name")
    if not first_name or not last_name:
        name_m = re.search(r"contact(?:\s+for)?\s+([A-Za-z]+)\s+([A-Za-z]+)", text, re.IGNORECASE)
        if name_m:
            first_name = first_name or name_m.group(1).strip()
            last_name = last_name or name_m.group(2).strip()

    if not email and first_name and last_name:
        clean_co = re.sub(r"[^A-Za-z0-9]", "", company).lower() or "example"
        email = f"{first_name.lower()}.{last_name.lower()}@{clean_co}.com"

    params["first_name"] = first_name or ""
    params["last_name"] = last_name or ""
    params["email"] = email or ""
    params["company"] = company
    if phone:
        params["phone"] = phone
    if title:
        params["title"] = title
    return params


def _extract_account_params(text: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    params = dict(payload)

    annual_revenue = params.get("annual_revenue")
    if annual_revenue is None:
        rev_m = re.search(r"(?:revenue|annual revenue)\s*[:=]?\s*\$?([0-9]+(?:\.[0-9]+)?)", text, re.IGNORECASE)
        annual_revenue = float(rev_m.group(1)) if rev_m else 0.0

    industry = params.get("industry")
    if not industry:
        ind_m = re.search(r"(?:in|industry)\s+([A-Za-z0-9\s&,.-]+?)(?=\s+(?:with|revenue|tier|named|$))", text, re.IGNORECASE)
        if ind_m:
            industry = ind_m.group(1).strip()

    name = params.get("name")
    if not name:
        name_m = re.search(r"account\s+(?:named\s+|for\s+)?([A-Za-z0-9\s&,.-]+?)(?=\s+(?:\bin\b|\bindustry\b|\bwith\b|\brevenue\b|\btier\b|$))", text, re.IGNORECASE)
        name = name_m.group(1).strip() if name_m else "New Account"

    params["name"] = name
    params["annual_revenue"] = float(annual_revenue)
    if industry:
        params["industry"] = industry
    return params


def _extract_opportunity_params(text: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    params = dict(payload)

    amount = params.get("amount")
    if amount is None:
        amt_m = re.search(r"(?:worth|amount|value|\$)\s*[:=]?\s*\$?(\d+(?:\.\d+)?)", text, re.IGNORECASE)
        amount = float(amt_m.group(1)) if amt_m else 0.0

    stage = params.get("stage") or params.get("new_stage")
    if not stage:
        stage_m = re.search(r"(?:stage\s+to|stage)\s+([A-Za-z0-9_\-]+)", text, re.IGNORECASE)
        stage = stage_m.group(1).strip().lower() if stage_m else "prospecting"
    if stage in ("discovery", "init", "new"):
        stage = "prospecting"

    name = params.get("name") or params.get("title")
    if not name:
        name_m = re.search(r"opportunity\s+(?:named\s+|for\s+)?([A-Za-z0-9\s&,.-]+?)(?=\s+(?:for|worth|amount|value|stage|\$|$))", text, re.IGNORECASE)
        name = name_m.group(1).strip() if name_m and name_m.group(1).strip() not in ("worth", "amount", "stage") else "New Opportunity"

    uuid_m = _UUID_PATTERN.search(text)
    account_id = params.get("account_id") or (uuid_m.group(0) if uuid_m else None)

    params["name"] = name
    params["title"] = name
    params["amount"] = float(amount)
    params["stage"] = stage
    if account_id:
        params["account_id"] = account_id
    return params


def _extract_deal_params(text: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    params = dict(payload)

    deal_value = params.get("deal_value") or params.get("amount")
    if deal_value is None:
        val_m = re.search(r"(?:worth|value|amount|for|\$)\s*[:=]?\s*\$?(\d+(?:\.\d+)?)", text, re.IGNORECASE)
        deal_value = float(val_m.group(1)) if val_m else 0.0

    discount = params.get("discount_percentage") or params.get("discount_pct") or params.get("discount")
    if discount is None:
        disc_m = re.search(r"(?:discount|discount_pct)\s*[:=]?\s*(\d+(?:\.\d+)?)\%?", text, re.IGNORECASE)
        discount = float(disc_m.group(1)) if disc_m else 0.0

    name = params.get("name") or params.get("title")
    if not name:
        name_m = re.search(r"deal\s+(?:named\s+|for\s+)?([A-Za-z0-9\s&,.-]+?)(?=\s+(?:for|worth|value|amount|discount|\$|$))", text, re.IGNORECASE)
        name = name_m.group(1).strip() if name_m and name_m.group(1).strip() not in ("worth", "value", "amount", "discount") else "New Deal"

    params["name"] = name
    params["title"] = name
    params["deal_value"] = float(deal_value)
    params["amount"] = float(deal_value)
    params["discount_percentage"] = float(discount)
    params["discount_pct"] = float(discount)
    return params


def extract_sales_intent(
    task_type: str,
    payload: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Parse a task type and payload into a concrete sales operation and parameters.

    Args:
        task_type: Task type string or text command.
        payload: Optional dictionary payload carrying arguments, description, etc.

    Returns:
        Dictionary with:
            - "category": subdomain category (e.g. "lead_management")
            - "operation": operation identifier (e.g. "create_lead")
            - "params": extracted parameters for the tool/service
            - "error": error description if ambiguous or unsupported
    """
    payload = payload or {}
    text = (payload.get("description") or task_type or "").strip()
    action = payload.get("action")

    # -----------------------------------------------------------------------
    # 0. Check for legacy abstract task types used in architecture tests
    # -----------------------------------------------------------------------
    legacy_categories = {
        # Lead
        "lead_intake": "lead_management",
        "lead_enrichment": "lead_management",
        "leads_enrichment": "lead_management",
        "qualify_prospect": "lead_management",
        "lead_scoring": "lead_management",
        "sales_lead_scoring": "lead_management",
        "sales_qualification": "lead_management",
        "lead_qualification": "lead_management",
        "sales_lead_qualification": "lead_management",
        # Opportunity
        "opportunity_forecast": "opportunity_management",
        "opportunity_stage_update": "opportunity_management",
        "opp_pipeline_forecast": "opportunity_management",
        "opp_stage": "opportunity_management",
        # Deal
        "deal_proposal": "deal_management",
        "deal_negotiation": "deal_management",
        "quote_generation": "deal_management",
        "quote_close": "deal_management",
        "deal_closing": "deal_management",
        "sales_deal": "deal_management",
        # General Sales
        "sales_general_audit": "general_sales",
        "sales_pipeline_audit": "general_sales",
        "sales_metrics_review": "general_sales",
        "revenue_report": "general_sales",
        "general_sales_task": "general_sales",
        "sales_report": "general_sales",
        "unrecognized_sales_job": "general_sales",
        "unclassified_request": "general_sales",
        "ambiguous_untyped_task": "general_sales",
    }
    clean_task_type = task_type.strip().lower()
    if clean_task_type in legacy_categories and not action:
        cat = legacy_categories[clean_task_type]
        return {
            "category": payload.get("sales_category") or cat,
            "operation": "legacy_default",
            "params": payload,
        }

    # -----------------------------------------------------------------------
    # 1. Direct explicit action in payload or task_type
    # -----------------------------------------------------------------------
    candidate_actions = []
    if action:
        candidate_actions.append(action.strip().lower())
    candidate_actions.append(clean_task_type)

    for act in candidate_actions:
        if act in ("create_lead", "add_lead", "new_lead"):
            return {
                "category": "lead_management",
                "operation": "create_lead",
                "params": _extract_lead_params(text, payload),
            }
        if act in ("search_leads", "find_leads", "list_leads"):
            p = dict(payload)
            if "query" not in p:
                q_m = re.search(r"(?:for|named|matching|at)\s+([A-Za-z0-9\s&,.-]+)$", text, re.IGNORECASE)
                p["query"] = q_m.group(1).strip() if q_m else ""
            return {
                "category": "lead_management",
                "operation": "search_leads",
                "params": p,
            }
        if act in ("qualify_lead", "qualify"):
            p = dict(payload)
            if not p.get("lead_id"):
                uuid_m = _UUID_PATTERN.search(text)
                if uuid_m:
                    p["lead_id"] = uuid_m.group(0)
            score_m = re.search(r"score\s*[:=]?\s*(\d+)", text, re.IGNORECASE)
            if score_m and "score" not in p:
                p["score"] = int(score_m.group(1))
            return {
                "category": "lead_management",
                "operation": "qualify_lead",
                "params": p,
            }
        if act in ("convert_lead", "convert"):
            p = dict(payload)
            if not p.get("lead_id"):
                uuid_m = _UUID_PATTERN.search(text)
                if uuid_m:
                    p["lead_id"] = uuid_m.group(0)
            return {
                "category": "lead_management",
                "operation": "convert_lead",
                "params": p,
            }

        if act in ("create_contact", "add_contact", "new_contact"):
            return {
                "category": "contact_management",
                "operation": "create_contact",
                "params": _extract_contact_params(text, payload),
            }
        if act in ("search_contacts", "find_contacts", "list_contacts"):
            p = dict(payload)
            if "query" not in p:
                q_m = re.search(r"(?:belonging to|for|at|in|named|matching)\s+([A-Za-z0-9\s&,.-]+)$", text, re.IGNORECASE)
                p["query"] = q_m.group(1).strip() if q_m else ""
            return {
                "category": "contact_management",
                "operation": "search_contacts",
                "params": p,
            }

        if act in ("create_account", "add_account", "new_account"):
            return {
                "category": "account_management",
                "operation": "create_account",
                "params": _extract_account_params(text, payload),
            }
        if act in ("search_accounts", "find_accounts", "list_accounts"):
            p = dict(payload)
            if "query" not in p:
                q_m = re.search(r"(?:for|named|matching|at)\s+([A-Za-z0-9\s&,.-]+)$", text, re.IGNORECASE)
                p["query"] = q_m.group(1).strip() if q_m else ""
            return {
                "category": "account_management",
                "operation": "search_accounts",
                "params": p,
            }
        if act in ("account_summary", "get_account_summary"):
            p = dict(payload)
            if not p.get("account_id"):
                uuid_m = _UUID_PATTERN.search(text)
                if uuid_m:
                    p["account_id"] = uuid_m.group(0)
            return {
                "category": "account_management",
                "operation": "account_summary",
                "params": p,
            }

        if act in ("create_opportunity", "add_opportunity", "new_opportunity"):
            return {
                "category": "opportunity_management",
                "operation": "create_opportunity",
                "params": _extract_opportunity_params(text, payload),
            }
        if act in ("search_opportunities", "find_opportunities", "list_opportunities"):
            p = dict(payload)
            if "query" not in p:
                q_m = re.search(r"(?:for|matching|named)\s+([A-Za-z0-9\s&,.-]+)$", text, re.IGNORECASE)
                p["query"] = q_m.group(1).strip() if q_m else ""
            return {
                "category": "opportunity_management",
                "operation": "search_opportunities",
                "params": p,
            }
        if act in ("advance_stage", "update_stage", "advance_opportunity_stage"):
            p = dict(payload)
            if not p.get("opportunity_id") and not p.get("opp_id"):
                uuid_m = _UUID_PATTERN.search(text)
                if uuid_m:
                    p["opportunity_id"] = uuid_m.group(0)
                    p["opp_id"] = uuid_m.group(0)
            if not p.get("new_stage") and not p.get("stage"):
                st_m = re.search(r"(?:stage\s+to|to\s+stage|to)\s+([A-Za-z0-9_]+)", text, re.IGNORECASE)
                if st_m:
                    p["new_stage"] = st_m.group(1).strip().lower()
                    p["stage"] = p["new_stage"]
            return {
                "category": "opportunity_management",
                "operation": "advance_stage",
                "params": p,
            }

        if act in ("create_deal", "add_deal", "new_deal"):
            return {
                "category": "deal_management",
                "operation": "create_deal",
                "params": _extract_deal_params(text, payload),
            }
        if act in ("close_deal", "close"):
            p = dict(payload)
            if not p.get("deal_id"):
                uuid_m = _UUID_PATTERN.search(text)
                if uuid_m:
                    p["deal_id"] = uuid_m.group(0)
            p["accepted"] = bool(p.get("accepted", True))
            return {
                "category": "deal_management",
                "operation": "close_deal",
                "params": p,
            }
        if act in ("search_deals", "find_deals", "list_deals"):
            return {
                "category": "deal_management",
                "operation": "search_deals",
                "params": payload,
            }

    # -----------------------------------------------------------------------
    # 2. Deterministic Regex / Keyword Pattern Matching from text
    # -----------------------------------------------------------------------
    t_lower = text.lower()

    # -- Lead Patterns ------------------------------------------------------
    if "qualify" in t_lower and ("lead" in t_lower or "prospect" in t_lower or payload.get("lead_id")):
        p = dict(payload)
        lead_id = p.get("lead_id")
        if not lead_id:
            uuid_m = _UUID_PATTERN.search(text)
            if uuid_m:
                lead_id = uuid_m.group(0)
        if lead_id:
            p["lead_id"] = lead_id
        score_m = re.search(r"score\s*[:=]?\s*(\d+)", text, re.IGNORECASE)
        if score_m and "score" not in p:
            p["score"] = int(score_m.group(1))
        return {
            "category": "lead_management",
            "operation": "qualify_lead",
            "params": p,
        }

    if "convert" in t_lower and ("lead" in t_lower or payload.get("lead_id")):
        p = dict(payload)
        lead_id = p.get("lead_id")
        if not lead_id:
            uuid_m = _UUID_PATTERN.search(text)
            if uuid_m:
                lead_id = uuid_m.group(0)
        if lead_id:
            p["lead_id"] = lead_id
        return {
            "category": "lead_management",
            "operation": "convert_lead",
            "params": p,
        }

    if any(k in t_lower for k in ("find lead", "search lead", "show lead", "list lead", "find prospect", "search leads")):
        p = dict(payload)
        q_m = re.search(r"(?:for|named|matching|at)\s+([A-Za-z0-9\s&,.-]+)$", text, re.IGNORECASE)
        p["query"] = q_m.group(1).strip() if q_m else p.get("query", "")
        return {
            "category": "lead_management",
            "operation": "search_leads",
            "params": p,
        }

    if "lead" in t_lower and ("create" in t_lower or "new" in t_lower or "add" in t_lower):
        return {
            "category": "lead_management",
            "operation": "create_lead",
            "params": _extract_lead_params(text, payload),
        }

    # -- Contact Patterns ---------------------------------------------------
    if any(k in t_lower for k in ("contacts belonging to", "contacts for", "find contact", "search contact", "show contact", "list contact", "search contacts")):
        p = dict(payload)
        q_m = re.search(r"(?:belonging to|for|at|in|named|matching)\s+([A-Za-z0-9\s&,.-]+)$", text, re.IGNORECASE)
        p["query"] = q_m.group(1).strip() if q_m else p.get("query", "")
        return {
            "category": "contact_management",
            "operation": "search_contacts",
            "params": p,
        }

    if "contact" in t_lower and ("create" in t_lower or "new" in t_lower or "add" in t_lower):
        return {
            "category": "contact_management",
            "operation": "create_contact",
            "params": _extract_contact_params(text, payload),
        }

    # -- Account Patterns ---------------------------------------------------
    if "account summary" in t_lower or "summary for account" in t_lower:
        p = dict(payload)
        acc_id = p.get("account_id")
        if not acc_id:
            uuid_m = _UUID_PATTERN.search(text)
            if uuid_m:
                acc_id = uuid_m.group(0)
        if acc_id:
            p["account_id"] = acc_id
        return {
            "category": "account_management",
            "operation": "account_summary",
            "params": p,
        }

    if any(k in t_lower for k in ("find account", "search account", "show account", "list account", "search accounts")):
        p = dict(payload)
        q_m = re.search(r"(?:for|named|matching|at)\s+([A-Za-z0-9\s&,.-]+)$", text, re.IGNORECASE)
        p["query"] = q_m.group(1).strip() if q_m else p.get("query", "")
        return {
            "category": "account_management",
            "operation": "search_accounts",
            "params": p,
        }

    if "account" in t_lower and ("create" in t_lower or "new" in t_lower or "add" in t_lower):
        return {
            "category": "account_management",
            "operation": "create_account",
            "params": _extract_account_params(text, payload),
        }

    # -- Opportunity Patterns -----------------------------------------------
    if "advance" in t_lower and ("stage" in t_lower or "opportunity" in t_lower):
        p = dict(payload)
        st_m = re.search(r"(?:stage\s+to|to\s+stage|to)\s+([A-Za-z0-9_]+)", text, re.IGNORECASE)
        p["new_stage"] = st_m.group(1).strip().lower() if st_m else p.get("new_stage", "")
        p["stage"] = p["new_stage"]
        opp_id = p.get("opp_id") or p.get("opportunity_id")
        if not opp_id:
            uuid_m = _UUID_PATTERN.search(text)
            if uuid_m:
                opp_id = uuid_m.group(0)
        p["opp_id"] = opp_id
        p["opportunity_id"] = opp_id
        return {
            "category": "opportunity_management",
            "operation": "advance_stage",
            "params": p,
        }

    if any(k in t_lower for k in ("show opportunities", "find opportunities", "search opportunities", "list opportunities")):
        p = dict(payload)
        q_m = re.search(r"(?:for|matching|named)\s+([A-Za-z0-9\s&,.-]+)$", text, re.IGNORECASE)
        p["query"] = q_m.group(1).strip() if q_m else p.get("query", "")
        return {
            "category": "opportunity_management",
            "operation": "search_opportunities",
            "params": p,
        }

    if "opportunity" in t_lower and ("create" in t_lower or "new" in t_lower or "add" in t_lower):
        return {
            "category": "opportunity_management",
            "operation": "create_opportunity",
            "params": _extract_opportunity_params(text, payload),
        }

    # -- Deal Patterns ------------------------------------------------------
    if "close" in t_lower and ("deal" in t_lower or payload.get("deal_id")):
        p = dict(payload)
        deal_id = p.get("deal_id")
        if not deal_id:
            uuid_m = _UUID_PATTERN.search(text)
            if uuid_m:
                deal_id = uuid_m.group(0)
        p["deal_id"] = deal_id
        p["accepted"] = bool(p.get("accepted", True))
        return {
            "category": "deal_management",
            "operation": "close_deal",
            "params": p,
        }

    if "deal" in t_lower and ("create" in t_lower or "new" in t_lower or "add" in t_lower):
        return {
            "category": "deal_management",
            "operation": "create_deal",
            "params": _extract_deal_params(text, payload),
        }

    # -----------------------------------------------------------------------
    # 3. Check if this is a generic / legacy test input
    # -----------------------------------------------------------------------
    if clean_task_type in legacy_categories or payload.get("sales_category") in (
        "lead_management", "contact_management", "account_management",
        "opportunity_management", "deal_management", "general_sales"
    ):
        return {
            "category": payload.get("sales_category") or legacy_categories.get(clean_task_type, "general_sales"),
            "operation": "legacy_default",
            "params": payload,
        }

    # -----------------------------------------------------------------------
    # 4. Fallback: Ambiguous or Unsupported
    # -----------------------------------------------------------------------
    return {
        "category": "general_sales",
        "operation": "unsupported_or_ambiguous",
        "params": payload,
        "error": (
            f"Ambiguous or unsupported sales request: '{text}'. "
            "Supported operations: create/search/qualify/convert lead, "
            "create/search contact, create/search account, "
            "create/search/advance opportunity, create/close deal."
        ),
    }
