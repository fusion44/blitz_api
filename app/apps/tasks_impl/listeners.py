"""
This module defines listeners for Redis channels that handle app status updates
and installation progress events.

These listeners are responsible for processing events from Redis channels and
broadcasting updates to clients via SSE (Server-Sent Events).
"""

import json

from loguru import logger

from app.api.channel import BaseChannelListener
from app.api.config import config
from app.api.utils import SSE, broadcast_sse_msg
from app.apps.constants import AppsServiceActions, AppsServiceKeys
from app.apps.models import InstallState

BAPI_REDIS_URL = config("BAPI_REDIS_URL", "redis://127.0.0.1:6379/0")
if BAPI_REDIS_URL == "":
    raise Exception("BAPI_REDIS_URL is not set")


class AppStatusUpdateListener(BaseChannelListener):
    """Listener for app status update events from Redis channels."""

    def __init__(self):
        super().__init__(AppsServiceKeys.APP_STATE_CHANNEL, BAPI_REDIS_URL)

    async def handle_event(self, event):
        """Process app state change events from the Redis channel"""
        logger.debug(f"Received app state event: {event}")

        key = action = new_value = None
        try:
            key = event.get("key")
            action = event.get("action")
            new_value = event.get("new_value")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse channel event JSON data: {e}")
        except KeyError as e:
            logger.error(f"Missing required key in channel event: {e}")
        except Exception as e:
            logger.exception(f"Unexpected error handling channel event: {e}")

        if not key or not action:
            logger.error("Missing key or action in channel event")
            return

        match (key, action):
            case (AppsServiceKeys.APP_STATUS_CACHE_KEY, AppsServiceActions.STARTED):
                await broadcast_sse_msg(SSE.APP_STATE_UPDATING, None)
            case (AppsServiceKeys.APP_STATUS_CACHE_KEY, AppsServiceActions.UPDATED):
                try:
                    if new_value:
                        parsed_status = json.loads(new_value)
                        await broadcast_sse_msg(SSE.INSTALLED_APP_STATUS, parsed_status)
                        await broadcast_sse_msg(SSE.APP_STATE_UPDATING_SUCCESS, None)
                        logger.info(
                            "App state updated via channel and broadcasted to clients"
                        )
                    else:
                        logger.warning("Received app status update with no value")
                except Exception as e:
                    logger.error(f"Failed to process app status update: {e}")
            case (
                AppsServiceKeys.APP_STATUS_UPDATE_FAILED_KEY,
                AppsServiceActions.ERROR,
            ):
                try:
                    if new_value:
                        error_payload = json.loads(new_value)
                        await broadcast_sse_msg(
                            SSE.APP_STATE_UPDATE_ERROR, error_payload
                        )
                        logger.info("App state update error broadcasted to clients")
                    else:
                        logger.warning("Received app status error with no value")
                except Exception as e:
                    logger.error(f"Failed to process app status error: {e}")
            case (AppsServiceKeys.APP_STATUS_LOCK_KEY, AppsServiceActions.LOCKED):
                logger.debug(f"Received lock status change: {action}")
            case _:
                logger.warning(
                    f"Received unknown channel event - key: {key}, action: {action}"
                )
