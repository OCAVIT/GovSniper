"""Tender participant model for tracking bidders."""

from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Index, Numeric, String, Text
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import BaseModel

if TYPE_CHECKING:
    from .tender import Tender


class ParticipantResult(str, Enum):
    """Result of participant's bid."""

    WINNER = "WINNER"
    LOSER = "LOSER"
    REJECTED = "REJECTED"  # Application rejected
    WITHDRAWN = "WITHDRAWN"  # Participant withdrew


class TenderParticipant(BaseModel):
    """
    Tender participant entity.

    Represents a company that participated in a tender.
    Used for lead generation from losers.
    """

    __tablename__ = "tender_participants"

    # Link to tender
    tender_id: Mapped[int] = mapped_column(
        ForeignKey("tenders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Company info (from protocol)
    company_name: Mapped[str] = mapped_column(String(500), nullable=False)
    inn: Mapped[str | None] = mapped_column(String(12), nullable=True, index=True)
    kpp: Mapped[str | None] = mapped_column(String(9), nullable=True)

    # Bid info
    bid_amount: Mapped[float | None] = mapped_column(Numeric(15, 2), nullable=True)

    # Result
    result: Mapped[ParticipantResult] = mapped_column(
        SQLEnum(
            ParticipantResult,
            native_enum=True,
            name="participantresult",
            create_type=False,
        ),
        nullable=False,
    )

    # Contact info (from DaData/EGRUL)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Processing flags
    contacts_fetched: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    client_created: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    email_sent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationship
    tender: Mapped["Tender"] = relationship("Tender", back_populates="participants")

    # Indexes
    __table_args__ = (
        Index("ix_participants_inn_result", "inn", "result"),
        Index("ix_participants_contacts_fetched", "contacts_fetched"),
        Index("ix_participants_client_created", "client_created"),
    )

    def __repr__(self) -> str:
        return f"<TenderParticipant(id={self.id}, inn={self.inn}, result={self.result})>"
