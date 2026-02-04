"""Webhook endpoints for YooKassa payments."""

import hashlib
import hmac
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.db import get_db
from src.services.payment_service import payment_service

logger = logging.getLogger(__name__)

router = APIRouter()


class YooKassaWebhookPayload(BaseModel):
    """YooKassa webhook payload schema."""

    type: str
    event: str
    object: dict[str, Any]


def verify_yookassa_signature(payload: bytes, signature: str | None) -> bool:
    """
    Verify YooKassa webhook signature.

    YooKassa sends signature in HTTP Basic Auth format.
    For production, implement proper signature verification.
    """
    if not settings.is_production:
        # Skip verification in development
        return True

    if not signature:
        return False

    # YooKassa uses shop_id:secret_key for basic auth
    # In production, verify the IP address is from YooKassa
    # IP ranges: 185.71.76.0/27, 185.71.77.0/27, 77.75.153.0/25, etc.

    # For now, basic check - in production add IP whitelist
    return True


@router.post("/yookassa")
async def yookassa_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Handle YooKassa payment webhooks.

    Events:
    - payment.succeeded: Payment completed successfully
    - payment.canceled: Payment was canceled
    - payment.waiting_for_capture: Payment is waiting for capture (not used with auto-capture)
    - refund.succeeded: Refund completed
    """
    # Get raw body for signature verification
    body = await request.body()

    # Verify signature (in production)
    auth_header = request.headers.get("Authorization")
    if not verify_yookassa_signature(body, auth_header):
        logger.warning("Invalid YooKassa signature")
        raise HTTPException(status_code=401, detail="Invalid signature")

    # Parse payload
    try:
        payload = await request.json()
    except Exception as e:
        logger.error(f"Error parsing webhook payload: {e}")
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    event = payload.get("event")
    payment_object = payload.get("object", {})

    logger.info(
        f"YooKassa webhook received: event={event}, "
        f"payment_id={payment_object.get('id')}"
    )

    # Handle different events
    if event == "payment.succeeded":
        try:
            await payment_service.handle_webhook(
                event=event,
                payment_data=payment_object,
                db=db,
            )
        except Exception as e:
            logger.error(f"Error processing payment webhook: {e}")
            # Return 200 to prevent YooKassa from retrying
            # Log the error for manual investigation
            return {"status": "error", "message": str(e)}

    elif event == "payment.canceled":
        logger.info(f"Payment canceled: {payment_object.get('id')}")
        await payment_service.handle_webhook(
            event=event,
            payment_data=payment_object,
            db=db,
        )

    elif event == "refund.succeeded":
        logger.info(f"Refund succeeded: {payment_object.get('id')}")
        # Handle refund if needed

    else:
        logger.info(f"Unhandled webhook event: {event}")

    return {"status": "ok"}


@router.post("/yookassa/test")
async def test_webhook(
    payload: YooKassaWebhookPayload,
    db: AsyncSession = Depends(get_db),
):
    """
    Test endpoint for simulating YooKassa webhooks.
    Only available in non-production environments.
    """
    if settings.is_production:
        raise HTTPException(status_code=404, detail="Not found")

    logger.info(f"Test webhook: {payload.event}")

    await payment_service.handle_webhook(
        event=payload.event,
        payment_data=payload.object,
        db=db,
    )

    return {"status": "ok", "message": "Test webhook processed"}
