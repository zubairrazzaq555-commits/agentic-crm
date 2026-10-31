"""Agentic CRM — Sales Domain Core Models & Database Schemas.

Defines dataclasses, enums, and SQLAlchemy Core table schemas for:
- Leads
- Accounts
- Contacts
- Opportunities
- Deals
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping, Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
)

from src.database.connection import metadata

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class LeadStatus(str, Enum):
    NEW = "new"
    CONTACTED = "contacted"
    QUALIFIED = "qualified"
    UNQUALIFIED = "unqualified"
    CONVERTED = "converted"


class AccountTier(str, Enum):
    ENTERPRISE = "enterprise"
    MID_MARKET = "mid_market"
    SMB = "smb"


class AccountStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class OpportunityStage(str, Enum):
    PROSPECTING = "prospecting"
    QUALIFICATION = "qualification"
    PROPOSAL = "proposal"
    NEGOTIATION = "negotiation"
    CLOSED_WON = "closed_won"
    CLOSED_LOST = "closed_lost"


class DealStatus(str, Enum):
    DRAFT = "draft"
    SENT = "sent"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


STAGE_PROBABILITIES: dict[str, int] = {
    OpportunityStage.PROSPECTING.value: 10,
    OpportunityStage.QUALIFICATION.value: 25,
    OpportunityStage.PROPOSAL.value: 50,
    OpportunityStage.NEGOTIATION.value: 75,
    OpportunityStage.CLOSED_WON.value: 100,
    OpportunityStage.CLOSED_LOST.value: 0,
}


def _utcnow() -> datetime:
    """Return timezone-aware current UTC datetime."""
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# SQLAlchemy Core Table Definitions
# ---------------------------------------------------------------------------

leads_table = metadata.tables.get("leads")
if leads_table is None:
    leads_table = Table(
        "leads",
        metadata,
        Column("id", String(36), primary_key=True),
        Column("first_name", String(100), nullable=False),
        Column("last_name", String(100), nullable=False),
        Column("email", String(255), nullable=False, index=True),
        Column("phone", String(50), nullable=True),
        Column("company", String(200), nullable=False),
        Column("title", String(100), nullable=True),
        Column("status", String(50), nullable=False, default=LeadStatus.NEW.value),
        Column("source", String(100), nullable=True),
        Column("score", Integer, nullable=False, default=0),
        Column("notes", Text, nullable=True),
        Column("created_at", DateTime, nullable=False, default=_utcnow),
        Column("updated_at", DateTime, nullable=False, default=_utcnow),
    )

accounts_table = metadata.tables.get("accounts")
if accounts_table is None:
    accounts_table = Table(
        "accounts",
        metadata,
        Column("id", String(36), primary_key=True),
        Column("name", String(200), nullable=False, unique=True, index=True),
        Column("industry", String(100), nullable=True),
        Column("website", String(255), nullable=True),
        Column("phone", String(50), nullable=True),
        Column("tier", String(50), nullable=False, default=AccountTier.SMB.value),
        Column("annual_revenue", Float, nullable=False, default=0.0),
        Column("billing_city", String(100), nullable=True),
        Column("billing_country", String(100), nullable=True),
        Column("status", String(50), nullable=False, default=AccountStatus.ACTIVE.value),
        Column("created_at", DateTime, nullable=False, default=_utcnow),
        Column("updated_at", DateTime, nullable=False, default=_utcnow),
    )

contacts_table = metadata.tables.get("contacts")
if contacts_table is None:
    contacts_table = Table(
        "contacts",
        metadata,
        Column("id", String(36), primary_key=True),
        Column(
            "account_id",
            String(36),
            ForeignKey("accounts.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        Column("first_name", String(100), nullable=False),
        Column("last_name", String(100), nullable=False),
        Column("email", String(255), nullable=False, index=True),
        Column("phone", String(50), nullable=True),
        Column("title", String(100), nullable=True),
        Column("department", String(100), nullable=True),
        Column("is_primary", Boolean, nullable=False, default=False),
        Column("created_at", DateTime, nullable=False, default=_utcnow),
        Column("updated_at", DateTime, nullable=False, default=_utcnow),
    )

opportunities_table = metadata.tables.get("opportunities")
if opportunities_table is None:
    opportunities_table = Table(
        "opportunities",
        metadata,
        Column("id", String(36), primary_key=True),
        Column(
            "account_id",
            String(36),
            ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        Column(
            "primary_contact_id",
            String(36),
            ForeignKey("contacts.id", ondelete="SET NULL"),
            nullable=True,
        ),
        Column("name", String(200), nullable=False),
        Column(
            "stage",
            String(50),
            nullable=False,
            default=OpportunityStage.PROSPECTING.value,
        ),
        Column("amount", Float, nullable=False, default=0.0),
        Column("probability", Integer, nullable=False, default=10),
        Column("close_date", DateTime, nullable=True),
        Column("created_at", DateTime, nullable=False, default=_utcnow),
        Column("updated_at", DateTime, nullable=False, default=_utcnow),
    )

deals_table = metadata.tables.get("deals")
if deals_table is None:
    deals_table = Table(
        "deals",
        metadata,
        Column("id", String(36), primary_key=True),
        Column(
            "opportunity_id",
            String(36),
            ForeignKey("opportunities.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        Column("name", String(200), nullable=False),
        Column("deal_value", Float, nullable=False, default=0.0),
        Column("discount_percentage", Float, nullable=False, default=0.0),
        Column("final_amount", Float, nullable=False, default=0.0),
        Column("status", String(50), nullable=False, default=DealStatus.DRAFT.value),
        Column("payment_terms", String(100), nullable=True),
        Column("contract_start_date", DateTime, nullable=True),
        Column("contract_end_date", DateTime, nullable=True),
        Column("closed_at", DateTime, nullable=True),
        Column("created_at", DateTime, nullable=False, default=_utcnow),
        Column("updated_at", DateTime, nullable=False, default=_utcnow),
    )


# ---------------------------------------------------------------------------
# Python Dataclass Models
# ---------------------------------------------------------------------------


@dataclass
class Lead:
    id: str
    first_name: str
    last_name: str
    company: str
    email: str
    phone: Optional[str] = None
    title: Optional[str] = None
    status: str = LeadStatus.NEW.value
    source: Optional[str] = None
    score: int = 0
    notes: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_row(cls, row: Mapping[str, Any]) -> Lead:
        return cls(
            id=row["id"],
            first_name=row["first_name"],
            last_name=row["last_name"],
            company=row["company"],
            email=row["email"],
            phone=row.get("phone"),
            title=row.get("title"),
            status=row.get("status", LeadStatus.NEW.value),
            source=row.get("source"),
            score=row.get("score", 0),
            notes=row.get("notes"),
            created_at=row.get("created_at"),
            updated_at=row.get("updated_at"),
        )


@dataclass
class Account:
    id: str
    name: str
    industry: Optional[str] = None
    website: Optional[str] = None
    phone: Optional[str] = None
    tier: str = AccountTier.SMB.value
    annual_revenue: float = 0.0
    billing_city: Optional[str] = None
    billing_country: Optional[str] = None
    status: str = AccountStatus.ACTIVE.value
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_row(cls, row: Mapping[str, Any]) -> Account:
        return cls(
            id=row["id"],
            name=row["name"],
            industry=row.get("industry"),
            website=row.get("website"),
            phone=row.get("phone"),
            tier=row.get("tier", AccountTier.SMB.value),
            annual_revenue=float(row.get("annual_revenue") or 0.0),
            billing_city=row.get("billing_city"),
            billing_country=row.get("billing_country"),
            status=row.get("status", AccountStatus.ACTIVE.value),
            created_at=row.get("created_at"),
            updated_at=row.get("updated_at"),
        )


@dataclass
class Contact:
    id: str
    first_name: str
    last_name: str
    email: str
    account_id: Optional[str] = None
    phone: Optional[str] = None
    title: Optional[str] = None
    department: Optional[str] = None
    is_primary: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_row(cls, row: Mapping[str, Any]) -> Contact:
        return cls(
            id=row["id"],
            first_name=row["first_name"],
            last_name=row["last_name"],
            email=row["email"],
            account_id=row.get("account_id"),
            phone=row.get("phone"),
            title=row.get("title"),
            department=row.get("department"),
            is_primary=bool(row.get("is_primary", False)),
            created_at=row.get("created_at"),
            updated_at=row.get("updated_at"),
        )


@dataclass
class Opportunity:
    id: str
    account_id: str
    name: str
    stage: str = OpportunityStage.PROSPECTING.value
    amount: float = 0.0
    probability: int = 10
    primary_contact_id: Optional[str] = None
    close_date: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_row(cls, row: Mapping[str, Any]) -> Opportunity:
        return cls(
            id=row["id"],
            account_id=row["account_id"],
            name=row["name"],
            stage=row.get("stage", OpportunityStage.PROSPECTING.value),
            amount=float(row.get("amount") or 0.0),
            probability=int(row.get("probability", 10)),
            primary_contact_id=row.get("primary_contact_id"),
            close_date=row.get("close_date"),
            created_at=row.get("created_at"),
            updated_at=row.get("updated_at"),
        )


@dataclass
class Deal:
    id: str
    opportunity_id: str
    name: str
    deal_value: float = 0.0
    discount_percentage: float = 0.0
    final_amount: float = 0.0
    status: str = DealStatus.DRAFT.value
    payment_terms: Optional[str] = None
    contract_start_date: Optional[datetime] = None
    contract_end_date: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_row(cls, row: Mapping[str, Any]) -> Deal:
        return cls(
            id=row["id"],
            opportunity_id=row["opportunity_id"],
            name=row["name"],
            deal_value=float(row.get("deal_value") or 0.0),
            discount_percentage=float(row.get("discount_percentage") or 0.0),
            final_amount=float(row.get("final_amount") or 0.0),
            status=row.get("status", DealStatus.DRAFT.value),
            payment_terms=row.get("payment_terms"),
            contract_start_date=row.get("contract_start_date"),
            contract_end_date=row.get("contract_end_date"),
            closed_at=row.get("closed_at"),
            created_at=row.get("created_at"),
            updated_at=row.get("updated_at"),
        )

