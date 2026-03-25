"""Tasks API endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.schemas.task import TaskCreate, TaskUpdate, TaskResponse, TaskListResponse
from app.services.task import TaskService
from app.dependencies import get_current_user
from app.models.user import User

router = APIRouter()


@router.post("/", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    task_data: TaskCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new task."""
    service = TaskService(db)
    task = await service.create_task(task_data, current_user.id)
    return task


@router.get("/", response_model=TaskListResponse)
async def list_tasks(skip: int = 0, limit: int = 20, db: AsyncSession = Depends(get_db)):
    """List all tasks."""
    service = TaskService(db)
    tasks, total = await service.list_tasks(skip=skip, limit=limit)
    return {"items": tasks, "total": total}


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(task_id: str, db: AsyncSession = Depends(get_db)):
    """Get task by ID."""
    service = TaskService(db)
    task = await service.get_task(task_id)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return task


@router.patch("/{task_id}", response_model=TaskResponse)
async def update_task(task_id: str, task_data: TaskUpdate, db: AsyncSession = Depends(get_db)):
    """Update task status."""
    service = TaskService(db)
    task = await service.update_task(task_id, task_data)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return task


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(task_id: str, db: AsyncSession = Depends(get_db)):
    """Delete a task."""
    service = TaskService(db)
    deleted = await service.delete_task(task_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return None
