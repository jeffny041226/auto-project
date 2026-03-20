"""Schemas package."""
from app.schemas.user import UserCreate, UserLogin, UserUpdate, UserResponse
from app.schemas.script import ScriptCreate, ScriptUpdate, ScriptResponse, ScriptListResponse
from app.schemas.task import TaskCreate, TaskUpdate, TaskResponse, TaskDetailResponse, TaskListResponse
from app.schemas.device import DeviceCreate, DeviceUpdate, DeviceResponse, DeviceListResponse
from app.schemas.common import ResponseBase, PaginationParams, ErrorDetail, HealthCheckResponse

__all__ = [
    "UserCreate",
    "UserLogin",
    "UserUpdate",
    "UserResponse",
    "ScriptCreate",
    "ScriptUpdate",
    "ScriptResponse",
    "ScriptListResponse",
    "TaskCreate",
    "TaskUpdate",
    "TaskResponse",
    "TaskDetailResponse",
    "TaskListResponse",
    "DeviceCreate",
    "DeviceUpdate",
    "DeviceResponse",
    "DeviceListResponse",
    "ResponseBase",
    "PaginationParams",
    "ErrorDetail",
    "HealthCheckResponse",
]
