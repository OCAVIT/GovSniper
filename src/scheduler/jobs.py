"""Scheduled jobs for tender processing pipeline."""

import logging

from sqlalchemy import select, func

from src.db import get_db_context
from src.models import Tender, TenderStatus
from src.scheduler.job_stats import job_stats
from src.services.ai_service import ai_service
from src.services.document_service import document_service
from src.services.notification_service import notification_service
from src.services.scraper_service import scraper_service

logger = logging.getLogger(__name__)

# Register jobs for stats tracking
job_stats.register_job("scrape_rss", "Scrape RSS Feed")
job_stats.register_job("download_documents", "Download Documents")
job_stats.register_job("analyze_tenders", "Analyze Tenders")
job_stats.register_job("send_notifications", "Send Notifications")
job_stats.register_job("cleanup_stale_data", "Cleanup Stale Data")


async def scrape_rss_job():
    """
    Job: Scrape RSS feed for new tenders.
    Runs every 15 minutes.
    """
    logger.info("Starting RSS scrape job")
    job_stats.start_run("scrape_rss")
    try:
        async with get_db_context() as db:
            new_count = await scraper_service.process_feed(db)
            logger.info(f"RSS scrape completed: {new_count} new tenders")
            job_stats.finish_run("scrape_rss", processed=new_count)
    except Exception as e:
        logger.error(f"RSS scrape job failed: {e}")
        job_stats.finish_run("scrape_rss", error=str(e))


async def download_documents_job():
    """
    Job: Download documents for NEW tenders.
    Runs every 3 minutes.
    Increased limit to process queue faster.
    """
    logger.info("Starting document download job")
    job_stats.start_run("download_documents")
    try:
        async with get_db_context() as db:
            # Increased limit from 5 to 20 to process queue faster
            processed = await document_service.process_new_tenders(db, limit=20)
            logger.info(f"Document download completed: {processed} tenders processed")
            job_stats.finish_run("download_documents", processed=processed)
    except Exception as e:
        logger.error(f"Document download job failed: {e}")
        job_stats.finish_run("download_documents", error=str(e))


async def analyze_tenders_job():
    """
    Job: AI teaser analysis for DOWNLOADED tenders.
    Runs every 5 minutes.
    """
    logger.info("Starting tender analysis job")
    job_stats.start_run("analyze_tenders")
    try:
        async with get_db_context() as db:
            # Get DOWNLOADED tenders
            result = await db.execute(
                select(Tender)
                .where(Tender.status == TenderStatus.DOWNLOADED)
                .order_by(Tender.created_at)
                .limit(10)
            )
            tenders = result.scalars().all()

            analyzed = 0
            for tender in tenders:
                try:
                    # Skip if no text available
                    if not tender.raw_text:
                        logger.warning(f"Tender {tender.id} has no text, skipping analysis")
                        tender.status = TenderStatus.ANALYZED
                        tender.risk_score = 50
                        tender.margin_estimate = "не определена"
                        tender.teaser_description = "Документация недоступна для анализа"
                        await db.commit()
                        continue

                    # Run AI teaser analysis
                    analysis = await ai_service.analyze_teaser(tender.raw_text)

                    # Update tender with analysis results
                    tender.risk_score = analysis.risk_score
                    tender.margin_estimate = analysis.margin_estimate
                    tender.teaser_description = analysis.description
                    tender.status = TenderStatus.ANALYZED

                    await db.commit()
                    analyzed += 1
                    logger.info(
                        f"Tender {tender.id} analyzed: "
                        f"risk={analysis.risk_score}%, margin={analysis.margin_estimate}"
                    )

                except Exception as e:
                    logger.error(f"Error analyzing tender {tender.id}: {e}")

            logger.info(f"Tender analysis completed: {analyzed} tenders analyzed")
            job_stats.finish_run("analyze_tenders", processed=analyzed)

    except Exception as e:
        logger.error(f"Tender analysis job failed: {e}")
        job_stats.finish_run("analyze_tenders", error=str(e))


async def send_notifications_job():
    """
    Job: Send teaser notifications for ANALYZED tenders.
    Runs every 10 minutes.
    """
    logger.info("Starting notification job")
    job_stats.start_run("send_notifications")
    try:
        async with get_db_context() as db:
            sent = await notification_service.process_analyzed_tenders(db, limit=10)
            logger.info(f"Notification job completed: {sent} notifications sent")
            job_stats.finish_run("send_notifications", processed=sent)
    except Exception as e:
        logger.error(f"Notification job failed: {e}")
        job_stats.finish_run("send_notifications", error=str(e))


async def get_queue_counts() -> dict:
    """Get count of tenders in each status (queue sizes)."""
    async with get_db_context() as db:
        result = await db.execute(
            select(Tender.status, func.count(Tender.id))
            .group_by(Tender.status)
        )
        counts = {status.value: count for status, count in result.all()}
        return counts
