"""API routes."""

from fastapi import APIRouter

from .admin import router as admin_router
from .health import router as health_router
from .webhooks import router as webhooks_router

api_router = APIRouter()
api_router.include_router(health_router, tags=["Health"])
api_router.include_router(webhooks_router, prefix="/webhooks", tags=["Webhooks"])
api_router.include_router(admin_router, prefix="/admin", tags=["Admin"])

__all__ = ["api_router"]
