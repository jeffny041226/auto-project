"""Celery application configuration."""
from celery import Celery

from app.config import settings

# Create Celery app
celery_app = Celery(
    "auto_test_platform",
    broker=settings.CELERY_BROKER_URL or "redis://localhost:6379/1",
    backend=settings.CELERY_RESULT_BACKEND or "redis://localhost:6379/2",
)

# Celery configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1 hour
    task_soft_time_limit=3300,  # 55 minutes
    worker_prefetch_multiplier=1,
    worker_concurrency=4,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_routes={
        "app.tasks.script_generation.*": {"queue": "script_gen"},
        "app.tasks.task_execution.*": {"queue": "task_exec"},
        "app.tasks.report_generation.*": {"queue": "reports"},
    },
    task_default_queue="default",
)

# Discover tasks
celery_app.autodiscover_tasks(["app.tasks"])


@celery_app.task(bind=True)
def debug_task(self):
    """Debug task for testing Celery."""
    print(f"Request: {self.request!r}")
    return {"status": "success", "task_id": self.request.id}
