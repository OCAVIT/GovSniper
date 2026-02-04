"""Tender-related Pydantic schemas."""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict

from src.models.tender import TenderStatus


class TenderBase(BaseModel):
    """Base tender schema."""

    external_id: str
    title: str
    url: str
    price: Optional[Decimal] = None
    customer_name: Optional[str] = None


class TenderCreate(TenderBase):
    """Schema for creating a tender."""

    pass


class TenderTeaser(BaseModel):
    """Teaser information for email/notification."""

    id: int
    external_id: str
    title: str
    url: str
    price: Optional[Decimal]
    risk_score: Optional[int]
    margin_estimate: Optional[str]
    teaser_description: Optional[str]

    model_config = ConfigDict(from_attributes=True)


class TenderResponse(TenderBase):
    """Full tender response schema."""

    id: int
    status: TenderStatus
    risk_score: Optional[int] = None
    margin_estimate: Optional[str] = None
    teaser_description: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class TenderDetailResponse(TenderResponse):
    """Detailed tender response with analysis."""

    deep_analysis: Optional[str] = None
    has_documents: bool = False

    @classmethod
    def from_orm_with_docs(cls, tender):
        """Create response with document info."""
        return cls(
            **TenderResponse.model_validate(tender).model_dump(),
            deep_analysis=tender.deep_analysis,
            has_documents=bool(tender.raw_text or tender.s3_files_path),
        )
