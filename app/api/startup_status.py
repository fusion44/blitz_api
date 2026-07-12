from app.api.models import ApiStartupStatus

# Single in-process source of truth for bitcoin/lightning startup state.
# Mutated by the startup tasks in app.main; read by the /system/health endpoint
# and the WebSocket warmup. Kept in this leaf module so app.system can import it
# without a circular dependency on app.main.
api_startup_status = ApiStartupStatus()
