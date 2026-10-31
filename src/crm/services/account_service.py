"""Agentic CRM — Account Service.

Encapsulates business rules and metrics for Account management:
- Account uniqueness & tier validation
- Revenue calculations
- Account summary aggregation (contacts, opportunities, deals)
"""

from __future__ import annotations

from typing import Any, Optional

from src.crm.models import Account, AccountStatus, AccountTier, OpportunityStage
from src.crm.repositories.account_repo import AccountRepository
from src.crm.repositories.contact_repo import ContactRepository
from src.crm.repositories.opportunity_repo import OpportunityRepository
from src.database.connection import DatabaseManager


class AccountService:
    """Business logic service for Account operations."""

    def __init__(self, db: DatabaseManager) -> None:
        self._db = db
        self._account_repo = AccountRepository(db)
        self._contact_repo = ContactRepository(db)
        self._opp_repo = OpportunityRepository(db)

    async def create_account(
        self,
        *,
        name: str,
        industry: Optional[str] = None,
        website: Optional[str] = None,
        phone: Optional[str] = None,
        tier: str = AccountTier.SMB.value,
        annual_revenue: float = 0.0,
        billing_city: Optional[str] = None,
        billing_country: Optional[str] = None,
    ) -> Account:
        """Validate and create an account."""
        if not name or not name.strip():
            raise ValueError("Account name is required and cannot be empty.")

        clean_name = name.strip()
        existing = await self._account_repo.get_by_name(clean_name)
        if existing:
            raise ValueError(f"An account with name '{clean_name}' already exists (ID: {existing.id}).")

        valid_tiers = {t.value for t in AccountTier}
        if tier not in valid_tiers:
            raise ValueError(f"Invalid account tier '{tier}'. Must be one of {valid_tiers}.")

        if annual_revenue < 0:
            raise ValueError(f"Annual revenue cannot be negative, got {annual_revenue}.")

        account = Account(
            id="",
            name=clean_name,
            industry=industry.strip() if industry else None,
            website=website.strip() if website else None,
            phone=phone.strip() if phone else None,
            tier=tier,
            annual_revenue=float(annual_revenue),
            billing_city=billing_city.strip() if billing_city else None,
            billing_country=billing_country.strip() if billing_country else None,
            status=AccountStatus.ACTIVE.value,
        )
        return await self._account_repo.create(account)

    async def get_account(self, account_id: str) -> Optional[Account]:
        """Fetch account by ID."""
        return await self._account_repo.get_by_id(account_id)

    async def update_account(self, account_id: str, **updates: Any) -> Optional[Account]:
        """Validate and apply updates to an account."""
        existing = await self._account_repo.get_by_id(account_id)
        if not existing:
            raise ValueError(f"Account not found with ID '{account_id}'.")

        if "name" in updates and updates["name"]:
            clean_name = updates["name"].strip()
            if not clean_name:
                raise ValueError("Account name cannot be empty.")
            name_check = await self._account_repo.get_by_name(clean_name)
            if name_check and name_check.id != account_id:
                raise ValueError(f"An account with name '{clean_name}' already exists.")
            updates["name"] = clean_name

        if "tier" in updates and updates["tier"]:
            valid_tiers = {t.value for t in AccountTier}
            if updates["tier"] not in valid_tiers:
                raise ValueError(f"Invalid tier '{updates['tier']}'. Must be one of {valid_tiers}.")

        if "annual_revenue" in updates and updates["annual_revenue"] is not None:
            rev = float(updates["annual_revenue"])
            if rev < 0:
                raise ValueError("Annual revenue cannot be negative.")
            updates["annual_revenue"] = rev

        return await self._account_repo.update(account_id, updates)

    async def get_account_summary(self, account_id: str) -> dict[str, Any]:
        """Compile comprehensive metrics for an account."""
        account = await self._account_repo.get_by_id(account_id)
        if not account:
            raise ValueError(f"Account not found with ID '{account_id}'.")

        contacts = await self._contact_repo.list_by_account(account_id)
        opportunities = await self._opp_repo.list_by_account(account_id)

        total_pipeline = sum(opp.amount for opp in opportunities)
        won_opps = [opp for opp in opportunities if opp.stage == OpportunityStage.CLOSED_WON.value]
        won_revenue = sum(opp.amount for opp in won_opps)

        return {
            "account": account,
            "contact_count": len(contacts),
            "opportunity_count": len(opportunities),
            "total_pipeline_value": round(total_pipeline, 2),
            "won_opportunity_count": len(won_opps),
            "won_revenue": round(won_revenue, 2),
        }

    async def search_accounts(
        self,
        query: str,
        *,
        tier: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Account]:
        """Search accounts by text query."""
        return await self._account_repo.search(query, tier=tier, status=status, limit=limit, offset=offset)

    async def list_accounts(
        self,
        *,
        tier: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Account]:
        """List accounts."""
        return await self._account_repo.list(tier=tier, status=status, limit=limit, offset=offset)

    async def delete_account(self, account_id: str) -> bool:
        """Delete an account and its cascade dependents."""
        return await self._account_repo.delete(account_id)

