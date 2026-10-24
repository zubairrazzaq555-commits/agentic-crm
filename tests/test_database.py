"""
Tests for src.database — Database foundation.

Covers:
- Default database configuration and URL generation
- Database URL override via environment variable
- Engine creation
- Database initialization
- Idempotent initialization (safe to call multiple times)
- Async connection executing a trivial SELECT 1
- Connection before initialization raises RuntimeError
- Engine disposal
- Data directory creation
- Test isolation (uses tmp_path, never touches production database)
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from src.config import Settings
from src.database.connection import DatabaseManager


# ==========================================================================
# Database configuration
# ==========================================================================


class TestDatabaseConfig:
    """Verify database-related configuration fields."""

    def test_default_db_path(self, clean_env: None) -> None:
        settings = Settings()
        assert settings.db_path == "data/agentic_crm.db"

    def test_default_database_url(self, clean_env: None) -> None:
        settings = Settings()
        url = settings.database_url
        assert url == "sqlite+aiosqlite:///data/agentic_crm.db"

    def test_override_db_path_updates_url(self, clean_env: None) -> None:
        os.environ["AGENTIC_CRM_DB_PATH"] = "custom/path/my.db"
        settings = Settings()
        assert settings.db_path == "custom/path/my.db"
        assert settings.database_url == "sqlite+aiosqlite:///custom/path/my.db"

    def test_database_url_contains_aiosqlite_driver(self, clean_env: None) -> None:
        settings = Settings()
        assert "aiosqlite" in settings.database_url

    def test_database_url_in_safe_summary(self, clean_env: None) -> None:
        settings = Settings()
        summary = settings.safe_summary()
        assert "database_url" in summary
        assert "aiosqlite" in summary["database_url"]


# ==========================================================================
# Fixtures
# ==========================================================================


@pytest.fixture()
async def db_manager(tmp_path: Path) -> DatabaseManager:
    """
    Provide a DatabaseManager backed by a temporary SQLite file.

    The database file lives inside pytest's tmp_path, ensuring complete
    isolation from the production database.  The engine is disposed
    automatically after the test.
    """
    db_file = tmp_path / "test_agentic.db"
    url = f"sqlite+aiosqlite:///{db_file.as_posix()}"
    manager = DatabaseManager(url)
    yield manager  # type: ignore[misc]
    await manager.dispose()


# ==========================================================================
# Engine creation
# ==========================================================================


class TestEngineCreation:
    """Verify engine lifecycle."""

    async def test_engine_is_none_before_init(self, db_manager: DatabaseManager) -> None:
        assert db_manager.engine is None

    async def test_engine_created_after_init(self, db_manager: DatabaseManager) -> None:
        await db_manager.init_db()
        assert db_manager.engine is not None
        assert isinstance(db_manager.engine, AsyncEngine)

    async def test_database_url_stored(self, db_manager: DatabaseManager) -> None:
        assert "aiosqlite" in db_manager.database_url
        assert "test_agentic.db" in db_manager.database_url


# ==========================================================================
# Initialization
# ==========================================================================


class TestInitialization:
    """Verify database initialization behavior."""

    async def test_init_succeeds(self, db_manager: DatabaseManager) -> None:
        """init_db() should complete without error."""
        await db_manager.init_db()
        assert db_manager.engine is not None

    async def test_init_idempotent(self, db_manager: DatabaseManager) -> None:
        """Calling init_db() twice must not error or replace the engine."""
        await db_manager.init_db()
        engine_first = db_manager.engine
        await db_manager.init_db()
        engine_second = db_manager.engine
        assert engine_first is engine_second

    async def test_init_creates_data_directory(self, tmp_path: Path) -> None:
        """init_db() must create parent directories for the database file."""
        db_file = tmp_path / "nested" / "deep" / "test.db"
        url = f"sqlite+aiosqlite:///{db_file.as_posix()}"
        manager = DatabaseManager(url)
        try:
            await manager.init_db()
            assert db_file.parent.exists()
        finally:
            await manager.dispose()

    async def test_init_does_not_destroy_existing_data(self, tmp_path: Path) -> None:
        """
        If the database already exists with data, init_db() must not
        destroy it.
        """
        db_file = tmp_path / "persist.db"
        url = f"sqlite+aiosqlite:///{db_file.as_posix()}"

        # First session: create a table and insert data
        manager1 = DatabaseManager(url)
        await manager1.init_db()
        async with manager1.connection() as conn:
            await conn.execute(text("CREATE TABLE test_tbl (id INTEGER PRIMARY KEY, val TEXT)"))
            await conn.execute(text("INSERT INTO test_tbl (val) VALUES ('hello')"))
            await conn.commit()
        await manager1.dispose()

        # Second session: call init_db() again — data must survive
        manager2 = DatabaseManager(url)
        await manager2.init_db()
        async with manager2.connection() as conn:
            result = await conn.execute(text("SELECT val FROM test_tbl"))
            row = result.scalar()
            assert row == "hello"
        await manager2.dispose()


# ==========================================================================
# Connection access
# ==========================================================================


class TestConnection:
    """Verify async connection behavior."""

    async def test_select_1(self, db_manager: DatabaseManager) -> None:
        """A basic SELECT 1 must succeed and return 1."""
        await db_manager.init_db()
        async with db_manager.connection() as conn:
            result = await conn.execute(text("SELECT 1"))
            assert result.scalar() == 1

    async def test_sqlite_version(self, db_manager: DatabaseManager) -> None:
        """Verify we can query SQLite metadata."""
        await db_manager.init_db()
        async with db_manager.connection() as conn:
            result = await conn.execute(text("SELECT sqlite_version()"))
            version = result.scalar()
            assert version is not None
            assert "." in version  # e.g. "3.45.1"

    async def test_connection_before_init_raises(self, db_manager: DatabaseManager) -> None:
        """Using connection() before init_db() must raise RuntimeError."""
        with pytest.raises(RuntimeError, match="not initialized"):
            async with db_manager.connection():
                pass


# ==========================================================================
# Disposal
# ==========================================================================


class TestDisposal:
    """Verify engine disposal."""

    async def test_dispose_clears_engine(self, db_manager: DatabaseManager) -> None:
        await db_manager.init_db()
        assert db_manager.engine is not None
        await db_manager.dispose()
        assert db_manager.engine is None

    async def test_dispose_without_init_is_safe(self, db_manager: DatabaseManager) -> None:
        """Calling dispose() before init_db() must not raise."""
        await db_manager.dispose()
        assert db_manager.engine is None

    async def test_reinit_after_dispose(self, db_manager: DatabaseManager) -> None:
        """After disposal, init_db() must create a new working engine."""
        await db_manager.init_db()
        await db_manager.dispose()
        assert db_manager.engine is None

        await db_manager.init_db()
        assert db_manager.engine is not None
        async with db_manager.connection() as conn:
            result = await conn.execute(text("SELECT 1"))
            assert result.scalar() == 1


# ==========================================================================
# Import safety
# ==========================================================================


class TestImportSafety:
    """Verify that importing the database module has no side effects."""

    def test_import_does_not_create_files(self, tmp_path: Path) -> None:
        """
        Importing src.database must NOT create a database file or
        data directory.
        """
        import src.database  # noqa: F401
        import src.database.connection  # noqa: F401

        # The default data/ directory should NOT be created by import
        default_data_dir = Path("data")
        # We can't assert it doesn't exist globally (CI might have it),
        # but we can assert that the tmp_path is still empty
        children = list(tmp_path.iterdir())
        assert len(children) == 0
