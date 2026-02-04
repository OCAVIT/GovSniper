"""PDF report generation service - STUB version for testing without WeasyPrint."""

import logging

logger = logging.getLogger(__name__)


class PDFGenerator:
    """Stub PDF generator for testing without WeasyPrint."""

    async def generate_deep_audit_report(self, tender, analysis) -> bytes:
        """
        Generate PDF report stub.

        Returns a simple text file instead of PDF for testing.
        To use real PDF generation, install WeasyPrint and GTK3 Runtime.
        """
        logger.warning(
            "PDF generation is using STUB - install WeasyPrint for real PDFs. "
            "Download GTK3 Runtime from: "
            "https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer/releases"
        )

        # Return simple text report instead of PDF
        report_text = f"""
        ========================================
        GOVSNIPER TENDER REPORT (TEXT VERSION)
        ========================================

        Tender ID: {tender.id}
        External ID: {tender.external_id}
        Title: {tender.title}
        Price: {tender.price} RUB

        Risk Score: {tender.risk_score}
        Margin Estimate: {tender.margin_estimate}

        ========================================
        ANALYSIS
        ========================================

        {analysis}

        ========================================
        NOTE: This is a text report stub.
        For PDF reports, install WeasyPrint:
        1. Install GTK3 Runtime
        2. pip install weasyprint
        ========================================
        """

        return report_text.encode('utf-8')


# Singleton instance
pdf_generator = PDFGenerator()
