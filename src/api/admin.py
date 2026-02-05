"""Admin API endpoints for managing clients and viewing statistics."""

import logging
import secrets
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel, EmailStr
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.db import get_db
from src.models import Client, Notification, Payment, PaymentStatus, Tender, TenderStatus
from src.models.participant import ParticipantResult, TenderParticipant

logger = logging.getLogger(__name__)

# Basic Auth (optional - enabled only if ADMIN_USERNAME and ADMIN_PASSWORD are set)
security = HTTPBasic(auto_error=False)


def verify_admin(credentials: HTTPBasicCredentials = Depends(security)):
    """Verify admin credentials if configured."""
    # If auth not configured, allow access
    if not settings.admin_username or not settings.admin_password:
        return None

    # Auth is configured but no credentials provided
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Basic"},
        )

    correct_username = secrets.compare_digest(credentials.username, settings.admin_username)
    correct_password = secrets.compare_digest(credentials.password, settings.admin_password)
    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


router = APIRouter(dependencies=[Depends(verify_admin)])


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
    source: Optional[str] = None
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
    customer_name: Optional[str]
    status: str
    risk_score: Optional[int]
    margin_estimate: Optional[str]
    teaser_description: Optional[str]
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


@router.get("/tenders")
async def list_tenders(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    status: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """List tenders with pagination and optional status filter."""
    # Base query with filters
    base_query = select(Tender)

    if status:
        try:
            tender_status = TenderStatus(status)
            base_query = base_query.where(Tender.status == tender_status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

    # Get total count
    count_result = await db.execute(
        select(func.count()).select_from(base_query.subquery())
    )
    total = count_result.scalar() or 0

    # Get paginated results
    query = base_query.offset(skip).limit(limit).order_by(Tender.created_at.desc())
    result = await db.execute(query)
    tenders = result.scalars().all()

    return {
        "items": [TenderResponse.model_validate(t) for t in tenders],
        "total": total,
        "skip": skip,
        "limit": limit,
        "has_more": skip + len(tenders) < total,
    }


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
_scheduler_paused = False  # Track paused state separately (APScheduler quirk)


def set_scheduler(scheduler):
    """Set scheduler reference for control endpoints."""
    global _scheduler
    _scheduler = scheduler


@router.get("/scheduler")
async def get_scheduler_status(db: AsyncSession = Depends(get_db)):
    """Get scheduler status, jobs with run stats, and queue sizes."""
    from src.scheduler.job_stats import job_stats

    if _scheduler is None:
        return {"error": "Scheduler not initialized"}

    # Get queue counts
    queue_result = await db.execute(
        select(Tender.status, func.count(Tender.id))
        .group_by(Tender.status)
    )
    queue_counts = {str(status.value): count for status, count in queue_result.all()}

    jobs = []
    for job in _scheduler.get_jobs():
        job_data = {
            "id": job.id,
            "name": job.name,
            "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
            "trigger": str(job.trigger),
        }
        # Add job stats if available
        stats = job_stats.to_dict(job.id)
        if stats:
            job_data["stats"] = stats.get("last_run")
            job_data["total_runs"] = stats.get("total_runs", 0)
            job_data["total_processed"] = stats.get("total_processed", 0)
        jobs.append(job_data)

    return {
        "running": not _scheduler_paused,  # Use our tracked state
        "paused": _scheduler_paused,
        "jobs": jobs,
        "queue": queue_counts,
    }


@router.post("/scheduler/pause")
async def pause_scheduler():
    """Pause all scheduler jobs."""
    global _scheduler_paused

    if _scheduler is None:
        return {"error": "Scheduler not initialized"}

    if not _scheduler_paused:
        _scheduler.pause()
        _scheduler_paused = True
        logger.info("Scheduler paused via API")

    return {"status": "paused", "running": False}


@router.post("/scheduler/resume")
async def resume_scheduler():
    """Resume scheduler jobs."""
    global _scheduler_paused

    if _scheduler is None:
        return {"error": "Scheduler not initialized"}

    if _scheduler_paused:
        _scheduler.resume()
        _scheduler_paused = False
        logger.info("Scheduler resumed via API")

    return {"status": "running", "running": True}


# ============== Notifications Endpoints ==============


@router.get("/notifications")
async def list_notifications(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """List recent notifications with their status."""
    from src.models import Notification, NotificationStatus

    result = await db.execute(
        select(Notification)
        .order_by(Notification.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    notifications = result.scalars().all()

    return [
        {
            "id": n.id,
            "tender_id": n.tender_id,
            "client_id": n.client_id,
            "type": n.notification_type.value,
            "status": n.status.value,
            "resend_id": n.resend_id,
            "error_message": n.error_message,
            "created_at": n.created_at.isoformat() if n.created_at else None,
        }
        for n in notifications
    ]


@router.get("/notifications/stats")
async def get_notification_stats(db: AsyncSession = Depends(get_db)):
    """Get notification statistics."""
    from src.models import Notification, NotificationStatus

    stats = {}
    for status in NotificationStatus:
        result = await db.execute(
            select(func.count(Notification.id)).where(Notification.status == status)
        )
        stats[status.value] = result.scalar() or 0

    return stats


@router.post("/test-email")
async def test_email(
    email: str = Query(..., description="Email to send test to"),
):
    """Send a test email to verify Resend configuration."""
    from src.services.email_service import email_service
    from src.config import settings

    if not settings.resend_api_key:
        return {"success": False, "error": "RESEND_API_KEY not configured"}

    try:
        import resend
        resend.api_key = settings.resend_api_key

        response = resend.Emails.send({
            "from": settings.email_from,
            "to": [email],
            "subject": "GovSniper Test Email",
            "html": """
            <h1>Test Email</h1>
            <p>If you see this, email sending is working correctly!</p>
            <p>Timestamp: """ + str(__import__('datetime').datetime.now()) + """</p>
            """,
        })

        return {
            "success": True,
            "email_id": response.get("id"),
            "to": email,
            "from": settings.email_from,
        }
    except Exception as e:
        logger.error(f"Test email failed: {e}")
        return {"success": False, "error": str(e)}


# ============== Lead Generation Endpoints ==============


class ParticipantResponse(BaseModel):
    """Schema for participant response."""

    id: int
    tender_id: int
    company_name: str
    inn: Optional[str]
    bid_amount: Optional[float]
    result: str
    email: Optional[str]
    phone: Optional[str]
    contacts_fetched: bool
    client_created: bool
    created_at: datetime

    class Config:
        from_attributes = True


class LeadgenStatsResponse(BaseModel):
    """Schema for lead generation statistics."""

    total_participants: int
    losers: int
    winners: int
    with_email: int
    clients_created: int
    pending_contacts: int
    pending_clients: int


@router.get("/leadgen/stats", response_model=LeadgenStatsResponse)
async def get_leadgen_stats(db: AsyncSession = Depends(get_db)):
    """Get lead generation statistics."""
    # Total participants
    total_result = await db.execute(select(func.count(TenderParticipant.id)))
    total_participants = total_result.scalar() or 0

    # Losers
    losers_result = await db.execute(
        select(func.count(TenderParticipant.id)).where(
            TenderParticipant.result == ParticipantResult.LOSER
        )
    )
    losers = losers_result.scalar() or 0

    # Winners
    winners_result = await db.execute(
        select(func.count(TenderParticipant.id)).where(
            TenderParticipant.result == ParticipantResult.WINNER
        )
    )
    winners = winners_result.scalar() or 0

    # With email
    with_email_result = await db.execute(
        select(func.count(TenderParticipant.id)).where(
            TenderParticipant.email.isnot(None)
        )
    )
    with_email = with_email_result.scalar() or 0

    # Clients created
    clients_created_result = await db.execute(
        select(func.count(TenderParticipant.id)).where(
            TenderParticipant.client_created == True  # noqa: E712
        )
    )
    clients_created = clients_created_result.scalar() or 0

    # Pending contacts (need to fetch)
    pending_contacts_result = await db.execute(
        select(func.count(TenderParticipant.id)).where(
            TenderParticipant.contacts_fetched == False,  # noqa: E712
            TenderParticipant.inn.isnot(None),
        )
    )
    pending_contacts = pending_contacts_result.scalar() or 0

    # Pending clients (have email, not created)
    pending_clients_result = await db.execute(
        select(func.count(TenderParticipant.id)).where(
            TenderParticipant.client_created == False,  # noqa: E712
            TenderParticipant.email.isnot(None),
        )
    )
    pending_clients = pending_clients_result.scalar() or 0

    return LeadgenStatsResponse(
        total_participants=total_participants,
        losers=losers,
        winners=winners,
        with_email=with_email,
        clients_created=clients_created,
        pending_contacts=pending_contacts,
        pending_clients=pending_clients,
    )


@router.get("/leadgen/participants")
async def list_participants(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    result_filter: Optional[str] = Query(None, description="Filter by result: WINNER, LOSER"),
    has_email: Optional[bool] = Query(None, description="Filter by email presence"),
    db: AsyncSession = Depends(get_db),
):
    """List tender participants with filtering."""
    query = select(TenderParticipant)

    if result_filter:
        try:
            result_enum = ParticipantResult(result_filter)
            query = query.where(TenderParticipant.result == result_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid result filter: {result_filter}")

    if has_email is not None:
        if has_email:
            query = query.where(TenderParticipant.email.isnot(None))
        else:
            query = query.where(TenderParticipant.email.is_(None))

    # Get total count
    count_result = await db.execute(
        select(func.count()).select_from(query.subquery())
    )
    total = count_result.scalar() or 0

    # Get paginated results
    query = query.offset(skip).limit(limit).order_by(TenderParticipant.created_at.desc())
    result = await db.execute(query)
    participants = result.scalars().all()

    return {
        "items": [
            {
                "id": p.id,
                "tender_id": p.tender_id,
                "company_name": p.company_name,
                "inn": p.inn,
                "bid_amount": float(p.bid_amount) if p.bid_amount else None,
                "result": p.result.value,
                "email": p.email,
                "phone": p.phone,
                "contacts_fetched": p.contacts_fetched,
                "client_created": p.client_created,
                "created_at": p.created_at.isoformat() if p.created_at else None,
            }
            for p in participants
        ],
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.get("/leadgen/auto-clients")
async def list_auto_clients(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """List clients created automatically from losers."""
    query = (
        select(Client)
        .where(Client.source == "loser")
        .offset(skip)
        .limit(limit)
        .order_by(Client.created_at.desc())
    )

    result = await db.execute(query)
    clients = result.scalars().all()

    # Get total count
    count_result = await db.execute(
        select(func.count(Client.id)).where(Client.source == "loser")
    )
    total = count_result.scalar() or 0

    return {
        "items": [
            {
                "id": c.id,
                "email": c.email,
                "company": c.company,
                "keywords": c.keywords,
                "source_inn": c.source_inn,
                "source_tender_id": c.source_tender_id,
                "is_active": c.is_active,
                "created_at": c.created_at.isoformat() if c.created_at else None,
            }
            for c in clients
        ],
        "total": total,
    }


@router.post("/leadgen/trigger/extract")
async def trigger_extract_losers(db: AsyncSession = Depends(get_db)):
    """Manually trigger loser extraction job."""
    from src.services.losers_service import losers_service

    try:
        stats = await losers_service.process_completed_tenders(db, limit=20)
        return {
            "status": "success",
            "tenders_processed": stats["tenders_processed"],
            "participants_found": stats["participants_found"],
        }
    except Exception as e:
        logger.error(f"Manual loser extraction failed: {e}")
        return {"status": "error", "error": str(e)}


@router.post("/leadgen/trigger/fetch-contacts")
async def trigger_fetch_contacts(db: AsyncSession = Depends(get_db)):
    """Manually trigger contact fetching job."""
    from src.services.losers_service import losers_service
    from src.config import settings

    if not settings.dadata_api_key:
        return {"status": "error", "error": "DaData API key not configured"}

    try:
        fetched = await losers_service.process_pending_contacts(db, limit=50)
        return {"status": "success", "contacts_fetched": fetched}
    except Exception as e:
        logger.error(f"Manual contact fetch failed: {e}")
        return {"status": "error", "error": str(e)}


@router.post("/leadgen/trigger/create-clients")
async def trigger_create_clients(db: AsyncSession = Depends(get_db)):
    """Manually trigger client creation job."""
    from src.services.losers_service import losers_service

    try:
        created = await losers_service.process_pending_clients(db, limit=50)
        return {"status": "success", "clients_created": created}
    except Exception as e:
        logger.error(f"Manual client creation failed: {e}")
        return {"status": "error", "error": str(e)}
