"""
Agentic CRM — Task model, status lifecycle, and persistent task queue.

Provides the SQLAlchemy Core table definition for tasks, a status enum
defining the task lifecycle, and async queue operations (enqueue, dequeue,
status transitions).

All operations require an initialized DatabaseManager instance.

Concurrency note:
    This module implements a single-process task queue.  It does NOT
    provide distributed locking or multi-worker dequeue guarantees.
    The queue API is designed so that locking can be added in a future
    milestone without changing the Task schema or public interface.

Usage:
    from src.database import DatabaseManager
    from src.core.task import TaskStatus, enqueue_task, dequeue_task, update_task_status

    manager = DatabaseManager(url)
    await manager.init_db()

    task_id = await enqueue_task(manager, task_type="qualify_lead", payload={"name": "Acme"})
    task = await dequeue_task(manager)
    await update_task_status(manager, task_id, TaskStatus.RUNNING)
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from sqlalchemy import (
    Column,
    DateTime,
    Integer,
    String,
    Text,
    insert,
    select,
    update,
)

from src.database.connection import DatabaseManager, metadata

# ---------------------------------------------------------------------------
# Task status lifecycle
# ---------------------------------------------------------------------------


class TaskStatus(str, Enum):
    """
    Task lifecycle states.

    Supported transitions:
        PENDING  → RUNNING
        RUNNING  → COMPLETED
        RUNNING  → FAILED
        PENDING  → CANCELLED
        RUNNING  → CANCELLED

    These are the transitions enforced in this milestone.
    Future milestones may add retry-related transitions.
    """

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# Valid state transitions enforced by update_task_status().
_VALID_TRANSITIONS: dict[TaskStatus, set[TaskStatus]] = {
    TaskStatus.PENDING: {TaskStatus.RUNNING, TaskStatus.CANCELLED},
    TaskStatus.RUNNING: {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED},
    TaskStatus.COMPLETED: set(),
    TaskStatus.FAILED: set(),
    TaskStatus.CANCELLED: set(),
}


# ---------------------------------------------------------------------------
# Task table definition (SQLAlchemy Core)
# ---------------------------------------------------------------------------

tasks_table = Column  # forward declaration replaced below

tasks_table = metadata.tables.get("tasks")  # type: ignore[assignment]
if tasks_table is None:
    from sqlalchemy import Table

    tasks_table = Table(
        "tasks",
        metadata,
        Column("id", String(36), primary_key=True),
        Column("task_type", String(100), nullable=False),
        Column("domain", String(50), nullable=True),
        Column("status", String(20), nullable=False, default=TaskStatus.PENDING.value),
        Column("priority", Integer, nullable=False, default=0),
        Column("payload", Text, nullable=True),
        Column("result", Text, nullable=True),
        Column("retry_count", Integer, nullable=False, default=0),
        Column("idempotency_key", String(100), nullable=True, unique=True),
        Column("created_at", DateTime, nullable=False),
        Column("updated_at", DateTime, nullable=False),
        Column("started_at", DateTime, nullable=True),
        Column("completed_at", DateTime, nullable=True),
    )


# ---------------------------------------------------------------------------
# JSON serialization helpers
# ---------------------------------------------------------------------------


def _serialize_payload(payload: Any) -> str | None:
    """
    Serialize a payload to a JSON string for storage.

    Accepts None, str, int, float, bool, list, and dict values
    (arbitrarily nested as long as all leaves are JSON-compatible).

    Raises:
        TypeError: If the payload contains non-JSON-serializable values.
    """
    if payload is None:
        return None
    try:
        return json.dumps(payload, ensure_ascii=False)
    except (TypeError, ValueError) as exc:
        raise TypeError(
            f"Task payload is not JSON-serializable: {exc}"
        ) from exc


def _deserialize_payload(raw: str | None) -> Any:
    """Deserialize a JSON string back to a Python object."""
    if raw is None:
        return None
    return json.loads(raw)


# ---------------------------------------------------------------------------
# Queue operations
# ---------------------------------------------------------------------------


def _utcnow() -> datetime:
    """Return the current UTC time (timezone-aware)."""
    return datetime.now(timezone.utc)


async def enqueue_task(
    db: DatabaseManager,
    *,
    task_type: str,
    payload: Any = None,
    priority: int = 0,
    domain: str | None = None,
    idempotency_key: str | None = None,
) -> str:
    """
    Create and persist a new task in PENDING status.

    Args:
        db: An initialized DatabaseManager.
        task_type: A short string identifying the kind of work (e.g. "qualify_lead").
        payload: JSON-compatible data to attach to the task.
        priority: Higher numbers are dequeued first.  Default is 0.
        domain: Optional domain classification (e.g. "sales").
        idempotency_key: Optional key for future deduplication.

    Returns:
        The generated task ID (UUID4 string).

    Raises:
        TypeError: If the payload is not JSON-serializable.
        RuntimeError: If the database is not initialized.
    """
    task_id = str(uuid.uuid4())
    now = _utcnow()
    serialized = _serialize_payload(payload)

    async with db.connection() as conn:
        await conn.execute(
            insert(tasks_table).values(
                id=task_id,
                task_type=task_type,
                domain=domain,
                status=TaskStatus.PENDING.value,
                priority=priority,
                payload=serialized,
                result=None,
                retry_count=0,
                idempotency_key=idempotency_key,
                created_at=now,
                updated_at=now,
                started_at=None,
                completed_at=None,
            )
        )
        await conn.commit()
    return task_id


async def get_task(db: DatabaseManager, task_id: str) -> dict[str, Any] | None:
    """
    Retrieve a single task by ID.

    Returns a dict with all task fields (payload/result deserialized),
    or None if the task does not exist.
    """
    async with db.connection() as conn:
        result = await conn.execute(
            select(tasks_table).where(tasks_table.c.id == task_id)
        )
        row = result.mappings().first()
    if row is None:
        return None
    return _row_to_dict(row)


async def dequeue_task(db: DatabaseManager) -> dict[str, Any] | None:
    """
    Retrieve the next eligible PENDING task without changing its status.

    Ordering:
        1. Higher priority first.
        2. Earlier created_at first (FIFO within the same priority).

    Returns a task dict or None if the queue is empty.

    Note:
        This does NOT atomically mark the task as RUNNING.  In a
        single-process setup this is fine.  Future milestones will add
        SELECT … FOR UPDATE or compare-and-swap for multi-worker safety.
    """
    async with db.connection() as conn:
        result = await conn.execute(
            select(tasks_table)
            .where(tasks_table.c.status == TaskStatus.PENDING.value)
            .order_by(tasks_table.c.priority.desc(), tasks_table.c.created_at.asc())
            .limit(1)
        )
        row = result.mappings().first()
    if row is None:
        return None
    return _row_to_dict(row)


async def update_task_status(
    db: DatabaseManager,
    task_id: str,
    new_status: TaskStatus,
    *,
    result: Any = None,
) -> None:
    """
    Transition a task to a new status.

    Enforces valid lifecycle transitions.  Updates ``updated_at``
    automatically.  Sets ``started_at`` when transitioning to RUNNING,
    and ``completed_at`` when transitioning to COMPLETED or FAILED.

    Args:
        db: An initialized DatabaseManager.
        task_id: The task to update.
        new_status: The target status.
        result: Optional JSON-compatible result data (typically set on
                COMPLETED or FAILED).

    Raises:
        ValueError: If the task does not exist or the transition is invalid.
        TypeError: If the result is not JSON-serializable.
    """
    task = await get_task(db, task_id)
    if task is None:
        raise ValueError(f"Task not found: {task_id}")

    current = TaskStatus(task["status"])
    if new_status not in _VALID_TRANSITIONS[current]:
        raise ValueError(
            f"Invalid status transition: {current.value} → {new_status.value}"
        )

    now = _utcnow()
    values: dict[str, Any] = {
        "status": new_status.value,
        "updated_at": now,
    }

    if result is not None:
        values["result"] = _serialize_payload(result)

    if new_status == TaskStatus.RUNNING:
        values["started_at"] = now

    if new_status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
        values["completed_at"] = now

    async with db.connection() as conn:
        await conn.execute(
            update(tasks_table).where(tasks_table.c.id == task_id).values(**values)
        )
        await conn.commit()


async def list_tasks(
    db: DatabaseManager,
    *,
    status: TaskStatus | None = None,
) -> list[dict[str, Any]]:
    """
    List tasks, optionally filtered by status.

    Returns a list of task dicts ordered by priority desc, created_at asc.
    """
    stmt = select(tasks_table).order_by(
        tasks_table.c.priority.desc(), tasks_table.c.created_at.asc()
    )
    if status is not None:
        stmt = stmt.where(tasks_table.c.status == status.value)

    async with db.connection() as conn:
        result = await conn.execute(stmt)
        rows = result.mappings().all()
    return [_row_to_dict(row) for row in rows]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _row_to_dict(row: Any) -> dict[str, Any]:
    """Convert a SQLAlchemy row mapping to a plain dict with deserialized JSON fields."""
    d = dict(row)
    d["payload"] = _deserialize_payload(d.get("payload"))
    d["result"] = _deserialize_payload(d.get("result"))
    return d
