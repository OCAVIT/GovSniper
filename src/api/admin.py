"""Admin API endpoints for managing clients and viewing statistics."""

import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, EmailStr
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_db
from src.models import Client, Notification, Payment, PaymentStatus, Tender, TenderStatus

logger = logging.getLogger(__name__)

router = APIRouter()


# ============== Schemas ==============


class ClientCreate(BaseModel):
    """Schema for creating a client."""

    email: EmailStr
    name: Optional[str] = None
    company: Optional[str] = None
    phone: Optional[str] = None
    keywords: list[str]
    min_price: Optional[int] = None
    max_price: Optional[int] = None


class ClientUpdate(BaseModel):
    """Schema for updating a client."""

    name: Optional[str] = None
    company: Optional[str] = None
    phone: Optional[str] = None
    keywords: Optional[list[str]] = None
    is_active: Optional[bool] = None
    min_price: Optional[int] = None
    max_price: Optional[int] = None


class ClientResponse(BaseModel):
    """Schema for client response."""

    id: int
    email: str
    name: Optional[str]
    company: Optional[str]
    phone: Optional[str]
    keywords: list[str]
    is_active: bool
    min_price: Optional[int]
    max_price: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True


class TenderResponse(BaseModel):
    """Schema for tender response."""

    id: int
    external_id: str
    title: str
    url: str
    price: Optional[float]
    status: str
    risk_score: Optional[int]
    margin_estimate: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class StatsResponse(BaseModel):
    """Schema for statistics response."""

    total_tenders: int
    tenders_by_status: dict[str, int]
    total_clients: int
    active_clients: int
    total_revenue: float
    successful_payments: int
    notifications_sent: int
    period_days: int


# ============== Client Endpoints ==============


@router.get("/clients", response_model=list[ClientResponse])
async def list_clients(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    active_only: bool = Query(False),
    db: AsyncSession = Depends(get_db),
):
    """List all clients with optional filtering."""
    query = select(Client).offset(skip).limit(limit).order_by(Client.created_at.desc())

    if active_only:
        query = query.where(Client.is_active == True)  # noqa: E712

    result = await db.execute(query)
    clients = result.scalars().all()

    return clients


@router.post("/clients", response_model=ClientResponse)
async def create_client(
    client_data: ClientCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new client/subscriber."""
    # Check if email already exists
    existing = await db.execute(
        select(Client).where(Client.email == client_data.email)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    client = Client(
        email=client_data.email,
        name=client_data.name,
        company=client_data.company,
        phone=client_data.phone,
        keywords=client_data.keywords,
        min_price=client_data.min_price,
        max_price=client_data.max_price,
        is_active=True,
    )

    db.add(client)
    await db.commit()
    await db.refresh(client)

    logger.info(f"Client created: {client.email}")
    return client


@router.get("/clients/{client_id}", response_model=ClientResponse)
async def get_client(
    client_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get client by ID."""
    result = await db.execute(select(Client).where(Client.id == client_id))
    client = result.scalar_one_or_none()

    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    return client


@router.patch("/clients/{client_id}", response_model=ClientResponse)
async def update_client(
    client_id: int,
    client_data: ClientUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update client details."""
    result = await db.execute(select(Client).where(Client.id == client_id))
    client = result.scalar_one_or_none()

    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    # Update fields
    update_data = client_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(client, field, value)

    await db.commit()
    await db.refresh(client)

    logger.info(f"Client updated: {client.email}")
    return client


@router.delete("/clients/{client_id}")
async def delete_client(
    client_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Delete a client."""
    result = await db.execute(select(Client).where(Client.id == client_id))
    client = result.scalar_one_or_none()

    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    await db.delete(client)
    await db.commit()

    logger.info(f"Client deleted: {client.email}")
    return {"status": "deleted", "id": client_id}


# ============== Tender Endpoints ==============


@router.get("/tenders", response_model=list[TenderResponse])
async def list_tenders(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    status: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """List tenders with optional status filter."""
    query = select(Tender).offset(skip).limit(limit).order_by(Tender.created_at.desc())

    if status:
        try:
            tender_status = TenderStatus(status)
            query = query.where(Tender.status == tender_status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

    result = await db.execute(query)
    tenders = result.scalars().all()

    return tenders


@router.get("/tenders/{tender_id}", response_model=TenderResponse)
async def get_tender(
    tender_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get tender by ID."""
    result = await db.execute(select(Tender).where(Tender.id == tender_id))
    tender = result.scalar_one_or_none()

    if not tender:
        raise HTTPException(status_code=404, detail="Tender not found")

    return tender


# ============== Statistics Endpoints ==============


@router.get("/stats", response_model=StatsResponse)
async def get_statistics(
    days: int = Query(30, ge=1, le=365, description="Period in days"),
    db: AsyncSession = Depends(get_db),
):
    """Get system statistics for the specified period."""
    cutoff_date = datetime.utcnow() - timedelta(days=days)

    # Total tenders
    total_tenders_result = await db.execute(
        select(func.count(Tender.id)).where(Tender.created_at >= cutoff_date)
    )
    total_tenders = total_tenders_result.scalar() or 0

    # Tenders by status
    status_counts = {}
    for status in TenderStatus:
        result = await db.execute(
            select(func.count(Tender.id)).where(
                Tender.status == status,
                Tender.created_at >= cutoff_date,
            )
        )
        status_counts[status.value] = result.scalar() or 0

    # Total clients
    total_clients_result = await db.execute(select(func.count(Client.id)))
    total_clients = total_clients_result.scalar() or 0

    # Active clients
    active_clients_result = await db.execute(
        select(func.count(Client.id)).where(Client.is_active == True)  # noqa: E712
    )
    active_clients = active_clients_result.scalar() or 0

    # Revenue from successful payments
    revenue_result = await db.execute(
        select(func.sum(Payment.amount)).where(
            Payment.status == PaymentStatus.SUCCEEDED,
            Payment.created_at >= cutoff_date,
        )
    )
    total_revenue = float(revenue_result.scalar() or 0)

    # Successful payments count
    payments_result = await db.execute(
        select(func.count(Payment.id)).where(
            Payment.status == PaymentStatus.SUCCEEDED,
            Payment.created_at >= cutoff_date,
        )
    )
    successful_payments = payments_result.scalar() or 0

    # Notifications sent
    notifications_result = await db.execute(
        select(func.count(Notification.id)).where(
            Notification.created_at >= cutoff_date,
        )
    )
    notifications_sent = notifications_result.scalar() or 0

    return StatsResponse(
        total_tenders=total_tenders,
        tenders_by_status=status_counts,
        total_clients=total_clients,
        active_clients=active_clients,
        total_revenue=total_revenue,
        successful_payments=successful_payments,
        notifications_sent=notifications_sent,
        period_days=days,
    )


@router.post("/trigger/scrape")
async def trigger_scrape(db: AsyncSession = Depends(get_db)):
    """Manually trigger RSS scraping and save to database."""
    from src.services.scraper_service import scraper_service

    try:
        new_count = await scraper_service.process_feed(db)
        return {
            "status": "success",
            "new_tenders_saved": new_count,
            "proxy_configured": bool(scraper_service.proxy_url),
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "proxy_configured": bool(scraper_service.proxy_url),
        }


@router.get("/stats/daily")
async def get_daily_statistics(
    days: int = Query(7, ge=1, le=30),
    db: AsyncSession = Depends(get_db),
):
    """Get daily breakdown of statistics."""
    daily_stats = []

    for i in range(days):
        date = datetime.utcnow().date() - timedelta(days=i)
        start = datetime.combine(date, datetime.min.time())
        end = datetime.combine(date, datetime.max.time())

        # Tenders scraped
        tenders_result = await db.execute(
            select(func.count(Tender.id)).where(
                Tender.created_at >= start,
                Tender.created_at <= end,
            )
        )
        tenders_count = tenders_result.scalar() or 0

        # Payments
        payments_result = await db.execute(
            select(func.count(Payment.id)).where(
                Payment.status == PaymentStatus.SUCCEEDED,
                Payment.created_at >= start,
                Payment.created_at <= end,
            )
        )
        payments_count = payments_result.scalar() or 0

        # Revenue
        revenue_result = await db.execute(
            select(func.sum(Payment.amount)).where(
                Payment.status == PaymentStatus.SUCCEEDED,
                Payment.created_at >= start,
                Payment.created_at <= end,
            )
        )
        revenue = float(revenue_result.scalar() or 0)

        daily_stats.append({
            "date": date.isoformat(),
            "tenders": tenders_count,
            "payments": payments_count,
            "revenue": revenue,
        })

    return {"daily_stats": daily_stats}


# ============== Token Usage Endpoints ==============


@router.get("/tokens")
async def get_token_usage():
    """Get OpenAI token usage statistics."""
    from src.services.ai_service import ai_service

    return ai_service.get_usage()


@router.post("/tokens/reset")
async def reset_token_usage():
    """Reset token usage counter."""
    from src.services.ai_service import ai_service

    ai_service.reset_usage()
    return {"status": "reset", "usage": ai_service.get_usage()}


# ============== Scheduler Control Endpoints ==============

# Global scheduler reference (set from main.py)
_scheduler = None


def set_scheduler(scheduler):
    """Set scheduler reference for control endpoints."""
    global _scheduler
    _scheduler = scheduler


@router.get("/scheduler")
async def get_scheduler_status():
    """Get scheduler status and jobs."""
    if _scheduler is None:
        return {"error": "Scheduler not initialized"}

    jobs = []
    for job in _scheduler.get_jobs():
        jobs.append({
            "id": job.id,
            "name": job.name,
            "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
            "trigger": str(job.trigger),
        })

    return {
        "running": _scheduler.running,
        "paused": not _scheduler.running,
        "jobs": jobs,
    }


@router.post("/scheduler/pause")
async def pause_scheduler():
    """Pause all scheduler jobs."""
    if _scheduler is None:
        return {"error": "Scheduler not initialized"}

    if _scheduler.running:
        _scheduler.pause()
        logger.info("Scheduler paused via API")

    return {"status": "paused", "running": _scheduler.running}


@router.post("/scheduler/resume")
async def resume_scheduler():
    """Resume scheduler jobs."""
    if _scheduler is None:
        return {"error": "Scheduler not initialized"}

    if not _scheduler.running:
        _scheduler.resume()
        logger.info("Scheduler resumed via API")

    return {"status": "running", "running": _scheduler.running}
