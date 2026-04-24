from celery import Celery

from app.config import settings
from app.workers.beat_schedule import CELERY_BEAT_SCHEDULE

celery_app = Celery(
    "salamatian",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Tehran",
    enable_utc=True,
    beat_schedule=CELERY_BEAT_SCHEDULE,
    task_track_started=True,
    task_time_limit=60 * 10,
)
