"""Domain classification logic for Grandparent Orchestrator.

Provides deterministic keyword-based classification as the primary mechanism,
with optional LLM-assisted fallback when the deterministic classifier is
uncertain (e.g. no keywords matched or competing domain signals).
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, Optional, Set

from src.agents.orchestrator.state import SUPPORTED_DOMAINS, OrchestratorState

logger = logging.getLogger("agentic_crm.orchestrator.classifier")

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


def classify_domain_confidence(
    task_type: str,
    payload: Optional[Dict[str, Any]] = None,
) -> tuple[str, bool]:
    """Classify the incoming task and determine if the result is confident.

    Args:
        task_type: Task type or category string.
        payload: Optional task payload carrying parameters, description, etc.

    Returns:
        tuple (domain, is_confident):
        - domain: One of SUPPORTED_DOMAINS ("sales", "marketing", "customer_service", "data", "unknown").
        - is_confident: True if the deterministic classifier found clear, unambiguous signals;
          False if uncertain (no matches, ambiguous ties, or explicit unknown).
    """
    payload = payload or {}

    # 1. Direct explicit override in payload -> 100% confident
    explicit = payload.get("target_domain") or payload.get("domain")
    if isinstance(explicit, str):
        normalized = explicit.strip().lower()
        if normalized in DOMAIN_KEYWORDS:
            return normalized, True

    # 2. Direct task_type prefix/exact matches -> 100% confident
    clean_type = task_type.strip().lower()
    if clean_type.startswith("sales_") or clean_type == "sales":
        return "sales", True
    if clean_type.startswith("marketing_") or clean_type == "marketing":
        return "marketing", True
    if (
        clean_type.startswith("customer_service_")
        or clean_type.startswith("support_")
        or clean_type in ("support", "customer_service", "service")
    ):
        return "customer_service", True
    if clean_type.startswith("data_") or clean_type == "data":
        return "data", True

    # 3. Gather text tokens from task_type and common text payload fields
    tokens = _tokenize(task_type)
    for field in ("category", "action", "description", "content", "subject"):
        val = payload.get(field)
        if isinstance(val, str):
            tokens.update(_tokenize(val))

    # 4. Keyword score accumulation across domain keyword sets
    scores: Dict[str, int] = {domain: 0 for domain in DOMAIN_KEYWORDS}
    for domain, kws in DOMAIN_KEYWORDS.items():
        matched = tokens.intersection(kws)
        scores[domain] = len(matched)

    max_score = max(scores.values()) if scores else 0
    if max_score == 0:
        return "unknown", False

    # Check for ties among top scoring domains
    top_domains = [domain for domain, sc in scores.items() if sc == max_score]
    if len(top_domains) > 1:
        # Ambiguous tie: competing domain signals
        fallback_domain = top_domains[0]
        for domain in top_domains:
            for kw in DOMAIN_KEYWORDS[domain]:
                if kw in clean_type:
                    fallback_domain = domain
                    break
        return fallback_domain, False

    return top_domains[0], True


def classify_domain(task_type: str, payload: Optional[Dict[str, Any]] = None) -> str:
    """Classify the incoming task into one of the CRM business domains.

    Args:
        task_type: Task type or category string.
        payload: Optional task payload carrying parameters, description, etc.

    Returns:
        One of "sales", "marketing", "customer_service", "data", or "unknown".
    """
    domain, _ = classify_domain_confidence(task_type, payload)
    return domain


def classifier_node(state: OrchestratorState) -> Dict[str, Any]:
    """LangGraph node: Classifies task into domain deterministically."""
    task_type = state.get("task_type", "")
    payload = state.get("input_payload", {})
    step = state.get("step", 0)

    domain = classify_domain(task_type, payload)

    return {
        "classified_domain": domain,
        "classification_method": "deterministic",
        "step": step + 1,
    }


def route_domain(state: OrchestratorState) -> str:
    """Conditional router function returning the classified domain key."""
    return state.get("classified_domain", "unknown")


# ---------------------------------------------------------------------------
# LLM-assisted classification (optional fallback)
# ---------------------------------------------------------------------------

CLASSIFICATION_PROMPT = """\
You are a CRM domain classification assistant.
Classify the following task into exactly one of these domains:
- sales
- marketing
- customer_service
- data
- unknown

Task: {task_description}

Respond with only the domain name in lowercase and nothing else."""


def _parse_llm_domain(raw_text: str) -> str:
    """Parse and validate an LLM domain classification response.

    Extracts a valid domain from potentially verbose or reasoning output.
    Returns ``"unknown"`` if no valid domain is found.
    """
    if not raw_text or not isinstance(raw_text, str):
        return "unknown"

    text = raw_text.strip().lower()
    if not text:
        return "unknown"

    # 1. Exact match (with underscores or spaces)
    normalized = text.replace(" ", "_").strip(".: \n\t")
    if normalized in SUPPORTED_DOMAINS:
        return normalized

    # 2. Check lines from bottom to top (models often place the final answer at the end)
    lines = [ln.strip().lower() for ln in text.splitlines() if ln.strip()]
    for line in reversed(lines):
        clean_line = re.sub(r"[*_`'\"]", "", line).replace(" ", "_").strip(".: ")
        if clean_line in SUPPORTED_DOMAINS:
            return clean_line
        for domain in ("customer_service", "sales", "marketing", "data", "unknown"):
            if clean_line == domain or clean_line.endswith(f"_{domain}") or clean_line.endswith(f":_{domain}"):
                return domain

    # 3. Search for word boundary domain matches (multi-word first)
    for domain in ("customer_service", "sales", "marketing", "data"):
        pattern = r"\b" + re.escape(domain).replace("_", r"[\s_]") + r"\b"
        if re.search(pattern, text):
            return domain

    if re.search(r"\bunknown\b", text):
        return "unknown"

    return "unknown"


async def llm_classify_domain(provider_manager: Any, task_description: str) -> str:
    """Classify a task domain using an LLM via ProviderManager.

    Obtains the first available provider, sends a structured classification
    prompt, and validates the response against ``SUPPORTED_DOMAINS``.

    Args:
        provider_manager: A ``ProviderManager`` instance.
        task_description: Combined text describing the task.

    Returns:
        A validated domain string from ``SUPPORTED_DOMAINS``.

    Raises:
        ProviderError / ProviderUnavailableError: On provider failure
            (caller should catch and fall back).
    """
    provider = provider_manager.get_available_provider()
    prompt = CLASSIFICATION_PROMPT.format(task_description=task_description)
    try:
        result = await provider.generate(prompt=prompt, max_tokens=500, temperature=0.0)
        domain = _parse_llm_domain(result.text)
        if hasattr(provider_manager, "record_success"):
            provider_manager.record_success(provider.name)
        return domain
    except Exception:
        if hasattr(provider_manager, "record_failure"):
            provider_manager.record_failure(provider.name)
        raise


def create_classifier_node(provider_manager: Any) -> Any:
    """Factory: create an async classifier node with LLM fallback.

    The returned node function:
    1. Runs the deterministic ``classify_domain_confidence()`` first.
    2. If the deterministic result is confident, returns immediately
       (``classification_method="deterministic"``).
    3. If the deterministic result is uncertain, calls the LLM for
       assisted classification via ``provider_manager``.
    4. If the LLM returns a valid domain, uses it
       (``classification_method="llm"``).
    5. If the LLM call fails or returns invalid output, falls back to
       ``"unknown"`` (``classification_method="fallback"``).

    Args:
        provider_manager: A ``ProviderManager`` instance providing access
            to registered ``BaseProvider`` implementations.

    Returns:
        An async LangGraph node function.
    """

    async def _llm_classifier_node(state: OrchestratorState) -> Dict[str, Any]:
        task_type = state.get("task_type", "")
        payload = state.get("input_payload", {})
        step = state.get("step", 0)

        # Step 1: deterministic classification first
        domain, is_confident = classify_domain_confidence(task_type, payload)

        if is_confident:
            return {
                "classified_domain": domain,
                "classification_method": "deterministic",
                "step": step + 1,
            }

        # Step 2: LLM fallback for ambiguous / uncertain tasks
        try:
            parts = [task_type] if task_type else []
            if payload:
                for key in ("description", "content", "subject", "action", "category"):
                    val = payload.get(key)
                    if isinstance(val, str) and val.strip():
                        parts.append(val.strip())
            task_description = " | ".join(parts) or "unknown task"

            llm_domain = await llm_classify_domain(provider_manager, task_description)
            logger.info(
                "LLM classification result for task '%s': %s",
                task_type or task_description[:60],
                llm_domain,
            )
            return {
                "classified_domain": llm_domain,
                "classification_method": "llm",
                "step": step + 1,
            }
        except Exception as exc:
            logger.warning(
                "LLM classification failed for task '%s': %s — falling back to 'unknown'",
                task_type or "N/A",
                exc,
            )
            return {
                "classified_domain": "unknown",
                "classification_method": "fallback",
                "step": step + 1,
            }

    return _llm_classifier_node
