"""Task scheduler for managing test execution."""
import asyncio
from typing import Optional, Callable, Any
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task import Task
from app.models.task_step import TaskStep
from app.core.executor.device_pool import DevicePool
from app.core.executor.driver import MaestroDriver
from app.core.vision.analyzer import VisionAnalyzer
from app.core.self_healing.detector import SelfHealingDetector
from app.utils.logger import get_logger

logger = get_logger(__name__)


class TaskScheduler:
    """Schedules and manages task execution."""

    def __init__(self, db: AsyncSession):
        """Initialize task scheduler."""
        self.db = db
        self.device_pool = DevicePool(db)
        self.maestro = MaestroDriver()
        self.vision = VisionAnalyzer()
        self.self_healing = SelfHealingDetector()
        self._running_tasks = {}
        self._callbacks = {}

    def register_callback(self, event: str, callback: Callable) -> None:
        """Register callback for scheduler events.

        Args:
            event: Event name (task_started, task_progress, task_completed, etc.)
            callback: Async callback function
        """
        if event not in self._callbacks:
            self._callbacks[event] = []
        self._callbacks[event].append(callback)

    async def execute_task(
        self,
        task_id: str,
        script_content: str,
        device_id: str = None,
        user_id: int = None,
    ) -> dict[str, Any]:
        """Execute a task.

        Args:
            task_id: Task ID
            script_content: Maestro YAML script content
            device_id: Device ID (optional, auto-allocated if None)
            user_id: User ID for device allocation

        Returns:
            Execution result dict
        """
        logger.info(f"Starting task execution: {task_id}")

        # Allocate device
        if not device_id:
            device = await self.device_pool.get_available_device()
            if not device:
                return {
                    "success": False,
                    "error": "No available devices",
                }
            device_id = device.device_id

        try:
            # Update task status
            await self._update_task_status(task_id, "running", device_id=device_id)

            # Execute via Maestro
            result = await self.maestro.execute(
                yaml_content=script_content,
                device_id=device_id,
                task_id=task_id,
            )

            if result["success"]:
                await self._update_task_status(task_id, "completed")
                await self._trigger_callbacks("task_completed", task_id, result)
            else:
                error_type = self.self_healing.classify_error(result.get("error", ""))
                await self._update_task_status(
                    task_id,
                    "failed",
                    error_type=error_type,
                    error_message=result.get("error"),
                )
                await self._trigger_callbacks("task_failed", task_id, result)

            return result

        except Exception as e:
            logger.error(f"Task execution error: {e}")
            await self._update_task_status(task_id, "failed", error_message=str(e))
            return {
                "success": False,
                "error": str(e),
            }
        finally:
            # Release device
            await self.device_pool.release_device(device_id)

    async def execute_step(
        self,
        task_id: str,
        step: dict,
        device_id: str,
        step_index: int,
    ) -> dict[str, Any]:
        """Execute a single step with self-healing.

        Args:
            task_id: Task ID
            step: Step definition dict
            device_id: Device ID
            step_index: Step index

        Returns:
            Step execution result
        """
        action = step.get("action")
        target = step.get("target")
        value = step.get("value")

        logger.debug(f"Executing step {step_index}: {action} on {target}")

        # Take screenshot before
        screenshot_before = await self._take_screenshot(device_id, task_id, step_index, "before")

        # Build Maestro command
        maestro_step = self._build_maestro_step(action, target, value)

        # Execute with retries
        max_retries = 3
        retry_count = 0
        last_error = None

        while retry_count < max_retries:
            try:
                result = await self.maestro.execute_step(
                    step=maestro_step,
                    device_id=device_id,
                )

                if result["success"]:
                    # Take screenshot after
                    screenshot_after = await self._take_screenshot(device_id, task_id, step_index, "after")

                    # Update step in database
                    await self._update_step(
                        task_id,
                        step_index,
                        status="completed",
                        screenshot_before=screenshot_before,
                        screenshot_after=screenshot_after,
                        duration_ms=result.get("duration_ms"),
                    )

                    return result

                last_error = result.get("error")

                # Try self-healing
                if retry_count < max_retries - 1:
                    fixed_step = await self.self_healing.try_fix(
                        step=step,
                        error=last_error,
                        screenshot=screenshot_before,
                    )

                    if fixed_step:
                        step = fixed_step
                        logger.info(f"Self-healing applied for step {step_index}")
                        await self._update_step(
                            task_id,
                            step_index,
                            fix_applied=str(fixed_step.get("action")),
                            retry_count=retry_count + 1,
                        )

                retry_count += 1

            except Exception as e:
                last_error = str(e)
                logger.error(f"Step execution error: {e}")
                retry_count += 1

        # All retries failed
        await self._update_step(
            task_id,
            step_index,
            status="failed",
            screenshot_before=screenshot_before,
            error_detail=last_error,
            retry_count=retry_count,
        )

        return {
            "success": False,
            "error": last_error,
        }

    async def _update_task_status(
        self,
        task_id: str,
        status: str,
        device_id: str = None,
        error_type: str = None,
        error_message: str = None,
    ) -> None:
        """Update task status."""
        from sqlalchemy import select

        result = await self.db.execute(select(Task).where(Task.task_id == task_id))
        task = result.scalar_one_or_none()

        if task:
            task.status = status
            if device_id:
                task.device_id = device_id
            if error_type:
                task.error_type = error_type
            if error_message:
                task.error_message = error_message
            if status == "completed":
                task.completed_steps = task.total_steps
            await self.db.flush()

    async def _update_step(
        self,
        task_id: str,
        step_index: int,
        status: str = None,
        screenshot_before: str = None,
        screenshot_after: str = None,
        duration_ms: int = None,
        retry_count: int = None,
        fix_applied: str = None,
        error_detail: str = None,
    ) -> None:
        """Update task step status."""
        from sqlalchemy import select, and_

        result = await self.db.execute(
            select(TaskStep).where(
                and_(
                    TaskStep.task_id == task_id,
                    TaskStep.step_index == step_index,
                )
            )
        )
        step = result.scalar_one_or_none()

        if step:
            if status:
                step.status = status
            if screenshot_before:
                step.screenshot_before = screenshot_before
            if screenshot_after:
                step.screenshot_after = screenshot_after
            if duration_ms is not None:
                step.duration_ms = duration_ms
            if retry_count is not None:
                step.retry_count = retry_count
            if fix_applied:
                step.fix_applied = fix_applied
            if error_detail:
                step.error_detail = error_detail
            await self.db.flush()

    async def _take_screenshot(
        self,
        device_id: str,
        task_id: str,
        step_index: int,
        timing: str,
    ) -> Optional[str]:
        """Take screenshot and upload to storage."""
        try:
            screenshot_path = f"/tmp/{task_id}_step{step_index}_{timing}.png"
            # In real implementation, capture from device
            # For now, return placeholder
            return screenshot_path
        except Exception as e:
            logger.error(f"Screenshot error: {e}")
            return None

    def _build_maestro_step(self, action: str, target: str, value: Any) -> dict:
        """Build Maestro step dict."""
        step = {"action": action}
        if target:
            step["target"] = target
        if value:
            step["value"] = value
        return step

    async def _trigger_callbacks(
        self,
        event: str,
        task_id: str,
        data: dict,
    ) -> None:
        """Trigger registered callbacks."""
        callbacks = self._callbacks.get(event, [])
        for callback in callbacks:
            try:
                await callback(task_id, data)
            except Exception as e:
                logger.error(f"Callback error for {event}: {e}")
