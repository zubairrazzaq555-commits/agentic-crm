"""Focused tests for LLM-assisted Grandparent Orchestrator classification (Milestone 5.2).

Verifies the integration between the deterministic classifier, ProviderManager,
and LLM-assisted domain classification fallback.
"""

from __future__ import annotations

import pytest

from src.agents.orchestrator import (
    GrandparentOrchestrator,
    classify_domain_confidence,
    create_orchestrator_graph,
)
from src.agents.orchestrator.classifier import _parse_llm_domain
from src.providers.exceptions import ProviderError
from src.providers.manager import ProviderManager
from src.providers.mock_provider import MockProvider


def _build_test_pm(
    custom_response: str = "sales",
    simulate_failure: bool = False,
    provider_name: str = "mock_classifier",
) -> ProviderManager:
    """Helper to build a ProviderManager with a MockProvider."""
    pm = ProviderManager(allow_paid=False)
    provider = MockProvider(
        name=provider_name,
        model_name="mock-classifier-v1",
        custom_response=custom_response,
        simulate_failure=simulate_failure,
    )
    pm.register(provider)
    return pm


# =====================================================================
# 1. Parsing and Normalization Helper Tests
# =====================================================================


@pytest.mark.parametrize(
    ("raw_text", "expected_domain"),
    [
        ("sales", "sales"),
        ("  Sales  ", "sales"),
        ("MARKETING", "marketing"),
        ("customer_service", "customer_service"),
        ("customer service", "customer_service"),
        ("Customer Service.", "customer_service"),
        ("data", "data"),
        ("Data.", "data"),
        ("unknown", "unknown"),
        ("Unknown", "unknown"),
        # Preamble / chatty / reasoning outputs
        ("The domain is sales.", "sales"),
        ("Here is the classification:\nmarketing", "marketing"),
        ("Here is my thinking:\n... Output: customer_service", "customer_service"),
        # Invalid / unrecognized domains -> must return unknown
        ("finance", "unknown"),
        ("human_resources", "unknown"),
        ("arbitrary_domain", "unknown"),
        ("", "unknown"),
        ("   ", "unknown"),
        ("12345", "unknown"),
    ],
)
def test_parse_llm_domain(raw_text: str, expected_domain: str) -> None:
    assert _parse_llm_domain(raw_text) == expected_domain


# =====================================================================
# 2. Uncertainty Detection in Deterministic Classifier
# =====================================================================


def test_confident_deterministic_prefix() -> None:
    domain, is_confident = classify_domain_confidence("sales_lead_scoring")
    assert domain == "sales"
    assert is_confident is True


def test_confident_deterministic_payload_override() -> None:
    domain, is_confident = classify_domain_confidence("custom_job", {"target_domain": "marketing"})
    assert domain == "marketing"
    assert is_confident is True


def test_uncertain_deterministic_no_keywords() -> None:
    domain, is_confident = classify_domain_confidence("ambiguous_user_prompt", {"description": "hello world"})
    assert domain == "unknown"
    assert is_confident is False


def test_uncertain_deterministic_competing_signals() -> None:
    # 1 keyword for sales ("deal"), 1 keyword for marketing ("campaign") -> tie
    payload = {"description": "Close this deal and update the campaign"}
    domain, is_confident = classify_domain_confidence("ambiguous_task", payload)
    assert is_confident is False


# =====================================================================
# 3. Deterministic Precedence & Non-Invocation of LLM
# =====================================================================


@pytest.mark.asyncio
async def test_confident_deterministic_does_not_call_llm() -> None:
    """When deterministic classifier is confident, LLM is NEVER called.

    Even if the provider simulates failure, the orchestrator succeeds.
    """
    failing_pm = _build_test_pm(simulate_failure=True)
    orchestrator = GrandparentOrchestrator(provider_manager=failing_pm)

    result = await orchestrator.aexecute(
        task_id="orch-det-1",
        task_type="sales_qualification",
        input_payload={"lead_id": 101},
    )

    assert result["classified_domain"] == "sales"
    assert result["classification_method"] == "deterministic"
    assert result["execution_status"] == "SUCCESS"
    assert result["delegation_result"]["domain"] == "sales"
    assert result["delegation_result"]["handler"] == "sales_handler_node"


# =====================================================================
# 4. LLM Fallback on Ambiguous Tasks
# =====================================================================


@pytest.mark.asyncio
async def test_ambiguous_task_triggers_llm_and_routes_sales() -> None:
    """Ambiguous task with no keywords triggers LLM which classifies as sales."""
    pm = _build_test_pm(custom_response="sales")
    orchestrator = GrandparentOrchestrator(provider_manager=pm)

    result = await orchestrator.aexecute(
        task_id="orch-llm-1",
        task_type="unclassified_request",
        input_payload={"description": "Client wants to purchase additional enterprise licenses"},
    )

    assert result["classified_domain"] == "sales"
    assert result["classification_method"] == "llm"
    assert result["execution_status"] == "SUCCESS"
    assert result["delegation_result"]["domain"] == "sales"
    assert result["delegation_result"]["handler"] == "sales_handler_node"


@pytest.mark.parametrize(
    ("llm_response", "expected_domain", "expected_handler"),
    [
        ("sales", "sales", "sales_handler_node"),
        ("marketing", "marketing", "marketing_handler_node"),
        ("customer_service", "customer_service", "customer_service_handler_node"),
        ("data", "data", "data_handler_node"),
        ("unknown", "unknown", "unknown_handler_node"),
    ],
)
@pytest.mark.asyncio
async def test_llm_classifies_each_valid_domain(
    llm_response: str,
    expected_domain: str,
    expected_handler: str,
) -> None:
    pm = _build_test_pm(custom_response=llm_response)
    orchestrator = GrandparentOrchestrator(provider_manager=pm)

    result = await orchestrator.aexecute(
        task_id="orch-llm-domains",
        task_type="ambiguous_untyped_task",
        input_payload={"description": "Please evaluate and handle this request"},
    )

    assert result["classified_domain"] == expected_domain
    assert result["classification_method"] == "llm"
    assert result["execution_status"] == "SUCCESS"
    assert result["delegation_result"]["domain"] == expected_domain
    assert result["delegation_result"]["handler"] == expected_handler


# =====================================================================
# 5. Invalid / Empty / Malformed LLM Outputs
# =====================================================================


@pytest.mark.parametrize(
    "invalid_response",
    [
        "finance",
        "human_resources",
        "random_arbitrary_route",
        "",
        "   ",
        "<!DOCTYPE html>",
    ],
)
@pytest.mark.asyncio
async def test_invalid_llm_output_falls_back_to_unknown(invalid_response: str) -> None:
    pm = _build_test_pm(custom_response=invalid_response)
    orchestrator = GrandparentOrchestrator(provider_manager=pm)

    result = await orchestrator.aexecute(
        task_id="orch-llm-invalid",
        task_type="unclassifiable_request",
        input_payload={"description": "Perform arbitrary undefined action"},
    )

    assert result["classified_domain"] == "unknown"
    assert result["classification_method"] == "llm"
    assert result["execution_status"] == "SUCCESS"
    assert result["delegation_result"]["domain"] == "unknown"
    assert result["delegation_result"]["handler"] == "unknown_handler_node"


# =====================================================================
# 6. Provider Failures & Graceful Fallback
# =====================================================================


@pytest.mark.asyncio
async def test_provider_failure_falls_back_to_unknown() -> None:
    """When provider raises an error, orchestrator does NOT crash and falls back to unknown."""
    pm = _build_test_pm(simulate_failure=True)
    orchestrator = GrandparentOrchestrator(provider_manager=pm)

    result = await orchestrator.aexecute(
        task_id="orch-llm-fail",
        task_type="ambiguous_task_requiring_llm",
        input_payload={"description": "Some task that triggers LLM fallback"},
    )

    assert result["classified_domain"] == "unknown"
    assert result["classification_method"] == "fallback"
    assert result["execution_status"] == "SUCCESS"
    assert result["delegation_result"]["domain"] == "unknown"
    assert result["delegation_result"]["delegation_status"] == "UNRESOLVED"


@pytest.mark.asyncio
async def test_no_available_provider_falls_back_to_unknown() -> None:
    """Empty ProviderManager falls back safely to unknown."""
    empty_pm = ProviderManager(allow_paid=False)
    orchestrator = GrandparentOrchestrator(provider_manager=empty_pm)

    result = await orchestrator.aexecute(
        task_id="orch-llm-empty-pm",
        task_type="ambiguous_task_without_provider",
    )

    assert result["classified_domain"] == "unknown"
    assert result["classification_method"] == "fallback"
    assert result["execution_status"] == "SUCCESS"


# =====================================================================
# 7. Sync & Async Execution Parity with ProviderManager
# =====================================================================


def test_sync_execution_with_provider_manager() -> None:
    """Synchronous execute() works cleanly with an LLM-configured orchestrator."""
    pm = _build_test_pm(custom_response="marketing")
    orchestrator = GrandparentOrchestrator(provider_manager=pm)

    result = orchestrator.execute(
        task_id="orch-sync-1",
        task_type="pending_external_task",
        input_payload={"description": "Distribute executive quarterly summaries"},
    )

    assert result["classified_domain"] == "marketing"
    assert result["classification_method"] == "llm"
    assert result["execution_status"] == "SUCCESS"
    assert result["delegation_result"]["domain"] == "marketing"


# =====================================================================
# 8. Security & Secret Protection
# =====================================================================


def test_orchestrator_state_contains_no_secrets() -> None:
    """Verify that orchestrator state only contains domain and execution metadata."""
    pm = _build_test_pm(custom_response="sales")
    orchestrator = GrandparentOrchestrator(provider_manager=pm)

    result = orchestrator.execute(
        task_id="orch-sec-1",
        task_type="sales_qualification",
    )

    # Ensure no API keys, credentials, or provider secrets are in state
    state_keys = set(result.keys())
    for secret_word in ("api_key", "token", "secret", "password"):
        assert not any(secret_word in k.lower() for k in state_keys)
        if result.get("error_message"):
            assert secret_word not in result["error_message"].lower()

