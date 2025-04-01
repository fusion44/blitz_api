from enum import Enum


class AppsServiceActions(str, Enum):
    STARTED = "started"
    UPDATED = "updated"
    ERROR = "error"
    LOCKED = "locked"
    LOCK_ERROR = "lock_error"


class AppsServiceKeys(str, Enum):
    APP_STATE_CHANNEL = "bapi:app_state_channel"
    APP_STATUS_CACHE_KEY = "bapi_app_status_cache"
    APP_STATUS_TIMESTAMP_KEY = "bapi_app_status_timestamp"
    APP_STATUS_LOCK_KEY = "bapi_app_status_update_lock"
    APP_STATUS_UPDATE_FAILED_KEY = "bapi_app_status_update_failed"
