from enum import Enum

DB_LOCKED_KEY = "bapi:app_install_lock"


# Actions used by the API to communicate the internal
# state of the app management process
# These actions are not intended to be sent to the client
class AppsServiceActions(str, Enum):
    STARTED = "started"
    UPDATED = "updated"
    ERROR = "error"
    LOCKED = "locked"
    LOCK_ERROR = "lock_error"


class InstallMode(str, Enum):
    ON = "on"
    OFF = "off"


# State of the app management process
# These states are used to communicate the state to the client
class AppManagementProcessState(str, Enum):
    INITIATED = "initiated"  # start message
    RUNNING = "running"  # message during installation
    SUCCESS = "success"  # message with OK result
    FAILURE = "failure"  # message with error result
    FINISHED = "finished"  # end message when installation has concluded

    @classmethod
    def __get_pydantic_json_schema__(cls, field_schema):
        field_schema.update(
            description="Represents the state of the installation process",
            enum=[state.value for state in cls],
        )


class AppsServiceKeys(str, Enum):
    # App status keys
    APP_STATE_CHANNEL = "bapi:app_state_channel"
    APP_STATUS_LOCK_KEY = "bapi_app_status_update_lock"
    APP_STATUS_CACHE_KEY = "bapi_app_status_cache"
    APP_STATUS_TIMESTAMP_KEY = "bapi_app_status_timestamp"
    APP_STATUS_UPDATE_FAILED_KEY = "bapi_app_status_update_failed"

    # App install keys
    APP_MANAGE_CHANNEL_KEY = "bapi:app_install_channel"
    APP_MANAGE_MESSAGE_KEY = "bapi_app_install_message"
    APP_INSTALL_LOCK_KEY = "bapi_app_install_lock"
