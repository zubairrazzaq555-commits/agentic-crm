"""Domain classification logic for Grandparent Orchestrator."""

import re
from typing import Any, Dict, Optional, Set

from src.agents.orchestrator.state import OrchestratorState

# Keyword sets per domain (both root words and singular/plural forms)
DOMAIN_KEYWORDS: Dict[str, Set[str]] = {
    "sales": {
        "lead",
        "leads",
        "deal",
        "deals",
        "opportunity",
        "opportunities",
        "quote",
        "quotes",
        "sales",
        "sale",
        "qualify",
        "qualification",
        "pipeline",
        "proposal",
        "proposals",
        "contract",
        "contracts",
        "pricing",
        "negotiation",
    },
    "marketing": {
        "campaign",
        "campaigns",
        "newsletter",
        "newsletters",
        "email",
        "blast",
        "social",
        "ad",
        "ads",
        "marketing",
        "promotion",
        "promotions",
        "promo",
        "audience",
        "content",
        "seo",
        "branding",
    },
    "customer_service": {
        "ticket",
        "tickets",
        "complaint",
        "complaints",
        "support",
        "refund",
        "refunds",
        "service",
        "inquiry",
        "inquiries",
        "helpdesk",
        "issue",
        "issues",
        "escalation",
    },
    "data": {
        "export",
        "exports",
        "import",
        "imports",
        "cleanup",
        "clean",
        "sync",
        "synchronization",
        "dedup",
        "deduplication",
        "migration",
        "data",
        "etl",
        "backup",
        "analytics",
        "warehouse",
        "csv",
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


def classify_domain(task_type: str, payload: Optional[Dict[str, Any]] = None) -> str:
    """Classify the incoming task into one of the CRM business domains.

    Args:
        task_type: Task type or category string.
        payload: Optional task payload carrying parameters, description, etc.

    Returns:
        One of "sales", "marketing", "customer_service", "data", or "unknown".
    """
    payload = payload or {}

    # 1. Direct explicit override in payload
    explicit = payload.get("target_domain") or payload.get("domain")
    if isinstance(explicit, str):
        normalized = explicit.strip().lower()
        if normalized in DOMAIN_KEYWORDS:
            return normalized

    # 2. Gather text tokens from task_type and common text payload fields
    tokens = _tokenize(task_type)
    for field in ("category", "action", "description", "content", "subject"):
        val = payload.get(field)
        if isinstance(val, str):
            tokens.update(_tokenize(val))

    # 3. Direct task_type prefix/exact matches
    clean_type = task_type.strip().lower()
    if clean_type.startswith("sales_") or clean_type == "sales":
        return "sales"
    if clean_type.startswith("marketing_") or clean_type == "marketing":
        return "marketing"
    if (
        clean_type.startswith("customer_service_")
        or clean_type.startswith("support_")
        or clean_type in ("support", "customer_service", "service")
    ):
        return "customer_service"
    if clean_type.startswith("data_") or clean_type == "data":
        return "data"

    # 4. Keyword score accumulation across domain keyword sets
    scores: Dict[str, int] = {domain: 0 for domain in DOMAIN_KEYWORDS}
    for domain, kws in DOMAIN_KEYWORDS.items():
        matched = tokens.intersection(kws)
        scores[domain] = len(matched)

    # Find highest scoring domain
    best_domain = "unknown"
    max_score = 0
    for domain, score in scores.items():
        if score > max_score:
            max_score = score
            best_domain = domain
        elif score == max_score and max_score > 0:
            # Ambiguous tie: if scores match, check if task_type has explicit keyword
            for kw in DOMAIN_KEYWORDS[domain]:
                if kw in clean_type:
                    best_domain = domain
                    break

    return best_domain if max_score > 0 else "unknown"


def classifier_node(state: OrchestratorState) -> Dict[str, Any]:
    """LangGraph node: Classifies task into domain and records in state."""
    task_type = state.get("task_type", "")
    payload = state.get("input_payload", {})
    step = state.get("step", 0)

    domain = classify_domain(task_type, payload)

    return {
        "classified_domain": domain,
        "step": step + 1,
    }


def route_domain(state: OrchestratorState) -> str:
    """Conditional router function returning the classified domain key."""
    return state.get("classified_domain", "unknown")
