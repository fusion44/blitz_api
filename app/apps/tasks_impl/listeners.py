"""
This module defines listeners for Redis channels that handle app status updates
and installation progress events.

These listeners are responsible for processing events from Redis channels and
broadcasting updates to clients via SSE (Server-Sent Events).
"""

import json

from loguru import logger
from pydantic import ValidationError

from app.api.channel import BaseChannelListener
from app.api.config import config
from app.api.utils import SSE, broadcast_sse_msg
from app.apps.constants import AppsServiceKeys
from app.apps.models import (
    AppManagementProcessState,
    AppManageTaskMessage,
    AppStatusUpdateTaskMessage,
)

BAPI_REDIS_URL = config("BAPI_REDIS_URL", "redis://127.0.0.1:6379/0")
if BAPI_REDIS_URL == "":
    raise Exception("BAPI_REDIS_URL is not set")


class AppManageListener(BaseChannelListener):
    """Listener for app manage events from Redis channels."""

    def __init__(self):
        super().__init__(AppsServiceKeys.APP_MANAGE_CHANNEL_KEY, BAPI_REDIS_URL)

    async def handle_event(self, event):
        """Process app manage progress events from the Redis channel"""
        # This handler basically just forwards events from the task to the client
        # Most of this logic here is just error handling and logging
        logger.debug(f"Received app manage progress event: {event}")

        key = message_json = None
        try:
            key = event.get("key")
            message_json = event.get("json_contents")
        except json.JSONDecodeError as e:
            return logger.error(f"Failed to parse channel event JSON data: {e}")
        except KeyError as e:
            return logger.error(f"Missing required key in channel event: {e}")
        except Exception as e:
            return logger.exception(f"Unexpected error handling channel event: {e}")

        if key != AppsServiceKeys.APP_MANAGE_MESSAGE_KEY:
            return logger.warning(f"Received unknown key '{key}' in app install event")

        if message_json is None:
            return logger.warning(
                f"Received app install event without message: {event}"
            )

        try:
            message = AppManageTaskMessage.model_validate_json(message_json)
        except ValidationError as e:
            return logger.error(f"Failed to validate app install message: {e}")
        except Exception as e:
            return logger.error(f"Failed to parse app install message: {e}")

        logger.trace("Broadcasting app management message")
        await broadcast_sse_msg(SSE.APP_MANAGE_MESSAGE, message.model_dump())

        if message.state == AppManagementProcessState.FINISHED:
            await self.stop()


class AppStatusUpdateListener(BaseChannelListener):
    """Listener for app status update events from Redis channels."""

    def __init__(self):
        super().__init__(AppsServiceKeys.APP_STATUS_CHANNEL_KEY, BAPI_REDIS_URL)

    async def handle_event(self, event):
        """Process app state change events from the Redis channel"""
        logger.debug(f"Received app state update event: {event}")

        key = message_json = None
        try:
            key = event.get("key")
            message_json = event.get("json_contents")
        except json.JSONDecodeError as e:
            return logger.error(f"Failed to parse channel event JSON data: {e}")
        except KeyError as e:
            return logger.error(f"Missing required key in channel event: {e}")
        except Exception as e:
            return logger.exception(f"Unexpected error handling channel event: {e}")

        if key != AppsServiceKeys.APP_STATUS_MESSAGE_KEY:
            return logger.warning(
                f"Received unexpected key '{key}' in app status update event"
            )

        if message_json is None:
            return logger.warning(
                f"Received app app status update event without message: {event}"
            )

        try:
            message = AppStatusUpdateTaskMessage.model_validate_json(message_json)
        except ValidationError as e:
            return logger.error(f"Failed to validate app status update message: {e}")
        except Exception as e:
            return logger.error(f"Failed to parse app status update message: {e}")

        logger.trace("Broadcasting app management message")
        await broadcast_sse_msg(SSE.APP_STATE_MESSAGE, message.model_dump())

        # Note: the app status listener will listen for the entire duration of the
        #       API running, so we don't need to stop it here
