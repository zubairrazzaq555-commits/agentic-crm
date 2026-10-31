"""
Agentic CRM — Async SQLite connection management.

Provides a DatabaseManager class for SQLAlchemy Core + aiosqlite engine
lifecycle: initialization, connection access, and disposal.

No global side effects on import — the database is only created when
init_db() is explicitly called.

Usage:
    from src.database import DatabaseManager

    manager = DatabaseManager("sqlite+aiosqlite:///data/agentic_crm.db")
    await manager.init_db()

    async with manager.connection() as conn:
        result = await conn.execute(text("SELECT 1"))

    await manager.dispose()
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncGenerator

from sqlalchemy import MetaData, event
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine

# ---------------------------------------------------------------------------
# Shared metadata registry
# ---------------------------------------------------------------------------
# Future milestones register their table definitions against this MetaData
# instance.  DatabaseManager.init_db() calls metadata.create_all() to
# create any registered tables (using CREATE TABLE IF NOT EXISTS).
# ---------------------------------------------------------------------------
metadata = MetaData()


class DatabaseManager:
    """
    Manages the async SQLAlchemy engine lifecycle for SQLite.

    Responsibilities:
    - Create the async engine from a database URL.
    - Ensure the data directory exists before creating the database file.
    - Initialize the schema (CREATE TABLE IF NOT EXISTS for registered tables).
    - Provide an async context manager for database connections.
    - Cleanly dispose the engine.

    Thread-safety note:
        This class is designed for use within a single asyncio event loop.
        It is NOT thread-safe.
    """

    def __init__(self, database_url: str) -> None:
        """
        Create a DatabaseManager.

        Args:
            database_url: A SQLAlchemy async database URL.
                          Example: "sqlite+aiosqlite:///data/agentic_crm.db"
        """
        self._database_url = database_url
        self._engine: AsyncEngine | None = None

    # -- Properties ---------------------------------------------------------

    @property
    def engine(self) -> AsyncEngine | None:
        """The underlying async engine, or None if not yet initialized."""
        return self._engine

    @property
    def database_url(self) -> str:
        """The database URL this manager was configured with."""
        return self._database_url

    # -- Initialization -----------------------------------------------------

    def _ensure_data_directory(self) -> None:
        """Create the parent directory for the database file if it does not exist."""
        # Only relevant for file-based SQLite databases
        if ":memory:" in self._database_url:
            return

        # Not a file-based database (e.g. PostgreSQL) — skip
        if "sqlite" not in self._database_url.lower():
            return

        # Extract the file path from the URL
        # sqlite+aiosqlite:///path/to/db  →  path/to/db
        parts = self._database_url.split("///", 1)
        if len(parts) < 2 or not parts[1]:
            return

        db_path = Path(parts[1])
        db_path.parent.mkdir(parents=True, exist_ok=True)

    async def init_db(self) -> None:
        """
        Initialize the database.

        - Creates the data directory if necessary.
        - Creates the async engine (if not already created).
        - Runs CREATE TABLE IF NOT EXISTS for all tables registered
          in the shared ``metadata`` instance.

        Safe to call multiple times — does not destroy existing data.
        """
        self._ensure_data_directory()

        if self._engine is None:
            self._engine = create_async_engine(
                self._database_url,
                echo=False,
            )
            if "sqlite" in self._database_url.lower():
                @event.listens_for(self._engine.sync_engine, "connect")
                def _set_sqlite_pragma(dbapi_connection: Any, connection_record: Any) -> None:
                    cursor = dbapi_connection.cursor()
                    cursor.execute("PRAGMA foreign_keys=ON")
                    cursor.close()

        # Create all tables registered in metadata.
        # In this milestone there are no tables yet, but this ensures
        # the mechanism is wired up for future milestones.
        async with self._engine.begin() as conn:
            await conn.run_sync(metadata.create_all)

    # -- Connection access --------------------------------------------------

    @asynccontextmanager
    async def connection(self) -> AsyncGenerator[AsyncConnection, None]:
        """
        Async context manager that yields a database connection.

        The connection is automatically returned to the pool when the
        context exits.

        Raises:
            RuntimeError: If the engine has not been initialized via init_db().
        """
        if self._engine is None:
            raise RuntimeError(
                "Database engine not initialized. Call init_db() first."
            )
        async with self._engine.connect() as conn:
            yield conn

    # -- Disposal -----------------------------------------------------------

    async def dispose(self) -> None:
        """
        Dispose the engine and release all connection pool resources.

        After disposal, init_db() must be called again before using
        the manager.  Safe to call even if the engine was never initialized.
        """
        if self._engine is not None:
            await self._engine.dispose()
            self._engine = None
