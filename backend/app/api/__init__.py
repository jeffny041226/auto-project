"""API package init."""
from fastapi import APIRouter

from app.api.v1 import api_router

# Re-export for convenience
__all__ = ["api_router"]
