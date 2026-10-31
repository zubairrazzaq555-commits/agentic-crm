"""Task classification logic for Sales Domain Agent."""

import re
from typing import Any, Dict, Optional, Set

from src.agents.sales.state import SUPPORTED_SALES_CATEGORIES, SalesAgentState

SALES_CATEGORY_KEYWORDS: Dict[str, Set[str]] = {
    "lead_management": {
        "lead",
        "leads",
        "prospect",
        "prospects",
        "inbound",
        "outbound",
        "enrichment",
        "qualify",
        "qualification",
        "intake",
        "route",
        "routing",
        "assign",
        "assignment",
    },
    "contact_management": {
        "contact",
        "contacts",
        "individual",
        "person",
        "stakeholder",
    },
    "account_management": {
        "account",
        "accounts",
        "company_account",
        "organization",
        "firm",
    },
    "opportunity_management": {
        "opportunity",
        "opportunities",
        "opp",
        "opps",
        "pipeline",
        "forecast",
        "forecasting",
        "stage",
        "milestone",
        "probability",
        "upsell",
        "expansion",
    },
    "deal_management": {
        "deal",
        "deals",
        "quote",
        "quotes",
        "proposal",
        "proposals",
        "contract",
        "contracts",
        "pricing",
        "negotiation",
        "discount",
        "close",
        "closing",
        "terms",
    },
    "general_sales": {
        "sales",
        "sale",
        "revenue",
        "rep",
        "quota",
        "commission",
        "report",
        "metrics",
        "general",
    },
}


def _tokenize(text: str) -> Set[str]:
    """Tokenize a string into lowercased tokens, phrases, and individual words."""
    if not text:
        return set()
    lowered = text.lower().strip()
    tokens: Set[str] = {lowered}
    normalized = re.sub(r"[\s_\-.:/]+", " ", lowered)
    tokens.add(normalized)
    words = [w for w in normalized.split() if w]
    tokens.update(words)
    return tokens


def classify_sales_task(task_type: str, payload: Optional[Dict[str, Any]] = None) -> str:
    """Classify a sales-related task into a specific sales subdomain category.

    Args:
        task_type: Specific task type or category string.
        payload: Optional dictionary payload carrying parameters, description, etc.

    Returns:
        One of "lead_management", "opportunity_management", "deal_management",
        or "general_sales".
    """
    payload = payload or {}

    # 1. Direct explicit override in payload
    explicit = (
        payload.get("sales_category")
        or payload.get("subdomain")
        or payload.get("category")
    )
    if isinstance(explicit, str):
        normalized = explicit.strip().lower()
        if normalized in SUPPORTED_SALES_CATEGORIES:
            return normalized

    # 2. Direct task_type prefix/exact matches
    clean_type = task_type.strip().lower()
    if clean_type.startswith("lead_") or clean_type.startswith("leads_") or clean_type == "lead":
        return "lead_management"
    if (
        clean_type.startswith("opportunity_")
        or clean_type.startswith("opportunities_")
        or clean_type.startswith("opp_")
        or clean_type == "opportunity"
    ):
        return "opportunity_management"
    if (
        clean_type.startswith("deal_")
        or clean_type.startswith("deals_")
        or clean_type.startswith("quote_")
        or clean_type == "deal"
    ):
        return "deal_management"

    # 3. Gather tokens from task_type and text fields
    tokens = _tokenize(task_type)
    for field in ("action", "description", "content", "subject"):
        val = payload.get(field)
        if isinstance(val, str):
            tokens.update(_tokenize(val))

    # 4. Keyword score accumulation across categories
    scores: Dict[str, int] = {cat: 0 for cat in SUPPORTED_SALES_CATEGORIES}
    for cat, kws in SALES_CATEGORY_KEYWORDS.items():
        matched = tokens.intersection(kws)
        scores[cat] = len(matched)

    # 5. Check specialized categories first to prevent broad terms from overriding subdomains
    specialized_categories = [
        "lead_management",
        "contact_management",
        "account_management",
        "opportunity_management",
        "deal_management",
    ]
    best_cat = "general_sales"
    max_score = 0

    for cat in specialized_categories:
        score = scores[cat]
        if score > max_score:
            max_score = score
            best_cat = cat

    # If no specialized category scored, fall back to general_sales
    return best_cat


def sales_classifier_node(state: SalesAgentState) -> Dict[str, Any]:
    """LangGraph node: Classifies sales task and updates state."""
    task_type = state.get("task_type", "")
    payload = state.get("input_payload", {})
    step = state.get("step", 0)

    category = classify_sales_task(task_type, payload)

    return {
        "sales_task_category": category,
        "step": step + 1,
    }


def route_sales_category(state: SalesAgentState) -> str:
    """Conditional router function returning the classified sales category."""
    return state.get("sales_task_category", "general_sales")
