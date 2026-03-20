"""Report exporter for PDF generation."""
import os
import tempfile
from pathlib import Path

from app.utils.logger import get_logger

logger = get_logger(__name__)


class ReportExporter:
    """Exports reports to various formats."""

    def __init__(self, output_dir: str = None):
        """Initialize exporter.

        Args:
            output_dir: Directory for output files
        """
        self.output_dir = output_dir or tempfile.gettempdir()

    async def export_to_pdf(
        self,
        task_id: str,
        html_content: str,
    ) -> str:
        """Export HTML report to PDF.

        Args:
            task_id: Task ID for naming
            html_content: HTML content

        Returns:
            Path to generated PDF file
        """
        try:
            # Write HTML to temp file
            html_path = os.path.join(self.output_dir, f"{task_id}_report.html")
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(html_content)

            # Generate PDF using WeasyPrint
            pdf_path = os.path.join(self.output_dir, f"{task_id}_report.pdf")

            try:
                from weasyprint import HTML
                HTML(string=html_content, base_url=self.output_dir).write_pdf(pdf_path)
                logger.info(f"PDF exported to {pdf_path}")
            except ImportError:
                logger.warning("WeasyPrint not available, returning HTML path")
                return html_path

            # Cleanup HTML file
            os.remove(html_path)

            return pdf_path

        except Exception as e:
            logger.error(f"PDF export error: {e}")
            raise

    async def export_to_json(
        self,
        task_id: str,
        report_data: dict,
    ) -> str:
        """Export report data to JSON.

        Args:
            task_id: Task ID for naming
            report_data: Report data dict

        Returns:
            Path to generated JSON file
        """
        import json

        json_path = os.path.join(self.output_dir, f"{task_id}_report.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)

        logger.info(f"JSON exported to {json_path}")
        return json_path
