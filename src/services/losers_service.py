"""Service for parsing tender results and extracting losers for lead generation."""

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.models import Client, Tender, TenderStatus
from src.models.participant import ParticipantResult, TenderParticipant

from .dadata_service import dadata_service

logger = logging.getLogger(__name__)


@dataclass
class ParsedParticipant:
    """Parsed participant data from protocol."""

    company_name: str
    inn: str | None
    kpp: str | None
    bid_amount: float | None
    is_winner: bool


class LosersService:
    """Service for extracting and processing tender losers."""

    def __init__(self):
        self.base_url = "https://zakupki.gov.ru"
        self.proxy_url = settings.proxy_url

    def _get_http_client(self, timeout: float = 30.0) -> httpx.AsyncClient:
        """Get HTTP client with proxy and browser-like headers."""
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
            "Connection": "keep-alive",
        }
        kwargs = {
            "timeout": timeout,
            "follow_redirects": True,
            "headers": headers,
        }
        if self.proxy_url:
            kwargs["proxy"] = self.proxy_url
        return httpx.AsyncClient(**kwargs)

    async def _fetch_page(self, url: str) -> str | None:
        """Fetch page HTML."""
        try:
            async with self._get_http_client() as client:
                response = await client.get(url)
                response.raise_for_status()
                return response.text
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.debug(f"Page not found: {url}")
            else:
                logger.error(f"HTTP error fetching {url}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            return None

    def _build_results_url(self, tender_url: str) -> str:
        """Convert tender URL to results/protocol page URL."""
        results_url = tender_url.replace("common-info.html", "supplier-results.html")
        results_url = results_url.replace("documents.html", "supplier-results.html")
        return results_url

    def _build_journal_url(self, tender_url: str) -> str:
        """Convert tender URL to event journal page URL."""
        journal_url = tender_url.replace("common-info.html", "event-journal.html")
        journal_url = journal_url.replace("documents.html", "event-journal.html")
        return journal_url

    def _extract_inn(self, text: str) -> str | None:
        """Extract INN from text (10 or 12 digits)."""
        # Look for INN pattern
        match = re.search(r'ИНН[:\s]*(\d{10,12})', text)
        if match:
            return match.group(1)

        # Try standalone number that looks like INN
        match = re.search(r'\b(\d{10}|\d{12})\b', text)
        if match:
            inn = match.group(1)
            # Basic validation: check control digit would be complex,
            # just ensure it's not obviously wrong
            if inn.startswith('0') and len(inn) == 10:
                return None
            return inn
        return None

    def _extract_kpp(self, text: str) -> str | None:
        """Extract KPP from text (9 digits)."""
        match = re.search(r'КПП[:\s]*(\d{9})', text)
        if match:
            return match.group(1)
        return None

    def _extract_price(self, text: str) -> float | None:
        """Extract price from text."""
        # Remove spaces from numbers
        text = text.replace(' ', '').replace('\xa0', '')
        # Look for price pattern
        match = re.search(r'(\d+(?:[,\.]\d+)?)', text)
        if match:
            price_str = match.group(1).replace(',', '.')
            try:
                return float(price_str)
            except ValueError:
                return None
        return None

    def _parse_participants_from_html(self, html: str) -> list[ParsedParticipant]:
        """Parse participants from protocol HTML."""
        soup = BeautifulSoup(html, "lxml")
        participants = []

        # Pattern 1: Look for participant tables
        # zakupki.gov.ru often uses tables with specific classes
        tables = soup.find_all("table")

        for table in tables:
            rows = table.find_all("tr")
            if len(rows) < 2:
                continue

            # Check if this looks like a participant table
            header = rows[0].get_text().lower()
            if not any(kw in header for kw in ['участник', 'поставщик', 'инн', 'предложение', 'заявка']):
                continue

            for row in rows[1:]:
                cells = row.find_all(['td', 'th'])
                if len(cells) < 2:
                    continue

                row_text = row.get_text()

                # Extract company name (usually first non-empty cell or cell with company-like content)
                company_name = None
                for cell in cells:
                    cell_text = cell.get_text(strip=True)
                    # Skip cells that are just numbers or short
                    if cell_text and len(cell_text) > 10 and not cell_text.isdigit():
                        if 'ООО' in cell_text or 'ИП' in cell_text or 'АО' in cell_text or 'ЗАО' in cell_text:
                            company_name = cell_text
                            break
                        if not company_name:
                            company_name = cell_text

                if not company_name:
                    continue

                inn = self._extract_inn(row_text)
                kpp = self._extract_kpp(row_text)
                bid_amount = None

                # Look for price in cells
                for cell in cells:
                    price = self._extract_price(cell.get_text())
                    if price and price > 1000:  # Likely a bid amount
                        bid_amount = price
                        break

                # Determine if winner
                is_winner = any(kw in row_text.lower() for kw in [
                    'победител', 'выигра', 'признан победител',
                    'заключ', 'контракт заключен'
                ])

                participants.append(ParsedParticipant(
                    company_name=company_name[:500],  # Limit length
                    inn=inn,
                    kpp=kpp,
                    bid_amount=bid_amount,
                    is_winner=is_winner,
                ))

        # Pattern 2: Look for participant blocks/divs
        participant_blocks = soup.find_all(
            class_=lambda x: x and any(
                cls in str(x).lower()
                for cls in ['participant', 'supplier', 'applicant', 'заявк']
            )
        )

        for block in participant_blocks:
            block_text = block.get_text()

            # Try to extract company name
            name_elem = block.find(class_=lambda x: x and 'name' in str(x).lower())
            company_name = name_elem.get_text(strip=True) if name_elem else None

            if not company_name:
                # Fallback: first significant text
                for elem in block.find_all(['span', 'div', 'p']):
                    text = elem.get_text(strip=True)
                    if text and len(text) > 10:
                        company_name = text
                        break

            if not company_name:
                continue

            inn = self._extract_inn(block_text)
            kpp = self._extract_kpp(block_text)
            bid_amount = self._extract_price(block_text)

            is_winner = any(kw in block_text.lower() for kw in [
                'победител', 'выигра', 'признан победител'
            ])

            # Avoid duplicates
            if not any(p.company_name == company_name for p in participants):
                participants.append(ParsedParticipant(
                    company_name=company_name[:500],
                    inn=inn,
                    kpp=kpp,
                    bid_amount=bid_amount,
                    is_winner=is_winner,
                ))

        return participants

    async def extract_participants(self, tender: Tender, db: AsyncSession) -> list[TenderParticipant]:
        """
        Extract participants from tender results page.

        Args:
            tender: Tender to process
            db: Database session

        Returns:
            List of created TenderParticipant entities
        """
        logger.info(f"Extracting participants for tender {tender.external_id}")

        # Build full URL
        tender_url = tender.url
        if not tender_url.startswith("http"):
            tender_url = urljoin(self.base_url, tender_url)

        # Try results page first
        results_url = self._build_results_url(tender_url)
        html = await self._fetch_page(results_url)

        if not html:
            # Try event journal
            journal_url = self._build_journal_url(tender_url)
            html = await self._fetch_page(journal_url)

        if not html:
            logger.warning(f"Could not fetch results for tender {tender.external_id}")
            return []

        # Parse participants
        parsed = self._parse_participants_from_html(html)
        if not parsed:
            logger.info(f"No participants found for tender {tender.external_id}")
            return []

        logger.info(f"Found {len(parsed)} participants for tender {tender.external_id}")

        # Create TenderParticipant entities
        created = []
        for p in parsed:
            # Check if already exists
            existing = await db.execute(
                select(TenderParticipant).where(
                    and_(
                        TenderParticipant.tender_id == tender.id,
                        TenderParticipant.company_name == p.company_name,
                    )
                )
            )
            if existing.scalar_one_or_none():
                continue

            participant = TenderParticipant(
                tender_id=tender.id,
                company_name=p.company_name,
                inn=p.inn,
                kpp=p.kpp,
                bid_amount=p.bid_amount,
                result=ParticipantResult.WINNER if p.is_winner else ParticipantResult.LOSER,
            )
            db.add(participant)
            created.append(participant)

        await db.commit()
        logger.info(f"Created {len(created)} participant records for tender {tender.external_id}")
        return created

    async def fetch_contacts_for_participant(
        self, participant: TenderParticipant, db: AsyncSession
    ) -> bool:
        """
        Fetch contact info for a participant using DaData.

        Args:
            participant: TenderParticipant to fetch contacts for
            db: Database session

        Returns:
            True if contacts were fetched successfully
        """
        if not participant.inn:
            logger.debug(f"No INN for participant {participant.id}, skipping contact fetch")
            participant.contacts_fetched = True
            await db.commit()
            return False

        company_info = await dadata_service.get_company_by_inn(participant.inn)

        if company_info:
            participant.email = company_info.email
            participant.phone = company_info.phone
            participant.address = company_info.address
            if company_info.kpp and not participant.kpp:
                participant.kpp = company_info.kpp

        participant.contacts_fetched = True
        await db.commit()

        if company_info and company_info.email:
            logger.info(f"Fetched contacts for {participant.inn}: {company_info.email}")
            return True

        logger.debug(f"No email found for INN {participant.inn}")
        return False

    def _extract_keywords_from_tender(self, tender: Tender) -> list[str]:
        """Extract relevant keywords from tender title for client subscription."""
        title = tender.title.lower()

        # Common category keywords to extract
        category_keywords = [
            'компьютер', 'сервер', 'ноутбук', 'монитор', 'принтер',
            'оборудование', 'техника', 'мебель', 'стол', 'стул',
            'канцелярия', 'бумага', 'картридж',
            'автомобиль', 'транспорт', 'запчасти',
            'медицин', 'лекарств', 'препарат',
            'строитель', 'ремонт', 'материал',
            'программ', 'софт', 'лицензи',
            'услуги', 'обслуживание', 'сервис',
            'продукт', 'питание', 'продовольств',
        ]

        found_keywords = []
        for kw in category_keywords:
            if kw in title:
                found_keywords.append(kw)

        # If no category keywords found, extract significant words from title
        if not found_keywords:
            words = re.findall(r'[а-яА-ЯёЁ]{4,}', title)
            # Filter common words
            stop_words = {'поставка', 'закупка', 'приобретение', 'выполнение', 'оказание', 'года', 'году'}
            found_keywords = [w for w in words[:5] if w not in stop_words]

        return found_keywords[:5]  # Limit to 5 keywords

    async def create_client_from_loser(
        self, participant: TenderParticipant, tender: Tender, db: AsyncSession
    ) -> Client | None:
        """
        Create a client subscription from a losing participant.

        Args:
            participant: Losing participant
            tender: Original tender they lost
            db: Database session

        Returns:
            Created Client or None if already exists or no email
        """
        if not participant.email:
            logger.debug(f"No email for participant {participant.id}, cannot create client")
            return None

        # Check if client with this email already exists
        existing = await db.execute(
            select(Client).where(Client.email == participant.email)
        )
        if existing.scalar_one_or_none():
            logger.debug(f"Client already exists for email {participant.email}")
            participant.client_created = True
            await db.commit()
            return None

        # Extract keywords from the tender they lost
        keywords = self._extract_keywords_from_tender(tender)

        if not keywords:
            keywords = ['тендер']  # Default fallback

        # Create client
        client = Client(
            email=participant.email,
            name=participant.company_name[:255] if participant.company_name else None,
            company=participant.company_name[:500] if participant.company_name else None,
            phone=participant.phone,
            is_active=True,
            keywords=keywords,
            source="loser",
            source_inn=participant.inn,
            source_tender_id=tender.id,
            notes=f"Автоматически добавлен. Проиграл тендер: {tender.title[:200]}",
        )

        db.add(client)
        participant.client_created = True
        await db.commit()

        logger.info(f"Created client from loser: {participant.email} with keywords {keywords}")
        return client

    async def process_completed_tenders(self, db: AsyncSession, limit: int = 20) -> dict:
        """
        Process completed tenders to extract losers.

        Finds tenders that are old enough to have results,
        extracts participants, fetches contacts, creates clients.

        Args:
            db: Database session
            limit: Maximum tenders to process

        Returns:
            Stats dict with counts
        """
        stats = {
            "tenders_processed": 0,
            "participants_found": 0,
            "contacts_fetched": 0,
            "clients_created": 0,
        }

        if not settings.leadgen_enabled:
            logger.info("Lead generation is disabled")
            return stats

        # Find tenders old enough to have results
        min_age = datetime.utcnow() - timedelta(days=settings.leadgen_min_tender_age_days)
        max_age = datetime.utcnow() - timedelta(days=settings.leadgen_max_tender_age_days)

        # Get tenders that have been notified (processed) but not yet checked for results
        # We need to track this separately - for now, check if they have participants
        result = await db.execute(
            select(Tender)
            .where(
                and_(
                    Tender.status.in_([TenderStatus.NOTIFIED, TenderStatus.SOLD]),
                    Tender.created_at < min_age,
                    Tender.created_at > max_age,
                )
            )
            .order_by(Tender.created_at)
            .limit(limit)
        )
        tenders = result.scalars().all()

        for tender in tenders:
            # Check if already has participants
            existing = await db.execute(
                select(TenderParticipant).where(TenderParticipant.tender_id == tender.id).limit(1)
            )
            if existing.scalar_one_or_none():
                continue

            try:
                participants = await self.extract_participants(tender, db)
                stats["tenders_processed"] += 1
                stats["participants_found"] += len(participants)
            except Exception as e:
                logger.error(f"Error extracting participants for tender {tender.id}: {e}")

        return stats

    async def process_pending_contacts(self, db: AsyncSession, limit: int = 50) -> int:
        """
        Fetch contacts for participants that don't have them yet.

        Args:
            db: Database session
            limit: Maximum participants to process

        Returns:
            Number of contacts fetched
        """
        if not settings.dadata_api_key:
            logger.warning("DaData API key not configured, skipping contact fetch")
            return 0

        result = await db.execute(
            select(TenderParticipant)
            .where(
                and_(
                    TenderParticipant.contacts_fetched == False,
                    TenderParticipant.inn.isnot(None),
                    TenderParticipant.result == ParticipantResult.LOSER,
                )
            )
            .limit(limit)
        )
        participants = result.scalars().all()

        fetched = 0
        for participant in participants:
            try:
                if await self.fetch_contacts_for_participant(participant, db):
                    fetched += 1
            except Exception as e:
                logger.error(f"Error fetching contacts for participant {participant.id}: {e}")

        return fetched

    async def process_pending_clients(self, db: AsyncSession, limit: int = 50) -> int:
        """
        Create clients from losers that have email but no client yet.

        Args:
            db: Database session
            limit: Maximum clients to create

        Returns:
            Number of clients created
        """
        result = await db.execute(
            select(TenderParticipant)
            .where(
                and_(
                    TenderParticipant.client_created == False,
                    TenderParticipant.contacts_fetched == True,
                    TenderParticipant.email.isnot(None),
                    TenderParticipant.result == ParticipantResult.LOSER,
                )
            )
            .limit(limit)
        )
        participants = result.scalars().all()

        created = 0
        for participant in participants:
            try:
                # Get the tender
                tender_result = await db.execute(
                    select(Tender).where(Tender.id == participant.tender_id)
                )
                tender = tender_result.scalar_one_or_none()

                if tender and await self.create_client_from_loser(participant, tender, db):
                    created += 1
            except Exception as e:
                logger.error(f"Error creating client for participant {participant.id}: {e}")

        return created


# Singleton instance
losers_service = LosersService()
