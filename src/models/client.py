"""Client (subscriber) model."""

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, String, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import BaseModel

if TYPE_CHECKING:
    from .notification import Notification
    from .payment import Payment


class Client(BaseModel):
    """
    Client/Subscriber entity.

    Clients subscribe with keywords to receive teaser notifications
    about matching tenders.
    """

    __tablename__ = "clients"

    # Contact info
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
    )
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    company: Mapped[str | None] = mapped_column(String(500), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Subscription settings
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    keywords: Mapped[list[str]] = mapped_column(
        ARRAY(String(100)),
        default=list,
        nullable=False,
    )

    # Additional filters (optional)
    min_price: Mapped[int | None] = mapped_column(nullable=True)
    max_price: Mapped[int | None] = mapped_column(nullable=True)
    regions: Mapped[list[str] | None] = mapped_column(ARRAY(String(100)), nullable=True)

    # Notes (for admin)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Lead source tracking (for auto-generated clients from losers)
    source: Mapped[str | None] = mapped_column(
        String(50), nullable=True, index=True
    )  # "manual", "loser", "website"
    source_inn: Mapped[str | None] = mapped_column(
        String(12), nullable=True, index=True
    )  # INN of the source company
    source_tender_id: Mapped[int | None] = mapped_column(nullable=True)  # Tender they lost

    # Relationships
    payments: Mapped[list["Payment"]] = relationship(
        "Payment",
        back_populates="client",
        cascade="all, delete-orphan",
    )
    notifications: Mapped[list["Notification"]] = relationship(
        "Notification",
        back_populates="client",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Client(id={self.id}, email={self.email}, active={self.is_active})>"

    def matches_tender(self, tender_title: str, tender_price: float | None = None) -> bool:
        """
        Check if tender matches client's subscription criteria.

        Args:
            tender_title: Tender title to match against keywords
            tender_price: Tender price (optional) to check against filters

        Returns:
            True if tender matches client's criteria
        """
        if not self.is_active:
            return False

        # Check keywords (case-insensitive)
        title_lower = tender_title.lower()
        keyword_match = any(kw.lower() in title_lower for kw in self.keywords)

        if not keyword_match:
            return False

        # Check price filters if set
        if tender_price is not None:
            if self.min_price and tender_price < self.min_price:
                return False
            if self.max_price and tender_price > self.max_price:
                return False

        return True
