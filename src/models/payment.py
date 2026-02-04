"""Payment model."""

from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Numeric, String
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import BaseModel

if TYPE_CHECKING:
    from .client import Client
    from .tender import Tender


class PaymentStatus(str, Enum):
    """Payment status from YooKassa."""

    PENDING = "pending"
    WAITING_FOR_CAPTURE = "waiting_for_capture"
    SUCCEEDED = "succeeded"
    CANCELED = "canceled"
    REFUNDED = "refunded"


class Payment(BaseModel):
    """
    Payment entity for tender reports.

    Tracks payments made through YooKassa for deep analysis reports.
    """

    __tablename__ = "payments"

    # YooKassa payment ID
    yookassa_id: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        index=True,
        nullable=False,
    )

    # Relations
    tender_id: Mapped[int] = mapped_column(
        ForeignKey("tenders.id", ondelete="CASCADE"),
        nullable=False,
    )
    client_id: Mapped[int] = mapped_column(
        ForeignKey("clients.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Payment details
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="RUB", nullable=False)
    status: Mapped[PaymentStatus] = mapped_column(
        SQLEnum(
            PaymentStatus,
            values_callable=lambda x: [e.value for e in x],
            native_enum=True,
            name="paymentstatus",
            create_type=False,
        ),
        default=PaymentStatus.PENDING,
        nullable=False,
    )

    # Confirmation URL for redirect
    confirmation_url: Mapped[str | None] = mapped_column(String(2000), nullable=True)

    # Report delivery status
    report_sent: Mapped[bool] = mapped_column(default=False, nullable=False)

    # Relationships
    tender: Mapped["Tender"] = relationship("Tender", back_populates="payments")
    client: Mapped["Client"] = relationship("Client", back_populates="payments")

    def __repr__(self) -> str:
        return f"<Payment(id={self.id}, yookassa_id={self.yookassa_id}, status={self.status})>"

    @property
    def is_completed(self) -> bool:
        """Check if payment is successfully completed."""
        return self.status == PaymentStatus.SUCCEEDED
