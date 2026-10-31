"""Agentic CRM — Contact Service.

Encapsulates business rules and validation for Contact management:
- Email validation & duplicate protection
- Account association verification
- Primary contact management
"""

from __future__ import annotations

import re
from typing import Any, Optional

from src.crm.models import Contact
from src.crm.repositories.account_repo import AccountRepository
from src.crm.repositories.contact_repo import ContactRepository
from src.database.connection import DatabaseManager

_EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class ContactService:
    """Business logic service for Contact operations."""

    def __init__(self, db: DatabaseManager) -> None:
        self._db = db
        self._contact_repo = ContactRepository(db)
        self._account_repo = AccountRepository(db)

    def _validate_contact_input(self, first_name: str, last_name: str, email: str) -> None:
        if not first_name or not first_name.strip():
            raise ValueError("First name is required and cannot be empty.")
        if not last_name or not last_name.strip():
            raise ValueError("Last name is required and cannot be empty.")
        if not email or not email.strip():
            raise ValueError("Email is required and cannot be empty.")
        if not _EMAIL_REGEX.match(email.strip()):
            raise ValueError(f"Invalid email format: '{email}'.")

    async def create_contact(
        self,
        *,
        first_name: str,
        last_name: str,
        email: str,
        account_id: Optional[str] = None,
        phone: Optional[str] = None,
        title: Optional[str] = None,
        department: Optional[str] = None,
        is_primary: bool = False,
    ) -> Contact:
        """Validate and create a Contact."""
        self._validate_contact_input(first_name, last_name, email)
        clean_email = email.strip().lower()

        existing = await self._contact_repo.get_by_email(clean_email)
        if existing:
            raise ValueError(f"A contact with email '{clean_email}' already exists (ID: {existing.id}).")

        if account_id:
            account = await self._account_repo.get_by_id(account_id)
            if not account:
                raise ValueError(f"Account with ID '{account_id}' does not exist.")

        contact = Contact(
            id="",
            account_id=account_id,
            first_name=first_name.strip(),
            last_name=last_name.strip(),
            email=clean_email,
            phone=phone.strip() if phone else None,
            title=title.strip() if title else None,
            department=department.strip() if department else None,
            is_primary=bool(is_primary),
        )
        return await self._contact_repo.create(contact)

    async def get_contact(self, contact_id: str) -> Optional[Contact]:
        """Fetch contact by ID."""
        return await self._contact_repo.get_by_id(contact_id)

    async def update_contact(self, contact_id: str, **updates: Any) -> Optional[Contact]:
        """Validate and apply updates to a contact."""
        existing = await self._contact_repo.get_by_id(contact_id)
        if not existing:
            raise ValueError(f"Contact not found with ID '{contact_id}'.")

        if "email" in updates and updates["email"]:
            clean_email = updates["email"].strip().lower()
            if not _EMAIL_REGEX.match(clean_email):
                raise ValueError(f"Invalid email format: '{clean_email}'.")
            email_check = await self._contact_repo.get_by_email(clean_email)
            if email_check and email_check.id != contact_id:
                raise ValueError(f"A contact with email '{clean_email}' already exists.")
            updates["email"] = clean_email

        if "account_id" in updates and updates["account_id"]:
            account = await self._account_repo.get_by_id(updates["account_id"])
            if not account:
                raise ValueError(f"Account with ID '{updates['account_id']}' does not exist.")

        return await self._contact_repo.update(contact_id, updates)

    async def list_contacts_by_account(self, account_id: str) -> list[Contact]:
        """List all contacts belonging to an account."""
        return await self._contact_repo.list_by_account(account_id)

    async def search_contacts(
        self,
        query: str,
        *,
        account_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Contact]:
        """Search contacts by query string."""
        return await self._contact_repo.search(query, account_id=account_id, limit=limit, offset=offset)

    async def list_contacts(
        self,
        *,
        account_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Contact]:
        """List contacts."""
        return await self._contact_repo.list(account_id=account_id, limit=limit, offset=offset)

    async def delete_contact(self, contact_id: str) -> bool:
        """Delete a contact."""
        return await self._contact_repo.delete(contact_id)

