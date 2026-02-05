"""DaData API service for company information lookup."""

import logging
from dataclasses import dataclass

import httpx

from src.config import settings

logger = logging.getLogger(__name__)

DADATA_URL = "https://suggestions.dadata.ru/suggestions/api/4_1/rs/findById/party"


@dataclass
class CompanyInfo:
    """Company information from DaData."""

    inn: str
    kpp: str | None
    name: str
    full_name: str | None
    email: str | None
    phone: str | None
    address: str | None
    okved: str | None  # Main activity code
    okved_name: str | None  # Activity description
    status: str | None  # ACTIVE, LIQUIDATING, LIQUIDATED, etc.


class DaDataService:
    """Service for fetching company info from DaData API."""

    def __init__(self):
        self.api_key = settings.dadata_api_key
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Token {self.api_key}",
        }

    async def get_company_by_inn(self, inn: str) -> CompanyInfo | None:
        """
        Get company information by INN.

        Args:
            inn: Company INN (10 or 12 digits)

        Returns:
            CompanyInfo or None if not found
        """
        if not self.api_key:
            logger.warning("DaData API key not configured")
            return None

        if not inn or len(inn) not in (10, 12):
            logger.warning(f"Invalid INN format: {inn}")
            return None

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    DADATA_URL,
                    headers=self.headers,
                    json={"query": inn, "count": 1},
                )
                response.raise_for_status()
                data = response.json()

            suggestions = data.get("suggestions", [])
            if not suggestions:
                logger.info(f"No company found for INN: {inn}")
                return None

            company = suggestions[0]
            company_data = company.get("data", {})

            # Extract contact info
            emails = company_data.get("emails")
            phones = company_data.get("phones")

            email = None
            if emails and isinstance(emails, list) and len(emails) > 0:
                email = emails[0].get("value") if isinstance(emails[0], dict) else emails[0]

            phone = None
            if phones and isinstance(phones, list) and len(phones) > 0:
                phone = phones[0].get("value") if isinstance(phones[0], dict) else phones[0]

            # Extract address
            address_data = company_data.get("address", {})
            address = address_data.get("value") if address_data else None

            # Extract OKVED (activity code)
            okved = company_data.get("okved")
            okved_name = company_data.get("okved_type")

            # Extract status
            state = company_data.get("state", {})
            status = state.get("status") if state else None

            return CompanyInfo(
                inn=company_data.get("inn", inn),
                kpp=company_data.get("kpp"),
                name=company.get("value", ""),
                full_name=company_data.get("name", {}).get("full_with_opf"),
                email=email,
                phone=phone,
                address=address,
                okved=okved,
                okved_name=okved_name,
                status=status,
            )

        except httpx.HTTPStatusError as e:
            logger.error(f"DaData API error for INN {inn}: {e.response.status_code}")
            return None
        except Exception as e:
            logger.error(f"Error fetching company info for INN {inn}: {e}")
            return None

    async def get_companies_batch(self, inns: list[str]) -> dict[str, CompanyInfo | None]:
        """
        Get company information for multiple INNs.

        Args:
            inns: List of INNs to lookup

        Returns:
            Dict mapping INN to CompanyInfo (or None if not found)
        """
        results = {}
        for inn in inns:
            results[inn] = await self.get_company_by_inn(inn)
        return results


# Singleton instance
dadata_service = DaDataService()
