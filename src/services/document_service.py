"""Document download and text extraction service."""

import io
import logging
import re
import zipfile
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from docx import Document as DocxDocument
from PyPDF2 import PdfReader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.models import Tender, TenderStatus

logger = logging.getLogger(__name__)


class DocumentService:
    """Service for downloading and processing tender documents.

    Downloads documents from zakupki.gov.ru, extracts text,
    and stores it in the database (no S3 storage).
    """

    SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt", ".rtf"}
    MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB

    def __init__(self):
        self.base_url = "https://zakupki.gov.ru"
        self.proxy_url = settings.proxy_url

    def _get_http_client(self, timeout: float = 30.0) -> httpx.AsyncClient:
        """Get HTTP client with proxy if configured."""
        kwargs = {"timeout": timeout, "follow_redirects": True}
        if self.proxy_url:
            kwargs["proxy"] = self.proxy_url
        return httpx.AsyncClient(**kwargs)

    async def _fetch_tender_page(self, url: str) -> str | None:
        """Fetch tender page HTML."""
        try:
            async with self._get_http_client(timeout=30.0) as client:
                response = await client.get(url)
                response.raise_for_status()
                return response.text
        except Exception as e:
            logger.error(f"Error fetching tender page {url}: {e}")
            return None

    def _extract_document_links(self, html: str, base_url: str) -> list[str]:
        """Extract document download links from tender page."""
        soup = BeautifulSoup(html, "lxml")
        links = []

        # Common patterns for document links on zakupki.gov.ru
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]

            # Check if it's a document link
            if any(ext in href.lower() for ext in [".pdf", ".docx", ".doc", ".zip", ".rar"]):
                full_url = urljoin(base_url, href)
                links.append(full_url)
                continue

            # Check for download endpoints
            if "/download/" in href or "fileDownload" in href:
                full_url = urljoin(base_url, href)
                links.append(full_url)

        # Remove duplicates while preserving order
        seen = set()
        unique_links = []
        for link in links:
            if link not in seen:
                seen.add(link)
                unique_links.append(link)

        logger.info(f"Found {len(unique_links)} document links")
        return unique_links

    async def _download_file(self, url: str) -> tuple[bytes, str] | None:
        """Download file and return content with filename."""
        try:
            async with self._get_http_client(timeout=60.0) as client:
                response = await client.get(url)
                response.raise_for_status()

                # Check file size
                content = response.content
                if len(content) > self.MAX_FILE_SIZE:
                    logger.warning(f"File too large: {url}")
                    return None

                # Extract filename from URL or Content-Disposition
                filename = Path(urlparse(url).path).name
                if "content-disposition" in response.headers:
                    cd = response.headers["content-disposition"]
                    if "filename=" in cd:
                        filename = re.findall(r'filename="?([^";\n]+)"?', cd)[0]

                return content, filename

        except Exception as e:
            logger.error(f"Error downloading file {url}: {e}")
            return None

    def _extract_text_from_pdf(self, content: bytes) -> str:
        """Extract text from PDF file."""
        try:
            reader = PdfReader(io.BytesIO(content))
            text_parts = []
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    text_parts.append(text)
            return "\n\n".join(text_parts)
        except Exception as e:
            logger.error(f"Error extracting PDF text: {e}")
            return ""

    def _extract_text_from_docx(self, content: bytes) -> str:
        """Extract text from DOCX file."""
        try:
            doc = DocxDocument(io.BytesIO(content))
            text_parts = []
            for para in doc.paragraphs:
                if para.text.strip():
                    text_parts.append(para.text)

            # Also extract from tables
            for table in doc.tables:
                for row in table.rows:
                    for cell in row.cells:
                        if cell.text.strip():
                            text_parts.append(cell.text)

            return "\n\n".join(text_parts)
        except Exception as e:
            logger.error(f"Error extracting DOCX text: {e}")
            return ""

    def _extract_text_from_zip(self, content: bytes) -> str:
        """Extract text from files inside ZIP archive."""
        texts = []
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as zf:
                for filename in zf.namelist():
                    ext = Path(filename).suffix.lower()
                    if ext in self.SUPPORTED_EXTENSIONS:
                        try:
                            file_content = zf.read(filename)
                            if ext == ".pdf":
                                texts.append(self._extract_text_from_pdf(file_content))
                            elif ext == ".docx":
                                texts.append(self._extract_text_from_docx(file_content))
                            elif ext == ".txt":
                                texts.append(file_content.decode("utf-8", errors="ignore"))
                        except Exception as e:
                            logger.warning(f"Error processing {filename} in ZIP: {e}")
        except Exception as e:
            logger.error(f"Error processing ZIP file: {e}")

        return "\n\n".join(filter(None, texts))

    def _extract_text(self, content: bytes, filename: str) -> str:
        """Extract text based on file type."""
        ext = Path(filename).suffix.lower()

        if ext == ".pdf":
            return self._extract_text_from_pdf(content)
        elif ext == ".docx":
            return self._extract_text_from_docx(content)
        elif ext == ".zip":
            return self._extract_text_from_zip(content)
        elif ext == ".txt":
            return content.decode("utf-8", errors="ignore")

        return ""

    async def process_tender(self, tender: Tender, db: AsyncSession) -> bool:
        """
        Download documents for a tender and extract text.

        Text is stored directly in the database (raw_text field).
        No S3 storage is used.

        Args:
            tender: Tender entity to process
            db: Database session

        Returns:
            True if successful, False otherwise
        """
        logger.info(f"Processing tender {tender.external_id}")

        # Build full URL if relative
        tender_url = tender.url
        if not tender_url.startswith("http"):
            tender_url = urljoin(self.base_url, tender_url)

        # Fetch tender page
        html = await self._fetch_tender_page(tender_url)
        if not html:
            logger.error(f"Could not fetch tender page: {tender.url}")
            return False

        # Extract document links
        doc_links = self._extract_document_links(html, tender_url)
        if not doc_links:
            logger.warning(f"No document links found for tender {tender.external_id}")
            # Still mark as downloaded with empty text
            tender.status = TenderStatus.DOWNLOADED
            tender.raw_text = ""
            await db.commit()
            return True

        # Download and extract text from all documents
        all_texts = []

        for url in doc_links[:10]:  # Limit to 10 files
            result = await self._download_file(url)
            if not result:
                continue

            content, filename = result

            # Extract text (no S3 upload - text only)
            text = self._extract_text(content, filename)
            if text:
                all_texts.append(f"--- {filename} ---\n{text}")

        # Update tender with extracted text
        tender.raw_text = "\n\n".join(all_texts) if all_texts else ""
        tender.status = TenderStatus.DOWNLOADED

        await db.commit()
        logger.info(
            f"Tender {tender.external_id} processed: "
            f"{len(all_texts)} documents, {len(tender.raw_text)} chars"
        )
        return True

    async def process_new_tenders(self, db: AsyncSession, limit: int = 5) -> int:
        """
        Process tenders with NEW status.

        Args:
            db: Database session
            limit: Maximum number of tenders to process

        Returns:
            Number of tenders processed
        """
        # Get NEW tenders
        result = await db.execute(
            select(Tender)
            .where(Tender.status == TenderStatus.NEW)
            .order_by(Tender.created_at)
            .limit(limit)
        )
        tenders = result.scalars().all()

        processed = 0
        for tender in tenders:
            try:
                if await self.process_tender(tender, db):
                    processed += 1
            except Exception as e:
                logger.error(f"Error processing tender {tender.external_id}: {e}")

        return processed


# Singleton instance
document_service = DocumentService()
