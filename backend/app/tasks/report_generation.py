"""Report generation async tasks."""
import asyncio
from typing import Any

from app.tasks.celery_app import celery_app
from app.services.report import ReportService
from app.db.database import get_db_context
from app.utils.logger import get_logger

logger = get_logger(__name__)


@celery_app.task(bind=True, name="app.tasks.report_generation.generate_report")
def generate_report(
    self,
    task_id: str,
) -> dict[str, Any]:
    """Generate report for completed task.

    Args:
        task_id: Task ID

    Returns:
        Report generation result
    """
    logger.info(f"Generating report for task {task_id}")

    async def _generate():
        async with get_db_context() as db:
            service = ReportService(db)
            report_data = await service.get_report(task_id)

            if not report_data:
                return {"success": False, "error": "Task not found"}

            return {
                "success": True,
                "task_id": task_id,
                "report_id": report_data.get("report_id"),
            }

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    result = loop.run_until_complete(_generate())
    logger.info(f"Report generation completed for task {task_id}")
    return result


@celery_app.task(bind=True, name="app.tasks.report_generation.export_pdf")
def export_pdf(
    self,
    task_id: str,
) -> dict[str, Any]:
    """Export report as PDF.

    Args:
        task_id: Task ID

    Returns:
        Export result with file path
    """
    logger.info(f"Exporting PDF for task {task_id}")

    async def _export():
        async with get_db_context() as db:
            service = ReportService(db)
            pdf_path = await service.download_report(task_id)

            if not pdf_path:
                return {"success": False, "error": "Failed to export PDF"}

            return {
                "success": True,
                "task_id": task_id,
                "file_path": pdf_path,
            }

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    result = loop.run_until_complete(_export())
    return result


@celery_app.task(bind=True, name="app.tasks.report_generation.send_notification")
def send_notification(
    self,
    task_id: str,
    user_id: int,
    status: str,
) -> dict[str, Any]:
    """Send notification about task completion.

    Args:
        task_id: Task ID
        user_id: User ID
        status: Task status

    Returns:
        Notification result
    """
    logger.info(f"Sending notification for task {task_id}")

    # In a real implementation, this would send email/push notification
    return {
        "success": True,
        "task_id": task_id,
        "user_id": user_id,
        "status": status,
        "notification_sent": True,
    }
