"""Scheduled jobs for tender processing pipeline."""

import logging

from sqlalchemy import select, func

from src.db import get_db_context
from src.models import Tender, TenderStatus
from src.scheduler.job_stats import job_stats
from src.services.ai_service import ai_service
from src.services.document_service import document_service
from src.services.losers_service import losers_service
from src.services.notification_service import notification_service
from src.services.scraper_service import scraper_service

logger = logging.getLogger(__name__)

# Register jobs for stats tracking
job_stats.register_job("scrape_rss", "Scrape RSS Feed")
job_stats.register_job("download_documents", "Download Documents")
job_stats.register_job("analyze_tenders", "Analyze Tenders")
job_stats.register_job("send_notifications", "Send Notifications")
job_stats.register_job("cleanup_stale_data", "Cleanup Stale Data")
job_stats.register_job("extract_losers", "Extract Tender Losers")
job_stats.register_job("fetch_loser_contacts", "Fetch Loser Contacts")
job_stats.register_job("create_loser_clients", "Create Clients from Losers")


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


# ============= LEAD GENERATION JOBS =============


async def extract_losers_job():
    """
    Job: Extract participants from completed tenders.
    Runs every 6 hours.

    Finds tenders old enough to have results and extracts
    participant information from protocol pages.
    """
    logger.info("Starting losers extraction job")
    job_stats.start_run("extract_losers")
    try:
        async with get_db_context() as db:
            stats = await losers_service.process_completed_tenders(db, limit=20)
            logger.info(
                f"Losers extraction completed: "
                f"{stats['tenders_processed']} tenders, "
                f"{stats['participants_found']} participants"
            )
            job_stats.finish_run("extract_losers", processed=stats["participants_found"])
    except Exception as e:
        logger.error(f"Losers extraction job failed: {e}")
        job_stats.finish_run("extract_losers", error=str(e))


async def fetch_loser_contacts_job():
    """
    Job: Fetch contact information for losers via DaData.
    Runs every 6 hours (after extraction).

    Uses DaData API to get email/phone by INN.
    Free tier: 10k requests/day.
    """
    logger.info("Starting loser contacts fetch job")
    job_stats.start_run("fetch_loser_contacts")
    try:
        async with get_db_context() as db:
            fetched = await losers_service.process_pending_contacts(db, limit=50)
            logger.info(f"Loser contacts fetch completed: {fetched} contacts fetched")
            job_stats.finish_run("fetch_loser_contacts", processed=fetched)
    except Exception as e:
        logger.error(f"Loser contacts fetch job failed: {e}")
        job_stats.finish_run("fetch_loser_contacts", error=str(e))


async def create_loser_clients_job():
    """
    Job: Create client subscriptions from losers with email.
    Runs every 6 hours (after contacts fetch).

    Creates clients with keywords extracted from the tender they lost,
    so they receive notifications about similar tenders.
    """
    logger.info("Starting loser clients creation job")
    job_stats.start_run("create_loser_clients")
    try:
        async with get_db_context() as db:
            created = await losers_service.process_pending_clients(db, limit=50)
            logger.info(f"Loser clients creation completed: {created} clients created")
            job_stats.finish_run("create_loser_clients", processed=created)
    except Exception as e:
        logger.error(f"Loser clients creation job failed: {e}")
        job_stats.finish_run("create_loser_clients", error=str(e))
