"""
GovSniper - Government Procurement Analytics Platform

Main application entry point with FastAPI and APScheduler.
"""

import asyncio
import logging
import sys
from contextlib import asynccontextmanager

# Fix for Windows + psycopg: use SelectorEventLoop instead of ProactorEventLoop
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from src.api import api_router
from src.api.health import router as health_router
from src.config import settings
from src.scheduler import (
    analyze_tenders_job,
    cleanup_stale_data_job,
    download_documents_job,
    scrape_rss_job,
    send_notifications_job,
)

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger(__name__)

# Initialize scheduler
scheduler = AsyncIOScheduler()


def setup_scheduler():
    """Configure scheduled jobs."""
    # Scrape RSS feed every 15 minutes
    scheduler.add_job(
        scrape_rss_job,
        trigger=IntervalTrigger(minutes=settings.scraper_interval_minutes),
        id="scrape_rss",
        name="Scrape RSS Feed",
        replace_existing=True,
    )

    # Download documents every 3 minutes
    scheduler.add_job(
        download_documents_job,
        trigger=IntervalTrigger(minutes=settings.document_interval_minutes),
        id="download_documents",
        name="Download Documents",
        replace_existing=True,
    )

    # Analyze tenders every 5 minutes
    scheduler.add_job(
        analyze_tenders_job,
        trigger=IntervalTrigger(minutes=settings.analyzer_interval_minutes),
        id="analyze_tenders",
        name="Analyze Tenders",
        replace_existing=True,
    )

    # Send notifications every 10 minutes
    scheduler.add_job(
        send_notifications_job,
        trigger=IntervalTrigger(minutes=settings.notification_interval_minutes),
        id="send_notifications",
        name="Send Notifications",
        replace_existing=True,
    )

    # Cleanup stale data every 6 hours
    scheduler.add_job(
        cleanup_stale_data_job,
        trigger=IntervalTrigger(hours=settings.cleanup_interval_hours),
        id="cleanup_stale_data",
        name="Cleanup Stale Data",
        replace_existing=True,
    )

    logger.info("Scheduler jobs configured")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    Handles startup and shutdown events.
    """
    # Startup
    logger.info("Starting GovSniper application...")
    logger.info(f"Environment: {settings.app_env}")
    logger.info(f"Base URL: {settings.app_base_url}")

    # Setup and start scheduler
    setup_scheduler()
    scheduler.start()
    logger.info("Scheduler started")

    # Share scheduler with admin API for pause/resume
    from src.api.admin import set_scheduler
    set_scheduler(scheduler)

    # Run initial scrape on startup (optional, comment out if not needed)
    # await scrape_rss_job()

    yield

    # Shutdown
    logger.info("Shutting down GovSniper application...")
    scheduler.shutdown(wait=True)
    logger.info("Scheduler stopped")


# Create FastAPI application
app = FastAPI(
    title="GovSniper",
    description="Government Procurement Analytics Platform",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if not settings.is_production else None,
    redoc_url="/redoc" if not settings.is_production else None,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if not settings.is_production else [settings.app_base_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include health routes at root (for Railway healthcheck)
app.include_router(health_router, tags=["Health"])

# Include API routes
app.include_router(api_router, prefix="/api/v1")

# Static files for UI dashboard
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/")
async def root():
    """Serve UI dashboard or return API info."""
    index_file = static_dir / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {
        "service": "GovSniper",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs" if not settings.is_production else None,
    }


@app.get("/scheduler/status")
async def scheduler_status():
    """Get scheduler jobs status."""
    jobs = []
    for job in scheduler.get_jobs():
        jobs.append({
            "id": job.id,
            "name": job.name,
            "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
            "trigger": str(job.trigger),
        })
    return {"jobs": jobs, "running": scheduler.running}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=8080,
        reload=not settings.is_production,
    )
