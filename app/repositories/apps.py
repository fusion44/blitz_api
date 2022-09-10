from decouple import config

from app.models.system import APIPlatform

PLATFORM = config("platform", default=APIPlatform.RASPIBLITZ)
apps = None

if PLATFORM == APIPlatform.RASPIBLITZ:
    from .apps_impl.raspiblitz import RaspiBlitzAppsImpl as AppsImpl
elif PLATFORM == APIPlatform.NATIVE_PYTHON:
    from .apps_impl.native_python import NativePythonAppsImpl as AppsImpl

apps = AppsImpl()

if apps is None:
    raise RuntimeError(f"Unknown platform {PLATFORM}")


async def get_app_status_single(app_id: str):
    return await apps.get_app_status_single(app_id)


async def get_app_status():
    return await apps.get_app_status()


async def get_app_status_sub():
    return await apps.get_app_status_sub()


async def install_app_sub(app_id: str):
    return await apps.install_app_sub(app_id)


async def uninstall_app_sub(app_id: str, delete_data: bool):
    return await apps.uninstall_app_sub(app_id, delete_data)
