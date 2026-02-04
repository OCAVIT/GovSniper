"""Payment service using YooKassa."""

import logging
import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from yookassa import Configuration, Payment as YooPayment

from src.config import settings
from src.models import Client, Payment, PaymentStatus, Tender, TenderStatus

from .ai_service import ai_service
from .email_service import email_service

# Use stub PDF generator for testing without WeasyPrint
try:
    from .pdf_generator import pdf_generator
except ImportError:
    from .pdf_generator_stub import pdf_generator
    logger.warning("Using PDF generator stub - install WeasyPrint for real PDFs")

logger = logging.getLogger(__name__)

# Configure YooKassa
Configuration.account_id = settings.yookassa_shop_id
Configuration.secret_key = settings.yookassa_secret_key


class PaymentService:
    """Service for handling payments via YooKassa."""

    def __init__(self):
        self.return_url = f"{settings.app_base_url}/payment/success"

    def get_price_for_tender(self, tender_price: Decimal | None) -> Decimal:
        """
        Get report price based on tender value (tiered pricing).

        Tiers:
        - < 1M RUB: tier1 (default 990 RUB)
        - 1M - 10M RUB: tier2 (default 1990 RUB)
        - > 10M RUB: tier3 (default 4990 RUB)
        """
        if tender_price is None:
            return Decimal(str(settings.report_price_tier1))

        price = float(tender_price)
        if price < 1_000_000:
            return Decimal(str(settings.report_price_tier1))
        elif price < 10_000_000:
            return Decimal(str(settings.report_price_tier2))
        else:
            return Decimal(str(settings.report_price_tier3))

    async def create_payment(
        self,
        tender: Tender,
        client: Client,
        db: AsyncSession,
    ) -> tuple[Payment, str]:
        """
        Create a YooKassa payment for tender report.

        Args:
            tender: Tender to create payment for
            client: Client making the payment
            db: Database session

        Returns:
            Tuple of (Payment entity, confirmation_url)
        """
        idempotency_key = str(uuid.uuid4())
        report_price = self.get_price_for_tender(tender.price)

        try:
            # Create payment in YooKassa
            yoo_payment = YooPayment.create(
                {
                    "amount": {
                        "value": str(report_price),
                        "currency": "RUB",
                    },
                    "confirmation": {
                        "type": "redirect",
                        "return_url": self.return_url,
                    },
                    "capture": True,
                    "description": f"Аудит тендера №{tender.external_id}",
                    "metadata": {
                        "tender_id": str(tender.id),
                        "client_id": str(client.id),
                        "client_email": client.email,
                    },
                },
                idempotency_key,
            )

            # Save payment to database
            payment = Payment(
                yookassa_id=yoo_payment.id,
                tender_id=tender.id,
                client_id=client.id,
                amount=report_price,
                currency="RUB",
                status=PaymentStatus(yoo_payment.status),
                confirmation_url=yoo_payment.confirmation.confirmation_url,
            )

            db.add(payment)
            await db.commit()
            await db.refresh(payment)

            logger.info(
                f"Payment created: {payment.yookassa_id} for tender {tender.id}, "
                f"client {client.id}"
            )

            return payment, yoo_payment.confirmation.confirmation_url

        except Exception as e:
            logger.error(f"Error creating payment: {e}")
            raise

    async def handle_webhook(
        self,
        event: str,
        payment_data: dict,
        db: AsyncSession,
    ) -> bool:
        """
        Handle YooKassa webhook event.

        Args:
            event: Webhook event type
            payment_data: Payment data from webhook
            db: Database session

        Returns:
            True if handled successfully
        """
        yookassa_id = payment_data.get("id")
        status = payment_data.get("status")

        logger.info(f"Webhook received: event={event}, payment_id={yookassa_id}, status={status}")

        # Find payment in database
        result = await db.execute(
            select(Payment).where(Payment.yookassa_id == yookassa_id)
        )
        payment = result.scalar_one_or_none()

        if not payment:
            logger.warning(f"Payment not found: {yookassa_id}")
            return False

        # Update payment status
        payment.status = PaymentStatus(status)
        await db.commit()

        # Handle successful payment
        if event == "payment.succeeded" and status == "succeeded":
            await self._process_successful_payment(payment, db)

        return True

    async def _process_successful_payment(
        self,
        payment: Payment,
        db: AsyncSession,
    ) -> None:
        """
        Process successful payment: generate report and send to client.

        Args:
            payment: Payment entity
            db: Database session
        """
        logger.info(f"Processing successful payment: {payment.yookassa_id}")

        try:
            # Load related entities
            result = await db.execute(
                select(Tender).where(Tender.id == payment.tender_id)
            )
            tender = result.scalar_one()

            result = await db.execute(
                select(Client).where(Client.id == payment.client_id)
            )
            client = result.scalar_one()

            # 1. Deep AI analysis
            logger.info(f"Starting deep analysis for tender {tender.id}")
            analysis = await ai_service.analyze_deep_audit(tender.raw_text or "")

            # Save deep analysis
            tender.deep_analysis = str(analysis)
            await db.commit()

            # 2. Generate PDF report
            logger.info(f"Generating PDF report for tender {tender.id}")
            pdf_content = await pdf_generator.generate_deep_audit_report(
                tender=tender,
                analysis=analysis,
            )

            # 3. Send email with PDF
            logger.info(f"Sending report to {client.email}")
            email_id = await email_service.send_report_email(
                to_email=client.email,
                tender_title=tender.title,
                tender_id=tender.id,
                pdf_content=pdf_content,
            )

            if email_id:
                payment.report_sent = True
                await db.commit()

            # 4. Cleanup: clear raw text (no S3 - text only in DB)
            logger.info(f"Cleaning up data for tender {tender.id}")
            tender.raw_text = None
            tender.status = TenderStatus.SOLD

            await db.commit()
            logger.info(f"Payment {payment.yookassa_id} processed successfully")

        except Exception as e:
            logger.error(f"Error processing payment {payment.yookassa_id}: {e}")
            raise

    def get_payment_url(self, tender_id: int, client_id: int) -> str:
        """Generate payment initiation URL."""
        return f"{settings.app_base_url}/api/payments/create?tender_id={tender_id}&client_id={client_id}"


# Singleton instance
payment_service = PaymentService()
