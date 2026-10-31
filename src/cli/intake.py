"""Task intake and execution coordinator for the CLI interface."""

import asyncio
import json
import sys
from typing import Any, Dict, List, Optional

from src.agents.orchestrator import GrandparentOrchestrator
from src.cli.parser import build_parser
from src.config import get_settings
from src.core.task import (
    TaskStatus,
    enqueue_task,
    get_task,
    update_task_status,
)
from src.database.connection import DatabaseManager


def _sanitize_for_serialization(data: Any) -> Any:
    """Ensure data is JSON-serializable by converting datetimes and stripping un-serializable references."""
    if hasattr(data, "isoformat"):
        return data.isoformat()
    if isinstance(data, dict):
        return {
            k: _sanitize_for_serialization(v)
            for k, v in data.items()
            if not k.startswith("_") and not isinstance(v, DatabaseManager)
        }
    if isinstance(data, list):
        return [_sanitize_for_serialization(x) for x in data]
    return data


async def submit_task(
    description: str,
    task_type: Optional[str] = None,
    payload: Optional[Dict[str, Any]] = None,
    priority: int = 0,
    domain: Optional[str] = None,
    db: Optional[DatabaseManager] = None,
    orchestrator: Optional[GrandparentOrchestrator] = None,
) -> Dict[str, Any]:
    """Submit a task into the Agentic CRM pipeline and await its execution.

    Coordinates:
    1. Task payload packaging (integrating description).
    2. Queue persistence: registers task in SQLite with PENDING status.
    3. Lifecycle update: marks task as RUNNING.
    4. Hierarchical orchestration: dispatches to GrandparentOrchestrator.
    5. Final status update: marks task as COMPLETED or FAILED in DB.

    Args:
        description: Text description or prompt from the CLI user.
        task_type: Optional task type. If omitted, uses the description.
        payload: Optional dictionary carrying extra input parameters.
        priority: Task queue priority (default: 0).
        domain: Optional domain hint (e.g. 'sales').
        db: DatabaseManager instance. If omitted, uses default settings DB.
        orchestrator: GrandparentOrchestrator instance. If omitted, creates one.

    Returns:
        Structured dictionary summarizing task execution and routing results.
    """
    effective_task_type = (task_type or description).strip()
    task_payload = dict(payload) if payload else {}
    if "description" not in task_payload:
        task_payload["description"] = description

    # Ensure database manager
    owns_db = False
    if db is None:
        db_url = get_settings().database_url
        db = DatabaseManager(db_url)
        await db.init_db()
        owns_db = True

    orch = orchestrator or GrandparentOrchestrator()

    try:
        # 1. Enqueue task in persistent queue (PENDING)
        task_id = await enqueue_task(
            db,
            task_type=effective_task_type,
            payload=task_payload,
            priority=priority,
            domain=domain,
        )

        # 2. Transition lifecycle status to RUNNING
        await update_task_status(db, task_id, TaskStatus.RUNNING)

        # 3. Execute through Grandparent Orchestrator
        runtime_payload = dict(task_payload)
        runtime_payload["_db"] = db
        runtime_payload["db_url"] = db.database_url
        orch_state = await orch.aexecute(
            task_id=task_id,
            task_type=effective_task_type,
            input_payload=runtime_payload,
        )

        # 4. Determine outcome and finalize DB status
        execution_status = orch_state.get("execution_status", "FAILED")
        sanitized_state = _sanitize_for_serialization(orch_state)
        if execution_status == "SUCCESS":
            final_task_status = TaskStatus.COMPLETED
            await update_task_status(
                db,
                task_id,
                TaskStatus.COMPLETED,
                result=sanitized_state,
            )
        else:
            final_task_status = TaskStatus.FAILED
            err = (
                orch_state.get("error_message")
                or (
                    orch_state.get("delegation_result", {})
                    .get("sales_agent_result", {})
                    .get("handler_result", {})
                    .get("error")
                )
                or "Orchestrator execution failed"
            )
            await update_task_status(
                db,
                task_id,
                TaskStatus.FAILED,
                result={"error": err, "details": sanitized_state},
            )

        # 5. Build consolidated execution summary
        summary: Dict[str, Any] = {
            "task_id": task_id,
            "task_type": effective_task_type,
            "description": description,
            "status": final_task_status.value,
            "classified_domain": orch_state.get("classified_domain", "unknown"),
            "delegation_result": orch_state.get("delegation_result"),
            "orchestrator_state": orch_state,
        }
        return summary

    finally:
        if owns_db:
            await db.dispose()


def format_task_output(summary: Dict[str, Any], as_json: bool = False) -> str:
    """Format the task execution result summary for CLI presentation.

    Args:
        summary: Result dictionary returned by submit_task.
        as_json: If True, returns indented JSON; otherwise returns readable text.

    Returns:
        Formatted string for terminal display.
    """
    if as_json:
        return json.dumps(_sanitize_for_serialization(summary), indent=2, default=str)

    task_id = summary.get("task_id", "")
    task_type = summary.get("task_type", "")
    status = summary.get("status", "")
    domain = summary.get("classified_domain", "unknown")
    delegation = summary.get("delegation_result") or {}

    delegation_status = delegation.get("delegation_status", "N/A")
    handler = delegation.get("handler", "N/A")
    details = delegation.get("details", "")

    lines = [
        "=" * 60,
        "AGENTIC CRM -- TASK EXECUTION RESULT",
        "=" * 60,
        f"Task ID:           {task_id}",
        f"Task Type:         {task_type}",
        f"Status:            {status}",
        f"Classified Domain: {domain}",
        f"Delegation:        {delegation_status} ({handler})",
    ]

    # Include nested Sales Agent details if present
    sales_result = delegation.get("sales_agent_result")
    if sales_result:
        category = sales_result.get("sales_task_category", "general_sales")
        hr = sales_result.get("handler_result") or {}
        sub_handler = hr.get("handler", "N/A")
        sub_details = hr.get("details", "")
        operation = hr.get("operation")
        op_success = hr.get("success")
        record_id = hr.get("record_id")
        error_msg = hr.get("error")

        lines.append(f"  Sales Subdomain: {category} ({sub_handler})")
        if operation:
            lines.append(f"  Operation:       {operation}")
        if op_success is not None:
            op_outcome = "SUCCESS" if op_success else "FAILED"
            lines.append(f"  Operation Outcome: {op_outcome}")
        if record_id:
            lines.append(f"  Record ID:       {record_id}")
        if sub_details:
            lines.append(f"  Action Details:  {sub_details}")
        if error_msg:
            lines.append(f"  Error:           {error_msg}")
    elif details:
        lines.append(f"Details:           {details}")

    lines.append("=" * 60)
    return "\n".join(lines)


async def run_cli(argv: Optional[List[str]] = None) -> int:
    """Parse command-line arguments and run task intake asynchronously.

    Args:
        argv: Optional list of CLI argument strings.

    Returns:
        Process exit code (0 for success, non-zero for failure).
    """
    parser = build_parser()
    args = parser.parse_args(argv)

    extra_payload: Dict[str, Any] = {}
    if args.payload:
        try:
            parsed = json.loads(args.payload)
            if not isinstance(parsed, dict):
                print(
                    f"Error: Payload must be a JSON object, got {type(parsed).__name__}",
                    file=sys.stderr,
                )
                return 1
            extra_payload = parsed
        except json.JSONDecodeError as exc:
            print(f"Error: Invalid JSON payload: {exc}", file=sys.stderr)
            return 1

    db_url = args.db_url or get_settings().database_url
    db = DatabaseManager(db_url)
    await db.init_db()

    try:
        summary = await submit_task(
            description=args.description,
            task_type=args.task_type,
            payload=extra_payload,
            priority=args.priority,
            domain=args.domain,
            db=db,
        )

        output = format_task_output(summary, as_json=args.as_json)
        print(output)
        return 0 if summary.get("status") == TaskStatus.COMPLETED.value else 1
    except Exception as exc:
        print(f"Execution Error: {exc}", file=sys.stderr)
        return 1
    finally:
        await db.dispose()


def main(argv: Optional[List[str]] = None) -> int:
    """Synchronous entry point for the CLI intake layer."""
    return asyncio.run(run_cli(argv))
