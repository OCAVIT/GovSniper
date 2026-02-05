"""Tender model."""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Index, Numeric, String, Text
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import BaseModel

if TYPE_CHECKING:
    from .notification import Notification
    from .participant import TenderParticipant
    from .payment import Payment


class TenderStatus(str, Enum):
    """Tender processing status."""

    NEW = "NEW"  # Just scraped from RSS
    DOWNLOADED = "DOWNLOADED"  # Documents downloaded and text extracted
    ANALYZED = "ANALYZED"  # AI teaser analysis completed
    NOTIFIED = "NOTIFIED"  # Teaser emails sent to subscribers
    SOLD = "SOLD"  # Payment received, deep analysis sent


class Tender(BaseModel):
    """
    Tender entity representing a government procurement.

    Lifecycle:
    1. NEW -> Scraped from RSS, basic info stored
    2. DOWNLOADED -> Documents fetched, text extracted
    3. ANALYZED -> AI teaser generated (risk, margin, summary)
    4. NOTIFIED -> Teaser emails sent to matching subscribers
    5. SOLD -> Payment received, deep analysis PDF sent
    """

    __tablename__ = "tenders"

    # Unique identifier from zakupki.gov.ru
    external_id: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        index=True,
        nullable=False,
    )

    # Basic info from RSS
    title: Mapped[str] = mapped_column(String(1000), nullable=False)
    url: Mapped[str] = mapped_column(String(2000), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=True)
    customer_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Processing status
    status: Mapped[TenderStatus] = mapped_column(
        SQLEnum(
            TenderStatus,
            native_enum=True,
            name="tenderstatus",
            create_type=False,
        ),
        default=TenderStatus.NEW,
        index=True,
        nullable=False,
    )

    # Document content (extracted text, cleared after sale or 3-day retention)
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    # AI Teaser Analysis (quick assessment)
    risk_score: Mapped[int | None] = mapped_column(nullable=True)  # 0-100
    margin_estimate: Mapped[str | None] = mapped_column(String(100), nullable=True)
    teaser_description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # AI Deep Analysis (after payment)
    deep_analysis: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    payments: Mapped[list["Payment"]] = relationship(
        "Payment",
        back_populates="tender",
        cascade="all, delete-orphan",
    )
    notifications: Mapped[list["Notification"]] = relationship(
        "Notification",
        back_populates="tender",
        cascade="all, delete-orphan",
    )
    participants: Mapped[list["TenderParticipant"]] = relationship(
        "TenderParticipant",
        back_populates="tender",
        cascade="all, delete-orphan",
    )

    # Indexes for common queries
    __table_args__ = (
        Index("ix_tenders_status_created", "status", "created_at"),
        Index("ix_tenders_price", "price"),
    )

    def __repr__(self) -> str:
        return f"<Tender(id={self.id}, external_id={self.external_id}, status={self.status})>"

    @property
    def is_stale(self) -> bool:
        """Check if tender data should be cleaned up (older than 3 days without sale)."""
        from datetime import timedelta

        from src.config import settings

        if self.status == TenderStatus.SOLD:
            return False
        if self.created_at is None:
            return False
        cutoff = datetime.utcnow() - timedelta(days=settings.data_retention_days)
        return self.created_at < cutoff

    @property
    def has_heavy_data(self) -> bool:
        """Check if tender has heavy data that should be cleaned."""
        return bool(self.raw_text)
