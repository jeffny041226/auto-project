"""Task service for API endpoints."""
import uuid
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.task import Task
from app.models.task_step import TaskStep
from app.schemas.task import TaskCreate, TaskUpdate, TaskResponse, TaskDetailResponse
from app.utils.logger import get_logger

logger = get_logger(__name__)


class TaskService:
    """Service for task management API."""

    def __init__(self, db: AsyncSession):
        """Initialize task service."""
        self.db = db

    async def create_task(self, task_data: TaskCreate, user_id: int) -> TaskResponse:
        """Create a new task."""
        task = Task(
            task_id=str(uuid.uuid4()),
            user_id=user_id,
            instruction=task_data.instruction,
            device_id=task_data.device_id,
            status="pending",
            total_steps=0,
            completed_steps=0,
        )

        self.db.add(task)
        await self.db.flush()
        await self.db.refresh(task)

        logger.info(f"Task created: {task.task_id}")
        return TaskResponse.model_validate(task)

    async def get_task(self, task_id: str) -> Optional[TaskResponse]:
        """Get task by ID."""
        result = await self.db.execute(select(Task).where(Task.task_id == task_id))
        task = result.scalar_one_or_none()
        if task:
            return TaskResponse.model_validate(task)
        return None

    async def get_task_detail(self, task_id: str) -> Optional[TaskDetailResponse]:
        """Get task with steps."""
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

        return TaskDetailResponse(
            **TaskResponse.model_validate(task).model_dump(),
            steps=[s for s in steps],
        )

    async def list_tasks(
        self, user_id: Optional[int] = None, skip: int = 0, limit: int = 20
    ) -> tuple[list[TaskResponse], int]:
        """List tasks with pagination."""
        query = select(Task)
        count_query = select(Task)

        if user_id:
            query = query.where(Task.user_id == user_id)
            count_query = count_query.where(Task.user_id == user_id)

        from sqlalchemy import func

        total_result = await self.db.execute(select(func.count(Task.id)))
        total = total_result.scalar() or 0

        query = query.order_by(Task.created_at.desc()).offset(skip).limit(limit)
        result = await self.db.execute(query)
        tasks = result.scalars().all()

        return [TaskResponse.model_validate(t) for t in tasks], total

    async def update_task(
        self, task_id: str, task_data: TaskUpdate
    ) -> Optional[TaskResponse]:
        """Update task."""
        result = await self.db.execute(select(Task).where(Task.task_id == task_id))
        task = result.scalar_one_or_none()

        if not task:
            return None

        update_data = task_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(task, field, value)

        await self.db.flush()
        await self.db.refresh(task)

        logger.info(f"Task updated: {task_id}")
        return TaskResponse.model_validate(task)

    async def add_task_step(self, step_data: dict) -> TaskStep:
        """Add a step to a task."""
        step = TaskStep(
            step_id=str(uuid.uuid4()),
            task_id=step_data["task_id"],
            step_index=step_data["step_index"],
            action=step_data["action"],
            target=step_data.get("target"),
            value=step_data.get("value"),
            status="pending",
        )

        self.db.add(step)
        await self.db.flush()
        await self.db.refresh(step)

        return step

    async def update_task_progress(
        self,
        task_id: str,
        completed_steps: int,
        total_steps: int = None,
        status: str = None,
    ) -> None:
        """Update task progress."""
        result = await self.db.execute(select(Task).where(Task.task_id == task_id))
        task = result.scalar_one_or_none()

        if task:
            task.completed_steps = completed_steps
            if total_steps is not None:
                task.total_steps = total_steps
            if status:
                task.status = status
            await self.db.flush()

    async def complete_task(
        self,
        task_id: str,
        status: str = "completed",
        error_type: str = None,
        error_message: str = None,
        duration_ms: int = None,
    ) -> None:
        """Mark task as complete."""
        result = await self.db.execute(select(Task).where(Task.task_id == task_id))
        task = result.scalar_one_or_none()

        if task:
            task.status = status
            task.error_type = error_type
            task.error_message = error_message
            task.duration_ms = duration_ms
            await self.db.flush()

            logger.info(f"Task {task_id} completed with status: {status}")
