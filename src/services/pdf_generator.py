"""PDF report generation service using WeasyPrint."""

import logging
from datetime import datetime
from io import BytesIO
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from weasyprint import CSS, HTML

from src.models import Tender

from .ai_service import DeepAnalysis

logger = logging.getLogger(__name__)

# Setup Jinja2 environment
templates_dir = Path(__file__).parent.parent / "templates"
jinja_env = Environment(
    loader=FileSystemLoader(str(templates_dir)),
    autoescape=True,
)

# Base CSS for reports
BASE_CSS = """
@page {
    size: A4;
    margin: 2cm;
    @bottom-center {
        content: "Страница " counter(page) " из " counter(pages);
        font-size: 10px;
        color: #666;
    }
}

body {
    font-family: 'Liberation Sans', 'DejaVu Sans', Arial, sans-serif;
    font-size: 12px;
    line-height: 1.6;
    color: #333;
}

h1 {
    color: #1a365d;
    font-size: 24px;
    border-bottom: 2px solid #3182ce;
    padding-bottom: 10px;
    margin-bottom: 20px;
}

h2 {
    color: #2c5282;
    font-size: 18px;
    margin-top: 25px;
    margin-bottom: 10px;
}

h3 {
    color: #2b6cb0;
    font-size: 14px;
    margin-top: 15px;
}

.header {
    text-align: center;
    margin-bottom: 30px;
}

.logo {
    font-size: 28px;
    font-weight: bold;
    color: #1a365d;
}

.meta-info {
    background-color: #f7fafc;
    padding: 15px;
    border-radius: 5px;
    margin-bottom: 20px;
}

.meta-info p {
    margin: 5px 0;
}

.risk-badge {
    display: inline-block;
    padding: 5px 15px;
    border-radius: 15px;
    font-weight: bold;
    color: white;
}

.risk-low { background-color: #38a169; }
.risk-medium { background-color: #d69e2e; }
.risk-high { background-color: #e53e3e; }

.section {
    margin-bottom: 25px;
    page-break-inside: avoid;
}

.alert-box {
    padding: 15px;
    border-radius: 5px;
    margin: 10px 0;
}

.alert-warning {
    background-color: #fefcbf;
    border-left: 4px solid #d69e2e;
}

.alert-danger {
    background-color: #fed7d7;
    border-left: 4px solid #e53e3e;
}

.alert-success {
    background-color: #c6f6d5;
    border-left: 4px solid #38a169;
}

ul, ol {
    margin: 10px 0;
    padding-left: 25px;
}

li {
    margin-bottom: 8px;
}

.strategy-box {
    background-color: #ebf8ff;
    padding: 20px;
    border-radius: 5px;
    border: 1px solid #bee3f8;
}

.footer {
    margin-top: 40px;
    padding-top: 20px;
    border-top: 1px solid #e2e8f0;
    font-size: 10px;
    color: #718096;
    text-align: center;
}

table {
    width: 100%;
    border-collapse: collapse;
    margin: 15px 0;
}

th, td {
    border: 1px solid #e2e8f0;
    padding: 10px;
    text-align: left;
}

th {
    background-color: #edf2f7;
    font-weight: bold;
}
"""


class PDFGenerator:
    """Service for generating PDF reports."""

    def __init__(self):
        self.css = CSS(string=BASE_CSS)

    async def generate_deep_audit_report(
        self,
        tender: Tender,
        analysis: DeepAnalysis,
    ) -> bytes:
        """
        Generate deep audit PDF report.

        Args:
            tender: Tender entity
            analysis: Deep analysis result

        Returns:
            PDF content as bytes
        """
        try:
            template = jinja_env.get_template("reports/deep_audit.html")

            # Determine risk level
            risk_score = tender.risk_score or 50
            if risk_score <= 30:
                risk_level = "low"
                risk_text = "Низкий"
            elif risk_score <= 60:
                risk_level = "medium"
                risk_text = "Средний"
            else:
                risk_level = "high"
                risk_text = "Высокий"

            html_content = template.render(
                tender=tender,
                analysis=analysis,
                risk_level=risk_level,
                risk_text=risk_text,
                risk_score=risk_score,
                generated_at=datetime.utcnow().strftime("%d.%m.%Y %H:%M UTC"),
            )

            # Generate PDF
            html = HTML(string=html_content)
            pdf_buffer = BytesIO()
            html.write_pdf(pdf_buffer, stylesheets=[self.css])

            pdf_content = pdf_buffer.getvalue()
            logger.info(f"Generated PDF report: {len(pdf_content)} bytes")
            return pdf_content

        except Exception as e:
            logger.error(f"Error generating PDF: {e}")
            raise

    async def generate_simple_report(
        self,
        title: str,
        content: str,
    ) -> bytes:
        """
        Generate simple PDF report with title and content.

        Args:
            title: Report title
            content: HTML content

        Returns:
            PDF content as bytes
        """
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head><meta charset="utf-8"></head>
        <body>
            <div class="header">
                <div class="logo">GovSniper</div>
            </div>
            <h1>{title}</h1>
            {content}
            <div class="footer">
                Сгенерировано: {datetime.utcnow().strftime("%d.%m.%Y %H:%M UTC")}
            </div>
        </body>
        </html>
        """

        html = HTML(string=html_content)
        pdf_buffer = BytesIO()
        html.write_pdf(pdf_buffer, stylesheets=[self.css])

        return pdf_buffer.getvalue()


# Singleton instance
pdf_generator = PDFGenerator()
