"""API v1 package."""
from fastapi import APIRouter

from app.api.v1 import auth, scripts, tasks, devices, reports, agent

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(scripts.router, prefix="/scripts", tags=["Scripts"])
api_router.include_router(tasks.router, prefix="/tasks", tags=["Tasks"])
api_router.include_router(devices.router, prefix="/devices", tags=["Devices"])
api_router.include_router(reports.router, prefix="/reports", tags=["Reports"])
api_router.include_router(agent.router, prefix="/agent", tags=["Agent"])
