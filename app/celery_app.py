from celery import Celery
from celery.schedules import crontab
from loguru import logger

from app.api.config import config

BAPI_REDIS_URL = config("BAPI_REDIS_URL", "redis://127.0.0.1:6379/0")

APP_STATUS_UPDATE_INTERVAL_MIN = config(
    "BAPI_APP_STATUS_UPDATE_INTERVAL_MIN", cast=int, default=30
)


if not isinstance(APP_STATUS_UPDATE_INTERVAL_MIN, int):
    raise TypeError("BAPI_APP_STATUS_UPDATE_INTERVAL_MIN must be an integer")

logger.info(f"Celery app started with interval: {APP_STATUS_UPDATE_INTERVAL_MIN} mins")

celery_app = Celery(
    "worker",
    broker=BAPI_REDIS_URL,
    backend=BAPI_REDIS_URL,
    include=["app.apps.tasks"],
    # cache results for 1 hour, will be printed to logs anyway
    result_expires=3600,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)

celery_app.conf.beat_schedule = {
    f"update-app-status-every-{APP_STATUS_UPDATE_INTERVAL_MIN}-mins": {
        "task": "app.apps.tasks.update_app_state_task",
        "schedule": crontab(minute=f"*/{APP_STATUS_UPDATE_INTERVAL_MIN}"),
    },
}

if __name__ == "__main__":
    celery_app.start()
