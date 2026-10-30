"""Tests for CLI Intake Layer (Phase 4, Milestone 4.3)."""

import json
import pytest
from src.cli.intake import (
    format_task_output,
    main,
    run_cli,
    submit_task,
)
from src.cli.parser import (
    build_parser,
    parse_args,
)
from src.core.task import (
    TaskStatus,
    get_task,
)
from src.database.connection import DatabaseManager


# =====================================================================
# Argument Parser Tests
# =====================================================================


def test_parser_positional_description() -> None:
    args = parse_args(["Qualify lead Acme Corp"])
    assert args.description == "Qualify lead Acme Corp"
    assert args.task_type is None
    assert args.payload is None
    assert args.priority == 0
    assert args.domain is None
    assert args.as_json is False


def test_parser_custom_options() -> None:
    args = parse_args(
        [
            "Review contract",
            "-t",
            "deal_negotiation",
            "-p",
            '{"deal_value": 50000}',
            "--priority",
            "10",
            "--domain",
            "sales",
            "--json",
            "--db-url",
            "sqlite+aiosqlite:///:memory:",
        ]
    )
    assert args.description == "Review contract"
    assert args.task_type == "deal_negotiation"
    assert args.payload == '{"deal_value": 50000}'
    assert args.priority == 10
    assert args.domain == "sales"
    assert args.as_json is True
    assert args.db_url == "sqlite+aiosqlite:///:memory:"


def test_parser_missing_description_exits() -> None:
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args([])


# =====================================================================
# Output Formatting Tests
# =====================================================================


def test_format_task_output_text() -> None:
    summary = {
        "task_id": "test-uuid-123",
        "task_type": "Qualify lead Acme",
        "description": "Qualify lead Acme",
        "status": "completed",
        "classified_domain": "sales",
        "delegation_result": {
            "delegation_status": "DELEGATED",
            "handler": "sales_handler_node",
            "details": "Delegated to Sales Agent.",
            "sales_agent_result": {
                "sales_task_category": "lead_management",
                "handler_result": {
                    "handler": "lead_management_handler",
                    "details": "Lead processed successfully by Lead Management Handler.",
                },
            },
        },
    }
    output = format_task_output(summary, as_json=False)
    assert "AGENTIC CRM -- TASK EXECUTION RESULT" in output
    assert "Task ID:           test-uuid-123" in output
    assert "Status:            completed" in output
    assert "Classified Domain: sales" in output
    assert "DELEGATED (sales_handler_node)" in output
    assert "Sales Subdomain: lead_management (lead_management_handler)" in output


def test_format_task_output_json() -> None:
    summary = {
        "task_id": "test-uuid-456",
        "task_type": "Data sync",
        "status": "completed",
        "classified_domain": "data",
    }
    output = format_task_output(summary, as_json=True)
    parsed = json.loads(output)
    assert parsed["task_id"] == "test-uuid-456"
    assert parsed["classified_domain"] == "data"


# =====================================================================
# submit_task Integration Tests
# =====================================================================


@pytest.mark.asyncio
async def test_submit_task_sales_lead(tmp_path) -> None:
    db_file = tmp_path / "cli_test.db"
    db_url = f"sqlite+aiosqlite:///{db_file}"
    db = DatabaseManager(db_url)
    await db.init_db()

    try:
        summary = await submit_task(
            description="Qualify lead John Doe",
            payload={"contact": "john@example.com"},
            db=db,
        )

        task_id = summary["task_id"]
        assert task_id is not None
        assert summary["status"] == "completed"
        assert summary["classified_domain"] == "sales"

        delegation = summary["delegation_result"]
        assert delegation["domain"] == "sales"
        assert delegation["delegation_status"] == "DELEGATED"

        sales_res = delegation["sales_agent_result"]
        assert sales_res["sales_task_category"] == "lead_management"
        assert sales_res["handler_result"]["status"] == "COMPLETED"

        # Verify database record persistence
        persisted = await get_task(db, task_id)
        assert persisted is not None
        assert persisted["status"] == TaskStatus.COMPLETED.value
        assert persisted["payload"]["description"] == "Qualify lead John Doe"
        assert persisted["payload"]["contact"] == "john@example.com"
        assert persisted["result"] is not None
    finally:
        await db.dispose()


@pytest.mark.asyncio
async def test_submit_task_data_domain(tmp_path) -> None:
    db_file = tmp_path / "cli_data_test.db"
    db_url = f"sqlite+aiosqlite:///{db_file}"
    db = DatabaseManager(db_url)
    await db.init_db()

    try:
        summary = await submit_task(
            description="Export contact records to CSV",
            task_type="data_export_csv",
            db=db,
        )

        assert summary["status"] == "completed"
        assert summary["classified_domain"] == "data"
        assert summary["delegation_result"]["domain"] == "data"
        assert summary["delegation_result"]["handler"] == "data_handler_node"
    finally:
        await db.dispose()


@pytest.mark.asyncio
async def test_submit_task_unknown_domain_fallback(tmp_path) -> None:
    db_file = tmp_path / "cli_unknown_test.db"
    db_url = f"sqlite+aiosqlite:///{db_file}"
    db = DatabaseManager(db_url)
    await db.init_db()

    try:
        summary = await submit_task(
            description="Random unknown unclassifiable task 123",
            db=db,
        )

        assert summary["status"] == "completed"
        assert summary["classified_domain"] == "unknown"
        assert summary["delegation_result"]["domain"] == "unknown"
        assert summary["delegation_result"]["delegation_status"] == "UNRESOLVED"
    finally:
        await db.dispose()


# =====================================================================
# End-to-End CLI Execution (run_cli / main) Tests
# =====================================================================


@pytest.mark.asyncio
async def test_run_cli_success(tmp_path, capsys) -> None:
    db_file = tmp_path / "cli_run.db"
    db_url = f"sqlite+aiosqlite:///{db_file}"

    exit_code = await run_cli(
        ["Qualify lead Jane Doe", "--db-url", db_url]
    )
    assert exit_code == 0

    captured = capsys.readouterr()
    assert "AGENTIC CRM -- TASK EXECUTION RESULT" in captured.out
    assert "Classified Domain: sales" in captured.out
    assert "lead_management" in captured.out


@pytest.mark.asyncio
async def test_run_cli_json_output(tmp_path, capsys) -> None:
    db_file = tmp_path / "cli_json.db"
    db_url = f"sqlite+aiosqlite:///{db_file}"

    exit_code = await run_cli(
        ["Review proposal contract", "-t", "deal_negotiation", "--json", "--db-url", db_url]
    )
    assert exit_code == 0

    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["status"] == "completed"
    assert data["classified_domain"] == "sales"
    assert data["delegation_result"]["sales_agent_result"]["sales_task_category"] == "deal_management"


@pytest.mark.asyncio
async def test_run_cli_invalid_json_payload(capsys) -> None:
    exit_code = await run_cli(["Task", "-p", "not-a-valid-json"])
    assert exit_code == 1

    captured = capsys.readouterr()
    assert "Error: Invalid JSON payload" in captured.err


@pytest.mark.asyncio
async def test_run_cli_non_object_json_payload(capsys) -> None:
    exit_code = await run_cli(["Task", "-p", "[1, 2, 3]"])
    assert exit_code == 1

    captured = capsys.readouterr()
    assert "Error: Payload must be a JSON object" in captured.err


def test_main_sync_entrypoint(tmp_path, monkeypatch, capsys) -> None:
    db_file = tmp_path / "cli_main.db"
    db_url = f"sqlite+aiosqlite:///{db_file}"

    exit_code = main(["Qualify lead John Doe", "--db-url", db_url])
    assert exit_code == 0

    captured = capsys.readouterr()
    assert "AGENTIC CRM -- TASK EXECUTION RESULT" in captured.out
    assert "Classified Domain: sales" in captured.out
