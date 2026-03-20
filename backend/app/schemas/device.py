"""Device schemas."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class DeviceBase(BaseModel):
    """Base device schema."""

    device_name: str = Field(..., max_length=128)
    os_version: str = Field(..., max_length=64)
    model: Optional[str] = Field(None, max_length=128)


class DeviceCreate(DeviceBase):
    """Schema for creating a device."""

    device_id: str = Field(..., max_length=64)


class DeviceUpdate(BaseModel):
    """Schema for updating a device."""

    device_name: Optional[str] = Field(None, max_length=128)
    os_version: Optional[str] = Field(None, max_length=64)
    model: Optional[str] = Field(None, max_length=128)
    status: Optional[str] = Field(None, max_length=32)
    current_task_id: Optional[str] = Field(None, max_length=64)
    last_heartbeat: Optional[datetime] = None


class DeviceResponse(DeviceBase):
    """Schema for device response."""

    device_id: str
    status: str
    current_task_id: Optional[str] = None
    last_heartbeat: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DeviceListResponse(BaseModel):
    """Schema for paginated device list."""

    items: list[DeviceResponse]
    total: int
