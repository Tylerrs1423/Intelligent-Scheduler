"""
Simple Celery Configuration for AI Foco
Just for testing basic quest scheduling
"""

from celery import Celery

# Create simple Celery app
celery_app = Celery(
    "ai_foco",
    broker="redis://localhost:6379/0",  # Redis as message broker
    backend="redis://localhost:6379/0",  # Redis as result backend
    include=["app.celery_tasks"]  # Import tasks from app.celery_tasks module
)

# Basic configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)

if __name__ == "__main__":
    celery_app.start() 