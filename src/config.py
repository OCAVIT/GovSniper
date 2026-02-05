"""Application configuration using Pydantic Settings."""

import json
from functools import lru_cache
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Database (Supabase)
    # Use Transaction Pooler (port 6543) for serverless environments
    # Format: postgresql+asyncpg://postgres.[ref]:[pass]@aws-0-[region].pooler.supabase.com:6543/postgres
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/govsniper",
        description="Supabase PostgreSQL connection string (use port 6543 for pooler)",
    )

    # OpenAI
    openai_api_key: str = Field(default="", description="OpenAI API key")

    # YooKassa
    yookassa_shop_id: str = Field(default="", description="YooKassa shop ID")
    yookassa_secret_key: str = Field(default="", description="YooKassa secret key")

    # Resend Email
    resend_api_key: str = Field(default="", description="Resend API key")
    email_from: str = Field(default="GovSniper Analytics <info@govsniper.ru>", description="Sender email")

    # Application
    app_base_url: str = Field(default="http://localhost:8080", description="Base URL")
    app_env: str = Field(default="development", description="Environment")

    # Tender Filters
    min_tender_price: int = Field(default=100000, description="Minimum tender price")
    stop_words: List[str] = Field(
        default=["ремонт", "уборка", "питание", "клининг", "охрана"],
        description="Stop words for filtering tenders",
    )

    # Scheduler Intervals
    scraper_interval_minutes: int = Field(default=15)
    document_interval_minutes: int = Field(default=3)
    analyzer_interval_minutes: int = Field(default=5)
    notification_interval_minutes: int = Field(default=10)
    cleanup_interval_hours: int = Field(default=6)

    # Data Retention
    data_retention_days: int = Field(default=3)

    # Pricing (tiered by tender value for better cash-flow)
    # < 1M RUB
    report_price_tier1: int = Field(default=990, description="Price for tenders < 1M")
    # 1M - 10M RUB
    report_price_tier2: int = Field(default=1990, description="Price for tenders 1M-10M")
    # > 10M RUB
    report_price_tier3: int = Field(default=4990, description="Price for tenders > 10M")

    # Legacy/default
    report_price: int = Field(default=990, description="Default price in rubles")

    # RSS Feed (with filters: 44-FZ, sorted by update date)
    rss_feed_url: str = Field(
        default="https://zakupki.gov.ru/epz/order/extendedsearch/rss.html?morphology=on&search-filter=%D0%94%D0%B0%D1%82%D0%B5+%D1%80%D0%B0%D0%B7%D0%BC%D0%B5%D1%89%D0%B5%D0%BD%D0%B8%D1%8F&pageNumber=1&sortDirection=false&recordsPerPage=_10&showLotsInfoHidden=false&sortBy=UPDATE_DATE&fz44=on&pc=on&currencyIdGeneral=-1",
        description="RSS feed URL",
    )

    # Proxy for zakupki.gov.ru (required for foreign hosting like Railway)
    proxy_url: str | None = Field(
        default=None,
        description="HTTP proxy URL for accessing zakupki.gov.ru (e.g., http://user:pass@ip:port)",
    )

    # DaData API for company info lookup (free tier: 10k requests/day)
    dadata_api_key: str = Field(default="", description="DaData API key")
    dadata_secret_key: str = Field(default="", description="DaData secret key")

    # Lead generation settings
    leadgen_enabled: bool = Field(default=True, description="Enable automatic lead generation from losers")
    leadgen_interval_hours: int = Field(default=6, description="Interval for lead generation job")
    leadgen_min_tender_age_days: int = Field(default=7, description="Min days after tender deadline to check results")
    leadgen_max_tender_age_days: int = Field(default=30, description="Max age of tenders to process for leadgen")

    # Logging
    log_level: str = Field(default="INFO")

    # Admin Auth (set via ADMIN_USERNAME and ADMIN_PASSWORD env vars)
    admin_username: str = Field(default="", description="Admin username")
    admin_password: str = Field(default="", description="Admin password")

    @field_validator("stop_words", mode="before")
    @classmethod
    def parse_stop_words(cls, v):
        """Parse stop words from JSON string if needed."""
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return v.split(",")
        return v

    @property
    def is_production(self) -> bool:
        """Check if running in production."""
        return self.app_env.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Global settings instance
settings = get_settings()
