"""Logging configuration with traceId support."""
import logging
import sys
import uuid
from contextvars import ContextVar
from typing import Optional

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware


# Context variable for trace ID
trace_id_var: ContextVar[Optional[str]] = ContextVar("trace_id", default=None)


def get_trace_id() -> Optional[str]:
    """Get current trace ID from context."""
    return trace_id_var.get()


def generate_trace_id() -> str:
    """Generate new trace ID."""
    return str(uuid.uuid4())[:16]


class TraceIdMiddleware(BaseHTTPMiddleware):
    """Middleware to add trace ID to each request."""

    async def dispatch(self, request: Request, call_next):
        trace_id = request.headers.get("X-Trace-ID", generate_trace_id())
        trace_id_var.set(trace_id)

        response = await call_next(request)
        response.headers["X-Trace-ID"] = trace_id
        return response


def setup_logging(level: str = "INFO") -> None:
    """Setup application logging."""
    log_format = (
        "%(asctime)s - %(name)s - %(levelname)s - "
        "[%(filename)s:%(lineno)d] - %(message)s"
    )

    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format=log_format,
        handlers=[
            logging.StreamHandler(sys.stdout),
        ],
    )


def get_logger(name: str) -> logging.Logger:
    """Get logger with name."""
    return logging.getLogger(name)


class LoggerMixin:
    """Mixin to add logger to any class."""

    @property
    def logger(self) -> logging.Logger:
        """Get logger for this class."""
        name = f"{self.__class__.__module__}.{self.__class__.__name__}"
        return get_logger(name)
