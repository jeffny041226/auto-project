"""Report service for API endpoints."""
from typing import Optional
import os

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.task import Task
from app.models.task_step import TaskStep
from app.core.report.generator import ReportGenerator
from app.core.report.exporter import ReportExporter
from app.utils.logger import get_logger

logger = get_logger(__name__)


class ReportService:
    """Service for report generation and retrieval."""

    def __init__(self, db: AsyncSession):
        """Initialize report service."""
        self.db = db
        self.generator = ReportGenerator()
        self.exporter = ReportExporter()

    async def get_report(self, task_id: str) -> Optional[dict]:
        """Get report for a task."""
        result = await self.db.execute(select(Task).where(Task.task_id == task_id))
        task = result.scalar_one_or_none()

        if not task:
            return None

        # Get steps
        steps_result = await self.db.execute(
            select(TaskStep)
            .where(TaskStep.task_id == task_id)
            .order_by(TaskStep.step_index)
        )
        steps = steps_result.scalars().all()

        # Build report data
        report_data = self.generator.generate_report_data(task, steps)

        return report_data

    async def generate_html_report(self, task_id: str) -> Optional[str]:
        """Generate HTML report for a task."""
        result = await self.db.execute(select(Task).where(Task.task_id == task_id))
        task = result.scalar_one_or_none()

        if not task:
            return None

        # Get steps
        steps_result = await self.db.execute(
            select(TaskStep)
            .where(TaskStep.task_id == task_id)
            .order_by(TaskStep.step_index)
        )
        steps = list(steps_result.scalars().all())

        # Generate HTML
        html_content = self.generator.generate_html(task, steps)

        return html_content

    async def download_report(self, task_id: str) -> Optional[str]:
        """Generate and return path to PDF report."""
        html_content = await self.generate_html_report(task_id)

        if not html_content:
            return None

        # Export to PDF
        pdf_path = await self.exporter.export_to_pdf(
            task_id=task_id,
            html_content=html_content,
        )

        return pdf_path
