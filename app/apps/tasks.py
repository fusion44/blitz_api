import asyncio

from app.api.config import config
from app.apps.constants import InstallMode
from app.apps.models import AppId
from app.apps.tasks_impl import app_manage_task_impl, update_app_state_task_impl
from app.celery_app import celery_app

BAPI_REDIS_URL = config("BAPI_REDIS_URL", "redis://127.0.0.1:6379/0")

if BAPI_REDIS_URL == "":
    raise Exception("BAPI_REDIS_URL is not set")


@celery_app.task(name="app.apps.tasks.update_app_state_task")
def update_app_state_task():
    """
    Celery task to fetch the latest app status, update the cache
    and notify on Redis channel.
    """
    asyncio.run(update_app_state_task_impl(BAPI_REDIS_URL))


@celery_app.task(name="app.apps.tasks.manage_app_task")
def manage_app_task(id: AppId, mode: InstallMode, keep_data: bool = True):
    """
    Celery task to manage an app.

    Args:
        id (AppId): The ID of the app to be managed.
        mode (InstallMode): The mode of installation or management.
        keep_data (bool): Flag indicating whether to keep existing data.
    """
    asyncio.run(app_manage_task_impl(BAPI_REDIS_URL, id, mode, keep_data))
