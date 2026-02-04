"""Email service using Resend."""

import base64
import logging
from pathlib import Path

import resend
from jinja2 import Environment, FileSystemLoader

from src.config import settings

logger = logging.getLogger(__name__)

# Initialize Resend
resend.api_key = settings.resend_api_key

# Setup Jinja2 environment
templates_dir = Path(__file__).parent.parent / "templates"
jinja_env = Environment(
    loader=FileSystemLoader(str(templates_dir)),
    autoescape=True,
)


class EmailService:
    """Service for sending emails via Resend."""

    def __init__(self):
        self.from_email = settings.email_from
        self.base_url = settings.app_base_url

    async def send_teaser_email(
        self,
        to_email: str,
        tender_title: str,
        tender_id: int,
        risk_score: int,
        margin_estimate: str,
        description: str,
        payment_url: str,
        report_price: int | None = None,
    ) -> str | None:
        """
        Send teaser email with tender summary and payment link.

        Args:
            to_email: Recipient email
            tender_title: Tender title
            tender_id: Tender ID
            risk_score: Risk score (0-100)
            margin_estimate: Margin estimate string
            description: Short tender description
            payment_url: YooKassa payment URL
            report_price: Dynamic price based on tender value (optional)

        Returns:
            Resend email ID if successful, None otherwise
        """
        try:
            template = jinja_env.get_template("emails/teaser.html")
            html_content = template.render(
                tender_title=tender_title,
                tender_id=tender_id,
                risk_score=risk_score,
                margin_estimate=margin_estimate,
                description=description,
                payment_url=payment_url,
                report_price=report_price or settings.report_price,
            )

            # Determine risk level for subject
            if risk_score <= 30:
                risk_emoji = "✅"
                risk_text = "низкий риск"
            elif risk_score <= 60:
                risk_emoji = "⚠️"
                risk_text = "средний риск"
            else:
                risk_emoji = "🔴"
                risk_text = "высокий риск"

            response = resend.Emails.send(
                {
                    "from": self.from_email,
                    "to": [to_email],
                    "subject": f"{risk_emoji} Новый тендер ({risk_text}): {tender_title[:50]}...",
                    "html": html_content,
                }
            )

            email_id = response.get("id")
            logger.info(f"Teaser email sent to {to_email}: {email_id}")
            return email_id

        except Exception as e:
            logger.error(f"Error sending teaser email to {to_email}: {e}")
            return None

    async def send_report_email(
        self,
        to_email: str,
        tender_title: str,
        tender_id: int,
        pdf_content: bytes,
        filename: str | None = None,
    ) -> str | None:
        """
        Send email with PDF report attached.

        Args:
            to_email: Recipient email
            tender_title: Tender title
            tender_id: Tender ID
            pdf_content: PDF file content as bytes
            filename: Optional filename for attachment

        Returns:
            Resend email ID if successful, None otherwise
        """
        try:
            template = jinja_env.get_template("emails/report_delivery.html")
            html_content = template.render(
                tender_title=tender_title,
                tender_id=tender_id,
            )

            if not filename:
                filename = f"audit_tender_{tender_id}.pdf"

            # Base64 encode PDF for attachment
            pdf_base64 = base64.b64encode(pdf_content).decode("utf-8")

            response = resend.Emails.send(
                {
                    "from": self.from_email,
                    "to": [to_email],
                    "subject": f"📊 Ваш полный аудит тендера №{tender_id}",
                    "html": html_content,
                    "attachments": [
                        {
                            "filename": filename,
                            "content": pdf_base64,
                        }
                    ],
                }
            )

            email_id = response.get("id")
            logger.info(f"Report email sent to {to_email}: {email_id}")
            return email_id

        except Exception as e:
            logger.error(f"Error sending report email to {to_email}: {e}")
            return None

    async def send_welcome_email(self, to_email: str, name: str | None = None) -> str | None:
        """Send welcome email to new subscriber."""
        try:
            response = resend.Emails.send(
                {
                    "from": self.from_email,
                    "to": [to_email],
                    "subject": "Добро пожаловать в GovSniper!",
                    "html": f"""
                    <h1>Добро пожаловать{f', {name}' if name else ''}!</h1>
                    <p>Вы успешно подписались на уведомления о тендерах.</p>
                    <p>Мы будем присылать вам информацию о новых закупках,
                    соответствующих вашим ключевым словам.</p>
                    <p>С уважением,<br>Команда GovSniper</p>
                    """,
                }
            )

            email_id = response.get("id")
            logger.info(f"Welcome email sent to {to_email}: {email_id}")
            return email_id

        except Exception as e:
            logger.error(f"Error sending welcome email to {to_email}: {e}")
            return None


# Singleton instance
email_service = EmailService()
