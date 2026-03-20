"""Task schemas."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class TaskStepBase(BaseModel):
    """Base task step schema."""

    action: str = Field(..., max_length=64)
    target: Optional[str] = Field(None, max_length=255)
    value: Optional[str] = None


class TaskStepCreate(TaskStepBase):
    """Schema for creating a task step."""

    step_index: int
    task_id: str


class TaskStepResponse(TaskStepBase):
    """Schema for task step response."""

    step_id: str
    task_id: str
    step_index: int
    status: str
    screenshot_before: Optional[str] = None
    screenshot_after: Optional[str] = None
    retry_count: int
    fix_applied: Optional[str] = None
    error_detail: Optional[str] = None
    duration_ms: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TaskBase(BaseModel):
    """Base task schema."""

    instruction: str


class TaskCreate(TaskBase):
    """Schema for creating a task."""

    device_id: Optional[str] = None


class TaskUpdate(BaseModel):
    """Schema for updating a task."""

    status: Optional[str] = Field(None, max_length=32)
    device_id: Optional[str] = Field(None, max_length=64)
    completed_steps: Optional[int] = None
    error_type: Optional[str] = Field(None, max_length=64)
    error_message: Optional[str] = None
    report_url: Optional[str] = Field(None, max_length=512)
    duration_ms: Optional[int] = None


class TaskResponse(TaskBase):
    """Schema for task response."""

    task_id: str
    user_id: int
    script_id: Optional[str] = None
    device_id: Optional[str] = None
    status: str
    total_steps: int
    completed_steps: int
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    report_url: Optional[str] = None
    duration_ms: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TaskDetailResponse(TaskResponse):
    """Schema for task detail with steps."""

    steps: list[TaskStepResponse] = []


class TaskListResponse(BaseModel):
    """Schema for paginated task list."""

    items: list[TaskResponse]
    total: int
