"""Agentic CRM — Database foundation.

Provides async SQLite access via SQLAlchemy Core + aiosqlite.
"""

from src.database.connection import DatabaseManager, metadata
# Ensure all core and CRM table schemas are registered on shared metadata
import src.core.task  # noqa: F401
import src.crm.models  # noqa: F401

__all__ = ["DatabaseManager", "metadata"]
