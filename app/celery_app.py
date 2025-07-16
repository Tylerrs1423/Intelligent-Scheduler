"""
Celery Configuration for AI Foco with Beat Scheduling
"""

from celery import Celery
from celery.schedules import crontab

# Create Celery app
celery_app = Celery(
    "ai_foco",
    broker="redis://localhost:6379/0",  # Redis as message broker
    backend="redis://localhost:6379/0",  # Redis as result backend
    include=["app.celery_tasks.schedule"]  # Only include the current task module
)

# Basic configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)

# Beat schedule configuration
celery_app.conf.beat_schedule = {
    'schedule-daily-quests': {
        'task': 'app.celery_tasks.daily.schedule_daily_quests',
        'schedule': crontab(minute='*/5'),  # Run every 5 minutes for precise timing
    },
}

if __name__ == "__main__":
    celery_app.start() 