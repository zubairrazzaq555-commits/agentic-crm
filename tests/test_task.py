"""
Tests for src.core.task — Task model, status lifecycle, and persistent queue.

Covers:
- Task table creation via init_db()
- Task creation and default values
- Unique task IDs (UUID)
- JSON payload serialization / deserialization
- Result persistence
- Invalid payload rejection
- Enqueue operation
- Empty queue behavior
- Priority ordering (higher first)
- FIFO ordering (equal priority)
- Dequeue excludes completed tasks
- Dequeue excludes failed tasks
- Dequeue excludes cancelled tasks
- Status transitions: pending → running, running → completed, running → failed
- Invalid status transition rejection
- Timestamp updates (updated_at, started_at, completed_at)
- Persistence across database disposal / reinitialization
- list_tasks with status filter
- Cancellation transitions
- Non-existent task handling
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest

from src.core.task import (
    TaskStatus,
    _deserialize_payload,
    _serialize_payload,
    dequeue_task,
    enqueue_task,
    get_task,
    list_tasks,
    update_task_status,
)
from src.database.connection import DatabaseManager


# ==========================================================================
# Fixtures
# ==========================================================================


@pytest.fixture()
async def db(tmp_path: Path) -> DatabaseManager:
    """
    Provide an initialized DatabaseManager with the tasks table created.

    Uses a temporary SQLite file for full isolation.
    """
    # Import task module to ensure the table is registered in metadata
    import src.core.task  # noqa: F401

    db_file = tmp_path / "test_tasks.db"
    url = f"sqlite+aiosqlite:///{db_file.as_posix()}"
    manager = DatabaseManager(url)
    await manager.init_db()
    yield manager  # type: ignore[misc]
    await manager.dispose()


# ==========================================================================
# Table creation
# ==========================================================================


class TestTableCreation:
    """Verify the tasks table is created by init_db()."""

    async def test_tasks_table_exists(self, db: DatabaseManager) -> None:
        """After init_db(), the tasks table should exist in the database."""
        from sqlalchemy import text

        async with db.connection() as conn:
            result = await conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' AND name='tasks'")
            )
            row = result.scalar()
        assert row == "tasks"

    async def test_tasks_table_has_expected_columns(self, db: DatabaseManager) -> None:
        """The tasks table should have all required columns."""
        from sqlalchemy import text

        async with db.connection() as conn:
            result = await conn.execute(text("PRAGMA table_info(tasks)"))
            columns = {row[1] for row in result.fetchall()}

        expected = {
            "id", "task_type", "domain", "status", "priority",
            "payload", "result", "retry_count", "idempotency_key",
            "created_at", "updated_at", "started_at", "completed_at",
        }
        assert expected.issubset(columns)


# ==========================================================================
# Serialization
# ==========================================================================


class TestSerialization:
    """Verify JSON serialization helpers."""

    def test_serialize_none(self) -> None:
        assert _serialize_payload(None) is None

    def test_serialize_dict(self) -> None:
        result = _serialize_payload({"key": "value", "num": 42})
        assert '"key"' in result
        assert '"num"' in result

    def test_serialize_list(self) -> None:
        result = _serialize_payload([1, 2, "three"])
        assert result is not None

    def test_serialize_string(self) -> None:
        result = _serialize_payload("hello")
        assert result == '"hello"'

    def test_serialize_number(self) -> None:
        result = _serialize_payload(42)
        assert result == "42"

    def test_serialize_boolean(self) -> None:
        result = _serialize_payload(True)
        assert result == "true"

    def test_serialize_nested(self) -> None:
        payload = {"list": [1, {"nested": True}], "null_val": None}
        result = _serialize_payload(payload)
        assert result is not None

    def test_serialize_invalid_raises_type_error(self) -> None:
        with pytest.raises(TypeError, match="not JSON-serializable"):
            _serialize_payload(object())

    def test_serialize_set_raises_type_error(self) -> None:
        with pytest.raises(TypeError, match="not JSON-serializable"):
            _serialize_payload({"a_set": {1, 2, 3}})

    def test_deserialize_none(self) -> None:
        assert _deserialize_payload(None) is None

    def test_deserialize_roundtrip(self) -> None:
        original = {"key": [1, 2, None], "flag": False}
        serialized = _serialize_payload(original)
        result = _deserialize_payload(serialized)
        assert result == original


# ==========================================================================
# Task status enum
# ==========================================================================


class TestTaskStatus:
    """Verify status enum values and string representation."""

    def test_status_values(self) -> None:
        assert TaskStatus.PENDING.value == "pending"
        assert TaskStatus.RUNNING.value == "running"
        assert TaskStatus.COMPLETED.value == "completed"
        assert TaskStatus.FAILED.value == "failed"
        assert TaskStatus.CANCELLED.value == "cancelled"

    def test_status_from_string(self) -> None:
        assert TaskStatus("pending") == TaskStatus.PENDING
        assert TaskStatus("running") == TaskStatus.RUNNING


# ==========================================================================
# Enqueue
# ==========================================================================


class TestEnqueue:
    """Verify task creation and enqueue behavior."""

    async def test_enqueue_returns_id(self, db: DatabaseManager) -> None:
        task_id = await enqueue_task(db, task_type="test")
        assert isinstance(task_id, str)
        assert len(task_id) == 36  # UUID format

    async def test_enqueue_creates_pending_task(self, db: DatabaseManager) -> None:
        task_id = await enqueue_task(db, task_type="test")
        task = await get_task(db, task_id)
        assert task is not None
        assert task["status"] == "pending"

    async def test_enqueue_default_priority(self, db: DatabaseManager) -> None:
        task_id = await enqueue_task(db, task_type="test")
        task = await get_task(db, task_id)
        assert task["priority"] == 0

    async def test_enqueue_custom_priority(self, db: DatabaseManager) -> None:
        task_id = await enqueue_task(db, task_type="test", priority=10)
        task = await get_task(db, task_id)
        assert task["priority"] == 10

    async def test_enqueue_with_payload(self, db: DatabaseManager) -> None:
        payload = {"lead_name": "Acme Corp", "score": 85}
        task_id = await enqueue_task(db, task_type="score_lead", payload=payload)
        task = await get_task(db, task_id)
        assert task["payload"] == payload

    async def test_enqueue_with_none_payload(self, db: DatabaseManager) -> None:
        task_id = await enqueue_task(db, task_type="test", payload=None)
        task = await get_task(db, task_id)
        assert task["payload"] is None

    async def test_enqueue_with_domain(self, db: DatabaseManager) -> None:
        task_id = await enqueue_task(db, task_type="test", domain="sales")
        task = await get_task(db, task_id)
        assert task["domain"] == "sales"

    async def test_enqueue_with_idempotency_key(self, db: DatabaseManager) -> None:
        task_id = await enqueue_task(
            db, task_type="test", idempotency_key="unique-key-123"
        )
        task = await get_task(db, task_id)
        assert task["idempotency_key"] == "unique-key-123"

    async def test_enqueue_sets_timestamps(self, db: DatabaseManager) -> None:
        task_id = await enqueue_task(db, task_type="test")
        task = await get_task(db, task_id)
        assert task["created_at"] is not None
        assert task["updated_at"] is not None
        assert task["started_at"] is None
        assert task["completed_at"] is None

    async def test_enqueue_unique_ids(self, db: DatabaseManager) -> None:
        """Each enqueued task must get a unique ID."""
        ids = set()
        for _ in range(20):
            task_id = await enqueue_task(db, task_type="test")
            ids.add(task_id)
        assert len(ids) == 20

    async def test_enqueue_invalid_payload_raises(self, db: DatabaseManager) -> None:
        with pytest.raises(TypeError, match="not JSON-serializable"):
            await enqueue_task(db, task_type="test", payload=object())

    async def test_enqueue_retry_count_default(self, db: DatabaseManager) -> None:
        task_id = await enqueue_task(db, task_type="test")
        task = await get_task(db, task_id)
        assert task["retry_count"] == 0


# ==========================================================================
# Get task
# ==========================================================================


class TestGetTask:
    """Verify single-task retrieval."""

    async def test_get_existing_task(self, db: DatabaseManager) -> None:
        task_id = await enqueue_task(db, task_type="test")
        task = await get_task(db, task_id)
        assert task is not None
        assert task["id"] == task_id

    async def test_get_nonexistent_task(self, db: DatabaseManager) -> None:
        task = await get_task(db, "nonexistent-id")
        assert task is None


# ==========================================================================
# Dequeue
# ==========================================================================


class TestDequeue:
    """Verify queue retrieval (dequeue) behavior."""

    async def test_dequeue_empty_queue(self, db: DatabaseManager) -> None:
        task = await dequeue_task(db)
        assert task is None

    async def test_dequeue_returns_pending_task(self, db: DatabaseManager) -> None:
        task_id = await enqueue_task(db, task_type="test")
        task = await dequeue_task(db)
        assert task is not None
        assert task["id"] == task_id
        assert task["status"] == "pending"

    async def test_dequeue_priority_ordering(self, db: DatabaseManager) -> None:
        """Higher priority tasks should be dequeued first."""
        low_id = await enqueue_task(db, task_type="low", priority=1)
        high_id = await enqueue_task(db, task_type="high", priority=10)
        mid_id = await enqueue_task(db, task_type="mid", priority=5)

        task = await dequeue_task(db)
        assert task is not None
        assert task["id"] == high_id

    async def test_dequeue_fifo_same_priority(self, db: DatabaseManager) -> None:
        """Tasks with equal priority should be dequeued in FIFO order."""
        first_id = await enqueue_task(db, task_type="first", priority=0)
        # Small sleep to guarantee ordering
        await asyncio.sleep(0.01)
        second_id = await enqueue_task(db, task_type="second", priority=0)

        task = await dequeue_task(db)
        assert task is not None
        assert task["id"] == first_id

    async def test_dequeue_excludes_completed(self, db: DatabaseManager) -> None:
        """Completed tasks must not appear in dequeue results."""
        task_id = await enqueue_task(db, task_type="test")
        await update_task_status(db, task_id, TaskStatus.RUNNING)
        await update_task_status(db, task_id, TaskStatus.COMPLETED)

        result = await dequeue_task(db)
        assert result is None

    async def test_dequeue_excludes_failed(self, db: DatabaseManager) -> None:
        """Failed tasks must not appear in dequeue results."""
        task_id = await enqueue_task(db, task_type="test")
        await update_task_status(db, task_id, TaskStatus.RUNNING)
        await update_task_status(db, task_id, TaskStatus.FAILED)

        result = await dequeue_task(db)
        assert result is None

    async def test_dequeue_excludes_running(self, db: DatabaseManager) -> None:
        """Running tasks must not appear in dequeue results."""
        task_id = await enqueue_task(db, task_type="test")
        await update_task_status(db, task_id, TaskStatus.RUNNING)

        result = await dequeue_task(db)
        assert result is None

    async def test_dequeue_excludes_cancelled(self, db: DatabaseManager) -> None:
        """Cancelled tasks must not appear in dequeue results."""
        task_id = await enqueue_task(db, task_type="test")
        await update_task_status(db, task_id, TaskStatus.CANCELLED)

        result = await dequeue_task(db)
        assert result is None

    async def test_dequeue_skips_non_pending_returns_next(self, db: DatabaseManager) -> None:
        """Dequeue should skip completed/running tasks and return the next pending one."""
        done_id = await enqueue_task(db, task_type="done", priority=10)
        await update_task_status(db, done_id, TaskStatus.RUNNING)
        await update_task_status(db, done_id, TaskStatus.COMPLETED)

        pending_id = await enqueue_task(db, task_type="pending", priority=5)

        task = await dequeue_task(db)
        assert task is not None
        assert task["id"] == pending_id


# ==========================================================================
# Status transitions
# ==========================================================================


class TestStatusTransitions:
    """Verify valid and invalid status transitions."""

    async def test_pending_to_running(self, db: DatabaseManager) -> None:
        task_id = await enqueue_task(db, task_type="test")
        await update_task_status(db, task_id, TaskStatus.RUNNING)
        task = await get_task(db, task_id)
        assert task["status"] == "running"

    async def test_running_to_completed(self, db: DatabaseManager) -> None:
        task_id = await enqueue_task(db, task_type="test")
        await update_task_status(db, task_id, TaskStatus.RUNNING)
        await update_task_status(db, task_id, TaskStatus.COMPLETED)
        task = await get_task(db, task_id)
        assert task["status"] == "completed"

    async def test_running_to_failed(self, db: DatabaseManager) -> None:
        task_id = await enqueue_task(db, task_type="test")
        await update_task_status(db, task_id, TaskStatus.RUNNING)
        await update_task_status(db, task_id, TaskStatus.FAILED)
        task = await get_task(db, task_id)
        assert task["status"] == "failed"

    async def test_pending_to_cancelled(self, db: DatabaseManager) -> None:
        task_id = await enqueue_task(db, task_type="test")
        await update_task_status(db, task_id, TaskStatus.CANCELLED)
        task = await get_task(db, task_id)
        assert task["status"] == "cancelled"

    async def test_running_to_cancelled(self, db: DatabaseManager) -> None:
        task_id = await enqueue_task(db, task_type="test")
        await update_task_status(db, task_id, TaskStatus.RUNNING)
        await update_task_status(db, task_id, TaskStatus.CANCELLED)
        task = await get_task(db, task_id)
        assert task["status"] == "cancelled"

    # -- Invalid transitions -----------------------------------------------

    async def test_pending_to_completed_invalid(self, db: DatabaseManager) -> None:
        task_id = await enqueue_task(db, task_type="test")
        with pytest.raises(ValueError, match="Invalid status transition"):
            await update_task_status(db, task_id, TaskStatus.COMPLETED)

    async def test_pending_to_failed_invalid(self, db: DatabaseManager) -> None:
        task_id = await enqueue_task(db, task_type="test")
        with pytest.raises(ValueError, match="Invalid status transition"):
            await update_task_status(db, task_id, TaskStatus.FAILED)

    async def test_completed_to_running_invalid(self, db: DatabaseManager) -> None:
        task_id = await enqueue_task(db, task_type="test")
        await update_task_status(db, task_id, TaskStatus.RUNNING)
        await update_task_status(db, task_id, TaskStatus.COMPLETED)
        with pytest.raises(ValueError, match="Invalid status transition"):
            await update_task_status(db, task_id, TaskStatus.RUNNING)

    async def test_failed_to_running_invalid(self, db: DatabaseManager) -> None:
        task_id = await enqueue_task(db, task_type="test")
        await update_task_status(db, task_id, TaskStatus.RUNNING)
        await update_task_status(db, task_id, TaskStatus.FAILED)
        with pytest.raises(ValueError, match="Invalid status transition"):
            await update_task_status(db, task_id, TaskStatus.RUNNING)

    async def test_completed_to_pending_invalid(self, db: DatabaseManager) -> None:
        task_id = await enqueue_task(db, task_type="test")
        await update_task_status(db, task_id, TaskStatus.RUNNING)
        await update_task_status(db, task_id, TaskStatus.COMPLETED)
        with pytest.raises(ValueError, match="Invalid status transition"):
            await update_task_status(db, task_id, TaskStatus.PENDING)

    async def test_update_nonexistent_task_raises(self, db: DatabaseManager) -> None:
        with pytest.raises(ValueError, match="Task not found"):
            await update_task_status(db, "no-such-id", TaskStatus.RUNNING)


# ==========================================================================
# Result storage
# ==========================================================================


class TestResultStorage:
    """Verify result data persistence."""

    async def test_result_on_completion(self, db: DatabaseManager) -> None:
        task_id = await enqueue_task(db, task_type="test")
        await update_task_status(db, task_id, TaskStatus.RUNNING)
        await update_task_status(
            db, task_id, TaskStatus.COMPLETED, result={"score": 95, "status": "qualified"}
        )
        task = await get_task(db, task_id)
        assert task["result"] == {"score": 95, "status": "qualified"}

    async def test_result_on_failure(self, db: DatabaseManager) -> None:
        task_id = await enqueue_task(db, task_type="test")
        await update_task_status(db, task_id, TaskStatus.RUNNING)
        await update_task_status(
            db, task_id, TaskStatus.FAILED, result={"error": "provider timeout"}
        )
        task = await get_task(db, task_id)
        assert task["result"]["error"] == "provider timeout"

    async def test_no_result_by_default(self, db: DatabaseManager) -> None:
        task_id = await enqueue_task(db, task_type="test")
        task = await get_task(db, task_id)
        assert task["result"] is None


# ==========================================================================
# Timestamp behavior
# ==========================================================================


class TestTimestamps:
    """Verify timestamp management during status transitions."""

    async def test_created_at_set_on_enqueue(self, db: DatabaseManager) -> None:
        task_id = await enqueue_task(db, task_type="test")
        task = await get_task(db, task_id)
        assert task["created_at"] is not None

    async def test_updated_at_changes_on_status_update(self, db: DatabaseManager) -> None:
        task_id = await enqueue_task(db, task_type="test")
        task_before = await get_task(db, task_id)
        await asyncio.sleep(0.01)
        await update_task_status(db, task_id, TaskStatus.RUNNING)
        task_after = await get_task(db, task_id)
        assert task_after["updated_at"] >= task_before["updated_at"]

    async def test_started_at_set_on_running(self, db: DatabaseManager) -> None:
        task_id = await enqueue_task(db, task_type="test")
        task = await get_task(db, task_id)
        assert task["started_at"] is None

        await update_task_status(db, task_id, TaskStatus.RUNNING)
        task = await get_task(db, task_id)
        assert task["started_at"] is not None

    async def test_completed_at_set_on_completed(self, db: DatabaseManager) -> None:
        task_id = await enqueue_task(db, task_type="test")
        await update_task_status(db, task_id, TaskStatus.RUNNING)
        await update_task_status(db, task_id, TaskStatus.COMPLETED)
        task = await get_task(db, task_id)
        assert task["completed_at"] is not None

    async def test_completed_at_set_on_failed(self, db: DatabaseManager) -> None:
        task_id = await enqueue_task(db, task_type="test")
        await update_task_status(db, task_id, TaskStatus.RUNNING)
        await update_task_status(db, task_id, TaskStatus.FAILED)
        task = await get_task(db, task_id)
        assert task["completed_at"] is not None

    async def test_completed_at_null_for_pending(self, db: DatabaseManager) -> None:
        task_id = await enqueue_task(db, task_type="test")
        task = await get_task(db, task_id)
        assert task["completed_at"] is None


# ==========================================================================
# List tasks
# ==========================================================================


class TestListTasks:
    """Verify task listing with optional status filter."""

    async def test_list_all_tasks(self, db: DatabaseManager) -> None:
        await enqueue_task(db, task_type="a")
        await enqueue_task(db, task_type="b")
        tasks = await list_tasks(db)
        assert len(tasks) == 2

    async def test_list_filtered_by_status(self, db: DatabaseManager) -> None:
        id1 = await enqueue_task(db, task_type="a")
        await enqueue_task(db, task_type="b")
        await update_task_status(db, id1, TaskStatus.RUNNING)

        pending = await list_tasks(db, status=TaskStatus.PENDING)
        running = await list_tasks(db, status=TaskStatus.RUNNING)
        assert len(pending) == 1
        assert len(running) == 1

    async def test_list_empty(self, db: DatabaseManager) -> None:
        tasks = await list_tasks(db)
        assert tasks == []


# ==========================================================================
# Persistence across restart
# ==========================================================================


class TestPersistence:
    """Verify that tasks survive database disposal and reinitialization."""

    async def test_task_persists_across_restart(self, tmp_path: Path) -> None:
        """
        Critical test: enqueue a task, dispose the engine, create a new
        manager pointing at the same file, and confirm the task is still there.
        """
        import src.core.task  # noqa: F401

        db_file = tmp_path / "persist_test.db"
        url = f"sqlite+aiosqlite:///{db_file.as_posix()}"

        # Session 1: enqueue a task
        manager1 = DatabaseManager(url)
        await manager1.init_db()
        task_id = await enqueue_task(
            manager1,
            task_type="persist_check",
            payload={"key": "value"},
            priority=5,
        )
        await manager1.dispose()

        # Session 2: new manager, same database file
        manager2 = DatabaseManager(url)
        await manager2.init_db()
        try:
            task = await get_task(manager2, task_id)
            assert task is not None
            assert task["id"] == task_id
            assert task["task_type"] == "persist_check"
            assert task["payload"] == {"key": "value"}
            assert task["priority"] == 5
            assert task["status"] == "pending"
        finally:
            await manager2.dispose()

    async def test_task_status_persists_across_restart(self, tmp_path: Path) -> None:
        """Status changes must also survive a restart."""
        import src.core.task  # noqa: F401

        db_file = tmp_path / "persist_status.db"
        url = f"sqlite+aiosqlite:///{db_file.as_posix()}"

        # Session 1: enqueue and transition to running
        manager1 = DatabaseManager(url)
        await manager1.init_db()
        task_id = await enqueue_task(manager1, task_type="status_test")
        await update_task_status(manager1, task_id, TaskStatus.RUNNING)
        await update_task_status(
            manager1, task_id, TaskStatus.COMPLETED, result={"done": True}
        )
        await manager1.dispose()

        # Session 2: verify
        manager2 = DatabaseManager(url)
        await manager2.init_db()
        try:
            task = await get_task(manager2, task_id)
            assert task is not None
            assert task["status"] == "completed"
            assert task["result"] == {"done": True}
            assert task["started_at"] is not None
            assert task["completed_at"] is not None
        finally:
            await manager2.dispose()

    async def test_dequeue_works_after_restart(self, tmp_path: Path) -> None:
        """Dequeue should find tasks that were enqueued before a restart."""
        import src.core.task  # noqa: F401

        db_file = tmp_path / "persist_dequeue.db"
        url = f"sqlite+aiosqlite:///{db_file.as_posix()}"

        # Session 1
        manager1 = DatabaseManager(url)
        await manager1.init_db()
        task_id = await enqueue_task(manager1, task_type="dequeue_test", priority=3)
        await manager1.dispose()

        # Session 2
        manager2 = DatabaseManager(url)
        await manager2.init_db()
        try:
            task = await dequeue_task(manager2)
            assert task is not None
            assert task["id"] == task_id
        finally:
            await manager2.dispose()
