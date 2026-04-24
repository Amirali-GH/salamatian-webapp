from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    "daily-excel-inbox-scan": {
        "task": "app.workers.tasks.scan_excel_inbox",
        "schedule": crontab(hour=8, minute=0),
    },
}
