"""Scheduler jobs module."""

from .cleanup import cleanup_stale_data_job
from .jobs import (
    analyze_tenders_job,
    create_loser_clients_job,
    download_documents_job,
    extract_losers_job,
    fetch_loser_contacts_job,
    scrape_rss_job,
    send_notifications_job,
)

__all__ = [
    "scrape_rss_job",
    "download_documents_job",
    "analyze_tenders_job",
    "send_notifications_job",
    "cleanup_stale_data_job",
    "extract_losers_job",
    "fetch_loser_contacts_job",
    "create_loser_clients_job",
]
