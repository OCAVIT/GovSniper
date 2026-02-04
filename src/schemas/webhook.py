"""Webhook-related Pydantic schemas."""

from typing import Any, Optional

from pydantic import BaseModel


class YooKassaAmount(BaseModel):
    """YooKassa amount object."""

    value: str
    currency: str


class YooKassaMetadata(BaseModel):
    """YooKassa payment metadata."""

    tender_id: Optional[str] = None
    client_id: Optional[str] = None
    client_email: Optional[str] = None


class YooKassaPaymentObject(BaseModel):
    """YooKassa payment object in webhook."""

    id: str
    status: str
    amount: YooKassaAmount
    description: Optional[str] = None
    metadata: Optional[YooKassaMetadata] = None
    paid: Optional[bool] = None
    captured_at: Optional[str] = None
    created_at: Optional[str] = None


class YooKassaEvent(BaseModel):
    """YooKassa webhook event."""

    type: str
    event: str
    object: YooKassaPaymentObject


class YooKassaRefundObject(BaseModel):
    """YooKassa refund object in webhook."""

    id: str
    status: str
    amount: YooKassaAmount
    payment_id: str
    created_at: Optional[str] = None


class YooKassaRefundEvent(BaseModel):
    """YooKassa refund webhook event."""

    type: str
    event: str
    object: YooKassaRefundObject
