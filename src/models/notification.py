"""Notification model."""

from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import BaseModel

if TYPE_CHECKING:
    from .client import Client
    from .tender import Tender


class NotificationType(str, Enum):
    """Type of notification."""

    TEASER = "teaser"  # Initial teaser email with payment link
    REPORT = "report"  # Full report delivery after payment


class NotificationStatus(str, Enum):
    """Notification delivery status."""

    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    BOUNCED = "bounced"


class Notification(BaseModel):
    """
    Notification entity for tracking email delivery.

    Tracks both teaser notifications and report delivery emails.
    """

    __tablename__ = "notifications"

    # Relations
    tender_id: Mapped[int] = mapped_column(
        ForeignKey("tenders.id", ondelete="CASCADE"),
        nullable=False,
    )
    client_id: Mapped[int] = mapped_column(
        ForeignKey("clients.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Notification details
    notification_type: Mapped[NotificationType] = mapped_column(
        SQLEnum(NotificationType, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    status: Mapped[NotificationStatus] = mapped_column(
        SQLEnum(NotificationStatus, values_callable=lambda x: [e.value for e in x]),
        default=NotificationStatus.PENDING,
        nullable=False,
    )

    # Email tracking
    resend_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    # Relationships
    tender: Mapped["Tender"] = relationship("Tender", back_populates="notifications")
    client: Mapped["Client"] = relationship("Client", back_populates="notifications")

    # Indexes
    __table_args__ = (
        Index("ix_notifications_tender_client", "tender_id", "client_id"),
        Index("ix_notifications_type_status", "notification_type", "status"),
    )

    def __repr__(self) -> str:
        return (
            f"<Notification(id={self.id}, type={self.notification_type}, "
            f"status={self.status})>"
        )
