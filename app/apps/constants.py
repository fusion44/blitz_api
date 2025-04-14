from enum import Enum

DB_LOCKED_KEY = "bapi:app_install_lock"


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
    APP_STATUS_CHANNEL_KEY = "bapi:app_status_channel"
    APP_STATUS_LOCK_KEY = "bapi_app_status_update_lock"
    APP_STATUS_MESSAGE_KEY = "bapi_app_status_message"
    APP_STATUS_TIMESTAMP_KEY = "bapi_app_status_timestamp"
    APP_STATUS_UPDATE_FAILED_KEY = "bapi_app_status_update_failed"

    # App install keys
    APP_MANAGE_CHANNEL_KEY = "bapi:app_manage_channel"
    APP_MANAGE_MESSAGE_KEY = "bapi_app_manage_message"
    APP_MANAGE_LOCK_KEY = "bapi_app_manage_lock"
