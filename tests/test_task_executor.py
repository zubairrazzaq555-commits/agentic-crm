"""Integration tests for TaskExecutor (Milestone 3.3).

Verifies the complete flow:
Persistent Task Queue -> Task Retrieval -> State Mapping -> LangGraph
    -> ProviderManager -> MockProvider -> Result Persistence -> Lifecycle Updates
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from src.core.task import (
    TaskStatus,
    enqueue_task,
    get_task,
    update_task_status,
)
from src.core.task_executor import TaskExecutor
from src.database.connection import DatabaseManager
from src.providers.manager import ProviderManager
from src.providers.mock_provider import MockProvider


@pytest.fixture()
async def test_db(tmp_path: Path) -> Any:
    """Create and initialize an isolated SQLite database for testing."""
    db_file = tmp_path / "test_executor.db"
    manager = DatabaseManager(f"sqlite+aiosqlite:///{db_file.as_posix()}")
    await manager.init_db()
    try:
        yield manager
    finally:
        await manager.dispose()


@pytest.fixture()
def provider_manager() -> ProviderManager:
    """Create a ProviderManager with a registered MockProvider."""
    pm = ProviderManager(allow_paid=False)
    pm.register(MockProvider(name="mock", custom_response="MOCK_QUALIFIED_RESULT"))
    return pm


@pytest.mark.asyncio
async def test_task_executor_end_to_end_success(
    test_db: DatabaseManager,
    provider_manager: ProviderManager,
) -> None:
    """Verify task queue -> LangGraph -> MockProvider -> database result completion."""
    # 1. Enqueue task in PENDING status
    task_id = await enqueue_task(
        test_db,
        task_type="lead_scoring",
        payload={"company": "Globex Corp", "prompt": "Score lead Globex Corp"},
        priority=10,
    )

    initial_task = await get_task(test_db, task_id)
    assert initial_task is not None
    assert initial_task["status"] == TaskStatus.PENDING.value
    assert initial_task["started_at"] is None
    assert initial_task["completed_at"] is None

    # 2. Execute task via TaskExecutor
    executor = TaskExecutor(test_db, provider_manager, default_provider="mock")
    executed_task = await executor.execute_task_by_id(task_id)

    # 3. Verify final state and transition compliance
    assert executed_task["id"] == task_id
    assert executed_task["status"] == TaskStatus.COMPLETED.value
    assert executed_task["started_at"] is not None
    assert executed_task["completed_at"] is not None

    # Verify persisted structured result
    result = executed_task["result"]
    assert result is not None
    assert result["status"] == "success"
    assert result["output"] == "MOCK_QUALIFIED_RESULT"
    assert result["provider"] == "mock"
    assert result["steps"] == 2


@pytest.mark.asyncio
async def test_task_executor_process_next_task(
    test_db: DatabaseManager,
    provider_manager: ProviderManager,
) -> None:
    """Verify process_next_task dequeues and processes highest priority task first."""
    executor = TaskExecutor(test_db, provider_manager, default_provider="mock")

    # Enqueue low priority then high priority task
    low_id = await enqueue_task(test_db, task_type="low_task", priority=5)
    high_id = await enqueue_task(test_db, task_type="high_task", priority=50)

    # First call should process high_task
    first_processed = await executor.process_next_task()
    assert first_processed is not None
    assert first_processed["id"] == high_id
    assert first_processed["status"] == TaskStatus.COMPLETED.value

    # Second call should process low_task
    second_processed = await executor.process_next_task()
    assert second_processed is not None
    assert second_processed["id"] == low_id
    assert second_processed["status"] == TaskStatus.COMPLETED.value

    # Third call should return None (queue empty)
    empty = await executor.process_next_task()
    assert empty is None


@pytest.mark.asyncio
async def test_task_executor_provider_failure_transitions_to_failed(
    test_db: DatabaseManager,
) -> None:
    """Verify provider errors transition task to FAILED with structured error details."""
    pm = ProviderManager(allow_paid=False)
    pm.register(MockProvider(name="failing_mock", simulate_failure=True))

    executor = TaskExecutor(test_db, pm, default_provider="failing_mock")

    task_id = await enqueue_task(test_db, task_type="fail_test", payload={"test": True})
    executed = await executor.execute_task_by_id(task_id)

    assert executed["status"] == TaskStatus.FAILED.value
    assert executed["started_at"] is not None
    assert executed["completed_at"] is not None

    result = executed["result"]
    assert result["status"] == "failed"
    assert "Simulated mock provider failure" in result["error"]


@pytest.mark.asyncio
async def test_task_executor_invalid_transitions_rejected(
    test_db: DatabaseManager,
    provider_manager: ProviderManager,
) -> None:
    """Verify non-existent and already-completed tasks cannot be executed."""
    executor = TaskExecutor(test_db, provider_manager)

    # 1. Non-existent task ID raises ValueError
    with pytest.raises(ValueError, match="Task not found"):
        await executor.execute_task_by_id("non-existent-uuid")

    # 2. Task already in COMPLETED status cannot be executed
    task_id = await enqueue_task(test_db, task_type="completed_test")
    await update_task_status(test_db, task_id, TaskStatus.RUNNING)
    await update_task_status(test_db, task_id, TaskStatus.COMPLETED)

    with pytest.raises(ValueError, match="must be 'pending'"):
        await executor.execute_task_by_id(task_id)
