"""FastAPI application entry point."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import api_router
from app.api.ws import router as ws_router
from app.core.agent.websocket_proxy import router as agent_ws_router
from app.config import settings
from app.db.database import close_db, init_db, async_session_factory
from app.db.redis import redis_client
from app.db.minio import minio_client
from app.utils.logger import LoggerMixin, setup_logging, TraceIdMiddleware
from app.core.device.scanner import start_device_scanner, stop_device_scanner
from app.core.device.agent import device_agent_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    setup_logging(level="DEBUG" if settings.DEBUG else "INFO")
    logger = LoggerMixin().logger
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")

    # Initialize database
    await init_db()
    logger.info("Database initialized")

    # Connect Redis
    await redis_client.connect()
    logger.info("Redis connected")

    # Connect MinIO
    minio_client.connect()
    logger.info("MinIO connected")

    # Start ADB device scanner
    await start_device_scanner(async_session_factory)
    logger.info("ADB device scanner started")

    # Start device heartbeat monitoring
    await device_agent_manager.start_heartbeat_monitoring()
    logger.info("Device heartbeat monitoring started")

    yield

    # Shutdown
    await device_agent_manager.stop_heartbeat_monitoring()
    await stop_device_scanner()
    await redis_client.close()
    await close_db()
    logger.info("Application shutdown complete")


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # Add middleware
    app.add_middleware(TraceIdMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include API router
    app.include_router(api_router, prefix=settings.API_V1_PREFIX)

    # Include WebSocket routers
    app.include_router(ws_router)
    app.include_router(agent_ws_router)

    @app.get("/health")
    async def health_check():
        """Health check endpoint."""
        return {
            "status": "healthy",
            "app": settings.APP_NAME,
            "version": settings.APP_VERSION,
        }

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )
