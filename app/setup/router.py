from decouple import config

from app.system.models import APIPlatform

router = None

_PLATFORM = config("platform", default=APIPlatform.RASPIBLITZ)
if _PLATFORM == APIPlatform.RASPIBLITZ:
    from app.setup.impl.raspiblitz.router import router
