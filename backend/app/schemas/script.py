"""Script schemas."""
from datetime import datetime
from typing import Optional, Any

from pydantic import BaseModel, Field


class ScriptBase(BaseModel):
    """Base script schema."""

    intent: str = Field(..., max_length=255)
    structured_instruction: Optional[dict[str, Any]] = None


class ScriptCreate(ScriptBase):
    """Schema for creating a script."""

    pass


class ScriptUpdate(BaseModel):
    """Schema for updating a script."""

    intent: Optional[str] = Field(None, max_length=255)
    structured_instruction: Optional[dict[str, Any]] = None
    pseudo_code: Optional[str] = None
    maestro_yaml: Optional[str] = None
    status: Optional[str] = Field(None, max_length=32)


class ScriptResponse(ScriptBase):
    """Schema for script response."""

    script_id: str
    user_id: int
    pseudo_code: Optional[str] = None
    maestro_yaml: Optional[str] = None
    version: int
    hit_count: int
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ScriptListResponse(BaseModel):
    """Schema for paginated script list."""

    items: list[ScriptResponse]
    total: int
