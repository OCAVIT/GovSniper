"""RSS scraper service for zakupki.gov.ru."""

import logging
import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

import feedparser
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.models import Tender, TenderStatus

logger = logging.getLogger(__name__)


@dataclass
class RSSEntry:
    """Parsed RSS entry."""

    external_id: str
    title: str
    url: str
    price: Decimal | None
    customer_name: str | None
    published: datetime | None


class ScraperService:
    """Service for scraping tenders from zakupki.gov.ru RSS feed."""

    def __init__(self):
        self.feed_url = settings.rss_feed_url
        self.min_price = settings.min_tender_price
        self.stop_words = [w.lower() for w in settings.stop_words]
        self.proxy_url = settings.proxy_url

    def _get_http_client(self, timeout: float = 30.0) -> httpx.AsyncClient:
        """Get HTTP client with proxy if configured."""
        kwargs = {"timeout": timeout, "follow_redirects": True}
        if self.proxy_url:
            kwargs["proxy"] = self.proxy_url
            logger.debug(f"Using proxy: {self.proxy_url.split('@')[-1]}")  # Log without credentials
        return httpx.AsyncClient(**kwargs)

    def _extract_external_id(self, url: str) -> str | None:
        """Extract tender ID from URL."""
        # Pattern for zakupki.gov.ru URLs
        patterns = [
            r"regNumber=(\d+)",
            r"/order/(\d+)",
            r"purchaseId=(\d+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

    def _extract_price(self, title: str, summary: str) -> Decimal | None:
        """Extract price from title or summary."""
        # Common patterns for price in Russian tenders
        patterns = [
            r"(\d[\d\s]*[\d])\s*(?:руб|₽|RUB)",
            r"НМЦ[:\s]+(\d[\d\s]*[\d])",
            r"цена[:\s]+(\d[\d\s]*[\d])",
        ]
        text = f"{title} {summary}"
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                price_str = match.group(1).replace(" ", "").replace("\xa0", "")
                try:
                    return Decimal(price_str)
                except Exception:
                    continue
        return None

    def _should_skip(self, title: str, price: Decimal | None) -> bool:
        """Check if tender should be skipped based on filters."""
        title_lower = title.lower()

        # Check stop words
        for stop_word in self.stop_words:
            if stop_word in title_lower:
                logger.debug(f"Skipping tender with stop word '{stop_word}': {title[:50]}")
                return True

        # Check minimum price
        if price is not None and price < self.min_price:
            logger.debug(f"Skipping tender below min price {price}: {title[:50]}")
            return True

        return False

    async def fetch_rss(self) -> list[RSSEntry]:
        """Fetch and parse RSS feed."""
        entries = []

        try:
            async with self._get_http_client(timeout=30.0) as client:
                response = await client.get(self.feed_url)
                response.raise_for_status()

            feed = feedparser.parse(response.text)

            for entry in feed.entries:
                url = entry.get("link", "")
                external_id = self._extract_external_id(url)

                if not external_id:
                    logger.warning(f"Could not extract ID from URL: {url}")
                    continue

                title = entry.get("title", "")
                summary = entry.get("summary", "")
                price = self._extract_price(title, summary)

                # Parse published date
                published = None
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    published = datetime(*entry.published_parsed[:6])

                entries.append(
                    RSSEntry(
                        external_id=external_id,
                        title=title,
                        url=url,
                        price=price,
                        customer_name=entry.get("author"),
                        published=published,
                    )
                )

            logger.info(f"Fetched {len(entries)} entries from RSS feed")

        except httpx.HTTPError as e:
            logger.error(f"HTTP error fetching RSS: {e}")
        except Exception as e:
            logger.error(f"Error parsing RSS feed: {e}")

        return entries

    async def process_feed(self, db: AsyncSession) -> int:
        """
        Fetch RSS feed and save new tenders to database.

        Returns:
            Number of new tenders saved
        """
        entries = await self.fetch_rss()
        new_count = 0

        for entry in entries:
            # Apply filters
            if self._should_skip(entry.title, entry.price):
                continue

            # Check if tender already exists
            existing = await db.execute(
                select(Tender).where(Tender.external_id == entry.external_id)
            )
            if existing.scalar_one_or_none():
                continue

            # Create new tender
            tender = Tender(
                external_id=entry.external_id,
                title=entry.title,
                url=entry.url,
                price=entry.price,
                customer_name=entry.customer_name,
                status=TenderStatus.NEW,
            )

            db.add(tender)
            new_count += 1
            logger.info(f"New tender saved: {entry.external_id} - {entry.title[:50]}")

        await db.commit()
        logger.info(f"Saved {new_count} new tenders")
        return new_count


# Singleton instance
scraper_service = ScraperService()
