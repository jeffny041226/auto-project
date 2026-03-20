"""User schemas."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class UserBase(BaseModel):
    """Base user schema."""

    username: str = Field(..., min_length=3, max_length=64)
    email: Optional[str] = Field(None, max_length=255)


class UserCreate(UserBase):
    """Schema for creating a user."""

    password: str = Field(..., min_length=6, max_length=128)


class UserLogin(BaseModel):
    """Schema for user login."""

    username: str
    password: str


class UserUpdate(BaseModel):
    """Schema for updating a user."""

    email: Optional[str] = Field(None, max_length=255)
    role: Optional[str] = Field(None, max_length=32)
    status: Optional[str] = Field(None, max_length=32)


class UserResponse(UserBase):
    """Schema for user response."""

    user_id: str
    role: str
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
