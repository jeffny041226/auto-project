"""Common schemas."""
from typing import Generic, TypeVar, Optional, Any
from pydantic import BaseModel

T = TypeVar("T")


class ResponseBase(BaseModel, Generic[T]):
    """Base response schema."""

    code: int = 200
    message: str = "Success"
    data: Optional[T] = None


class PaginationParams(BaseModel):
    """Pagination parameters."""

    skip: int = 0
    limit: int = 20


class ErrorDetail(BaseModel):
    """Error detail schema."""

    field: Optional[str] = None
    message: str
    code: Optional[str] = None


class HealthCheckResponse(BaseModel):
    """Health check response."""

    status: str
    app: str
    version: str
