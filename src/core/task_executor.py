"""Task executor service coordinating queue persistence, LangGraph, and ProviderManager."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from src.core.task import (
    TaskStatus,
    dequeue_task,
    get_task,
    update_task_status,
)
from src.database.connection import DatabaseManager
from src.graph.task_graph import create_task_graph
from src.graph.task_state import (
    graph_state_to_task_result,
    task_to_graph_state,
)
from src.providers.manager import ProviderManager

logger = logging.getLogger("agentic_crm.core.task_executor")


class TaskExecutor:
    """Coordinates task execution between the persistent task queue and LangGraph.

    Maintains separation of concerns:
    - Database operations and lifecycle state transitions stay in this service.
    - Graph nodes focus purely on state transforms and provider invocations.
    - ProviderManager provides explicit lookup and health tracking.
    """

    def __init__(
        self,
        db: DatabaseManager,
        provider_manager: ProviderManager,
        default_provider: str = "mock",
    ) -> None:
        """Initialize the task executor.

        Args:
            db: Initialized DatabaseManager instance.
            provider_manager: ProviderManager with registered providers.
            default_provider: Default provider name when unspecified in task payload.
        """
        self.db = db
        self.provider_manager = provider_manager
        self.default_provider = default_provider
        self.graph = create_task_graph(provider_manager)

    async def execute_task_by_id(
        self,
        task_id: str,
        provider_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute a specific task by its unique ID.

        Lifecycle:
            PENDING -> RUNNING -> COMPLETED (on graph success)
            PENDING -> RUNNING -> FAILED    (on graph failure or unhandled error)

        Args:
            task_id: Unique task identifier.
            provider_name: Optional override for provider selection.

        Returns:
            Updated task dictionary after execution.

        Raises:
            ValueError: If the task does not exist in the database.
        """
        task = await get_task(self.db, task_id)
        if task is None:
            raise ValueError(f"Task not found: {task_id}")

        current_status = TaskStatus(task["status"])
        if current_status != TaskStatus.PENDING:
            raise ValueError(
                f"Task {task_id} cannot be executed because status is {current_status.value!r} (must be 'pending')"
            )

        # 1. Transition PENDING -> RUNNING
        await update_task_status(self.db, task_id, TaskStatus.RUNNING)
        logger.info("Task %s transitioned to RUNNING", task_id)

        # 2. Map task record to LangGraph state
        effective_provider = provider_name or self.default_provider
        initial_state = task_to_graph_state(task, default_provider=effective_provider)

        # 3. Invoke LangGraph asynchronously
        try:
            final_state = await self.graph.ainvoke(initial_state)
            result_payload = graph_state_to_task_result(final_state)

            if final_state.get("execution_status") == "SUCCESS":
                # 4a. Transition RUNNING -> COMPLETED
                await update_task_status(
                    self.db,
                    task_id,
                    TaskStatus.COMPLETED,
                    result=result_payload,
                )
                logger.info("Task %s completed successfully", task_id)
            else:
                # 4b. Transition RUNNING -> FAILED (structured graph failure)
                await update_task_status(
                    self.db,
                    task_id,
                    TaskStatus.FAILED,
                    result=result_payload,
                )
                logger.warning(
                    "Task %s marked FAILED by graph: %s",
                    task_id,
                    result_payload.get("error"),
                )

        except Exception as exc:
            # 4c. Transition RUNNING -> FAILED on unhandled exception
            logger.error("Unhandled error executing task %s: %s", task_id, exc)
            error_result = {
                "status": "failed",
                "error": str(exc),
                "provider": effective_provider,
            }
            await update_task_status(
                self.db,
                task_id,
                TaskStatus.FAILED,
                result=error_result,
            )

        # 5. Return latest task state from database
        updated = await get_task(self.db, task_id)
        assert updated is not None
        return updated

    async def process_next_task(
        self,
        provider_name: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Dequeue the next eligible PENDING task and execute it.

        Args:
            provider_name: Optional override for provider selection.

        Returns:
            Updated task dictionary after execution, or None if queue was empty.
        """
        task = await dequeue_task(self.db)
        if task is None:
            return None

        return await self.execute_task_by_id(task["id"], provider_name=provider_name)
