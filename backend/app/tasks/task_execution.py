"""Task execution async tasks."""
import asyncio
from datetime import datetime
from typing import Any

from app.tasks.celery_app import celery_app
from app.core.executor.scheduler import TaskScheduler
from app.core.script.manager import ScriptManager
from app.db.database import get_db_context
from app.utils.logger import get_logger

logger = get_logger(__name__)


@celery_app.task(bind=True, name="app.tasks.task_execution.execute_task")
def execute_task(
    self,
    task_id: str,
    script_id: str,
    device_id: str = None,
) -> dict[str, Any]:
    """Execute a test task asynchronously.

    Args:
        task_id: Task ID
        script_id: Script ID to execute
        device_id: Optional device ID

    Returns:
        Execution result
    """
    logger.info(f"Starting task execution: {task_id}")

    async def _execute():
        async with get_db_context() as db:
            # Get script
            manager = ScriptManager(db)
            script = await manager.get(script_id)

            if not script:
                return {"success": False, "error": "Script not found"}

            # Execute via scheduler
            scheduler = TaskScheduler(db)

            result = await scheduler.execute_task(
                task_id=task_id,
                script_content=script.maestro_yaml,
                device_id=device_id,
            )

            return {
                "success": result.get("success", False),
                "task_id": task_id,
                "error": result.get("error"),
            }

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    result = loop.run_until_complete(_execute())
    logger.info(f"Task execution completed: {task_id}, success: {result.get('success')}")
    return result


@celery_app.task(bind=True, name="app.tasks.task_execution.execute_step")
def execute_step(
    self,
    task_id: str,
    step_index: int,
    step_action: str,
    step_target: str,
    step_value: Any,
    device_id: str,
) -> dict[str, Any]:
    """Execute a single task step.

    Args:
        task_id: Task ID
        step_index: Step index
        step_action: Action to perform
        step_target: Target element
        step_value: Action value
        device_id: Device ID

    Returns:
        Step execution result
    """
    logger.info(f"Executing step {step_index} for task {task_id}")

    step = {
        "action": step_action,
        "target": step_target,
        "value": step_value,
    }

    async def _execute():
        async with get_db_context() as db:
            scheduler = TaskScheduler(db)
            result = await scheduler.execute_step(
                task_id=task_id,
                step=step,
                device_id=device_id,
                step_index=step_index,
            )
            return result

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    result = loop.run_until_complete(_execute())
    return result


@celery_app.task(bind=True, name="app.tasks.task_execution.update_progress")
def update_progress(
    self,
    task_id: str,
    completed_steps: int,
    total_steps: int = None,
) -> dict[str, Any]:
    """Update task progress.

    Args:
        task_id: Task ID
        completed_steps: Number of completed steps
        total_steps: Total number of steps (optional)

    Returns:
        Update result
    """
    async def _update():
        async with get_db_context() as db:
            from app.services.task import TaskService
            service = TaskService(db)
            await service.update_task_progress(
                task_id=task_id,
                completed_steps=completed_steps,
                total_steps=total_steps,
            )
            return {"success": True}

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    return loop.run_until_complete(_update())
