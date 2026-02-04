"""Payment-related Pydantic schemas."""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict

from src.models.payment import PaymentStatus


class PaymentCreate(BaseModel):
    """Schema for creating a payment."""

    tender_id: int
    client_id: int


class PaymentResponse(BaseModel):
    """Payment response schema."""

    id: int
    yookassa_id: str
    tender_id: int
    client_id: int
    amount: Decimal
    currency: str
    status: PaymentStatus
    confirmation_url: Optional[str] = None
    report_sent: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PaymentInitResponse(BaseModel):
    """Response when initiating a payment."""

    payment_id: int
    yookassa_id: str
    confirmation_url: str
    amount: Decimal
    currency: str


class PaymentStatusResponse(BaseModel):
    """Payment status check response."""

    yookassa_id: str
    status: PaymentStatus
    report_sent: bool
    tender_id: int
