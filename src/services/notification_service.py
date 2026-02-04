"""Notification service for sending tender alerts to subscribers."""

import logging

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.models import (
    Client,
    Notification,
    NotificationStatus,
    NotificationType,
    Tender,
    TenderStatus,
)

from .email_service import email_service
from .payment_service import payment_service

logger = logging.getLogger(__name__)


class NotificationService:
    """Service for matching tenders to subscribers and sending notifications."""

    async def find_matching_clients(
        self,
        tender: Tender,
        db: AsyncSession,
    ) -> list[Client]:
        """
        Find clients whose keywords match the tender.

        Args:
            tender: Tender to match
            db: Database session

        Returns:
            List of matching clients
        """
        # Get all active clients
        result = await db.execute(
            select(Client).where(Client.is_active == True)  # noqa: E712
        )
        clients = result.scalars().all()

        matching = []
        for client in clients:
            if client.matches_tender(tender.title, float(tender.price) if tender.price else None):
                # Check if we already notified this client about this tender
                existing = await db.execute(
                    select(Notification).where(
                        and_(
                            Notification.tender_id == tender.id,
                            Notification.client_id == client.id,
                            Notification.notification_type == NotificationType.TEASER,
                        )
                    )
                )
                if not existing.scalar_one_or_none():
                    matching.append(client)

        return matching

    async def send_teaser_notifications(
        self,
        tender: Tender,
        db: AsyncSession,
    ) -> int:
        """
        Send teaser notifications to matching clients.

        Args:
            tender: Tender to notify about
            db: Database session

        Returns:
            Number of notifications sent
        """
        # Find matching clients
        clients = await self.find_matching_clients(tender, db)

        if not clients:
            logger.debug(f"No matching clients for tender {tender.id}")
            return 0

        sent_count = 0

        for client in clients:
            try:
                # Generate payment URL
                payment_url = payment_service.get_payment_url(tender.id, client.id)

                # Create notification record
                notification = Notification(
                    tender_id=tender.id,
                    client_id=client.id,
                    notification_type=NotificationType.TEASER,
                    status=NotificationStatus.PENDING,
                )
                db.add(notification)
                await db.flush()

                # Send email
                resend_id = await email_service.send_teaser_email(
                    to_email=client.email,
                    tender_title=tender.title,
                    tender_id=tender.id,
                    risk_score=tender.risk_score or 50,
                    margin_estimate=tender.margin_estimate or "не определена",
                    description=tender.teaser_description or "Описание недоступно",
                    payment_url=payment_url,
                )

                if resend_id:
                    notification.status = NotificationStatus.SENT
                    notification.resend_id = resend_id
                    sent_count += 1
                    logger.info(
                        f"Teaser sent to {client.email} for tender {tender.id}"
                    )
                else:
                    notification.status = NotificationStatus.FAILED
                    notification.error_message = "Failed to send email"

                await db.commit()

            except Exception as e:
                logger.error(
                    f"Error sending notification to {client.email}: {e}"
                )
                notification.status = NotificationStatus.FAILED
                notification.error_message = str(e)[:1000]
                await db.commit()

        return sent_count

    async def process_analyzed_tenders(self, db: AsyncSession, limit: int = 10) -> int:
        """
        Send notifications for analyzed tenders.

        Args:
            db: Database session
            limit: Maximum number of tenders to process

        Returns:
            Number of tenders processed
        """
        # Get ANALYZED tenders
        result = await db.execute(
            select(Tender)
            .where(Tender.status == TenderStatus.ANALYZED)
            .order_by(Tender.created_at)
            .limit(limit)
        )
        tenders = result.scalars().all()

        total_sent = 0

        for tender in tenders:
            try:
                sent = await self.send_teaser_notifications(tender, db)
                total_sent += sent

                # Update status to NOTIFIED
                tender.status = TenderStatus.NOTIFIED
                await db.commit()

            except Exception as e:
                logger.error(f"Error processing tender {tender.id}: {e}")

        return total_sent


# Singleton instance
notification_service = NotificationService()
