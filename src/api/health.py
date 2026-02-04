"""Health check endpoints."""

from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_db

router = APIRouter()


@router.get("/health")
async def health_check():
    """Basic health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "govsniper",
    }


@router.get("/health/ready")
async def readiness_check(db: AsyncSession = Depends(get_db)):
    """
    Readiness check - verifies database connection.
    Used by Railway/K8s for readiness probes.
    """
    try:
        # Check database connection
        await db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)}"

    is_ready = db_status == "connected"

    return {
        "status": "ready" if is_ready else "not_ready",
        "timestamp": datetime.utcnow().isoformat(),
        "checks": {
            "database": db_status,
        },
    }


@router.get("/health/live")
async def liveness_check():
    """
    Liveness check - basic service check.
    Used by Railway/K8s for liveness probes.
    """
    return {
        "status": "alive",
        "timestamp": datetime.utcnow().isoformat(),
    }
