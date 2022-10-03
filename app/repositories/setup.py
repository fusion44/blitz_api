from decouple import config

from app.models.system import APIPlatform

router = None

_PLATFORM = config("platform", default=APIPlatform.RASPIBLITZ)
if _PLATFORM == APIPlatform.RASPIBLITZ:
    from app.repositories.setup_impl.raspiblitz.router import router
