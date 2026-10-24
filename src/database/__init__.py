"""Agentic CRM — Database foundation.

Provides async SQLite access via SQLAlchemy Core + aiosqlite.
"""

from src.database.connection import DatabaseManager

__all__ = ["DatabaseManager"]
