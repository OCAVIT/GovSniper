"""Cleanup job for removing stale tender data."""

import logging
from datetime import datetime, timedelta

from sqlalchemy import select

from src.config import settings
from src.db import get_db_context
from src.models import Tender, TenderStatus

logger = logging.getLogger(__name__)


async def cleanup_stale_data_job():
    """
    Job: Clean up stale tender data (older than retention period without sale).
    Runs every 6 hours.

    Rules:
    - Tenders with status ANALYZED or NOTIFIED
    - Older than DATA_RETENTION_DAYS (default 3 days)
    - Have raw_text

    Actions:
    - Clear raw_text field
    - Keep basic tender info (title, price, status) for statistics
    """
    logger.info("Starting data cleanup job")

    cutoff_date = datetime.utcnow() - timedelta(days=settings.data_retention_days)
    cleaned_count = 0

    try:
        async with get_db_context() as db:
            # Find stale tenders with raw_text
            result = await db.execute(
                select(Tender).where(
                    Tender.status.in_([TenderStatus.ANALYZED, TenderStatus.NOTIFIED]),
                    Tender.created_at < cutoff_date,
                    Tender.raw_text.isnot(None),
                )
            )
            tenders = result.scalars().all()

            for tender in tenders:
                try:
                    # Clear heavy fields
                    tender.raw_text = None
                    tender.deep_analysis = None
                    cleaned_count += 1

                except Exception as e:
                    logger.error(f"Error cleaning tender {tender.id}: {e}")

            await db.commit()

        logger.info(f"Cleanup completed: {cleaned_count} tenders cleaned")

    except Exception as e:
        logger.error(f"Cleanup job failed: {e}")


async def vacuum_database():
    """
    Optional: Run database maintenance tasks.
    Should be run during low-traffic periods.
    """
    logger.info("Starting database vacuum")

    try:
        async with get_db_context() as db:
            # PostgreSQL VACUUM ANALYZE for better performance
            # Note: This requires appropriate permissions
            # await db.execute(text("VACUUM ANALYZE tenders"))
            pass
    except Exception as e:
        logger.error(f"Database vacuum failed: {e}")
