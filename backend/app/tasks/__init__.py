"""Tasks package."""
from app.tasks.celery_app import celery_app

# Import modules to register tasks
from app.tasks import task_execution
from app.tasks import script_generation
from app.tasks import report_generation

__all__ = ["celery_app"]
