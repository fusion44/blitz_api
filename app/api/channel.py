import json
from datetime import datetime

import redis.asyncio as redis_async
from loguru import logger

from app.api.config import config
from app.api.error_report.report import Report
from app.api.utils import redis_delete, redis_get_raw, redis_publish, redis_set
from app.external.result_type.src.result.result import Err, Ok, Result


class BaseChannelNotifier:
    def __init__(self, channel: str, redis_url=None):
        self.redis_url: str = redis_url or config(
            "BAPI_REDIS_URL", "redis://127.0.0.1:6379/0"
        )
        self.redis: redis_async.Redis | None = None
        self.channel: str = channel

    async def connect(self) -> Result[None, Report]:
        if not self.redis:
            try:
                self.redis = await redis_async.from_url(
                    self.redis_url, decode_responses=True
                )
            except Exception as e:
                return Err(
                    Report(
                        message=f"Error connecting to Redis: {e}",
                        error=e,
                    )
                )
        else:
            logger.debug("Redis already connected")

        return Ok(None)

    async def notify_key_change(
        self, key: str, action: str | None = None, old_value=None, new_value=None
    ) -> Result[None, Report]:
        """Publish a formatted notification"""
        if not self.redis:
            return Err(
                Report(
                    message="Redis connection not established. Call connect() first.",
                    error=None,
                )
            )

        event = {
            "timestamp": datetime.now().isoformat(),
            "key": key,
            "action": action,
            "old_value": old_value,
            "new_value": new_value,
        }

        try:
            data = json.dumps(event)
            await redis_publish(self.channel, data, custom_redis=self.redis)
            logger.debug(
                f"Published notification to channel {self.channel}: {action} on {key}"
            )

            return Ok(None)
        except Exception as e:
            return Err(
                Report(
                    message=f"Error publishing notification to channel: {e}",
                    error=e,
                )
            )


class BaseChannelListener:
    def __init__(self, channel: str, redis_url=None):
        self.redis_url = redis_url or config(
            "BAPI_REDIS_URL", "redis://127.0.0.1:6379/0"
        )
        self.redis: redis_async.Redis | None = None
        self.channel: str = channel
        self.running = False

    async def connect(self) -> Result[None, Report]:
        if not self.redis:
            try:
                self.redis = await redis_async.from_url(
                    self.redis_url, decode_responses=True
                )
            except Exception as e:
                return Err(
                    Report(
                        message=f"Error connecting to Redis: {e}",
                        error=e,
                    )
                )
        else:
            logger.debug("Redis already connected")

        return Ok(None)

    async def listen(self) -> Result[None, Report]:
        """Start listening for messages on the channel"""
        if not self.redis:
            return Err(
                Report(
                    message="Redis connection not established. Call connect() first.",
                    error=None,
                )
            )

        pubsub = self.redis.pubsub()
        await pubsub.subscribe(self.channel)
        self.running = True
        logger.info(f"Started listening on channel: {self.channel}")

        try:
            while self.running:
                message = await pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=0.5
                )
                if message is None:
                    continue

                try:
                    event = json.loads(message["data"])
                    await self.handle_event(event)
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse message data: {message['data']}")
                except Exception as e:
                    logger.error(f"Error handling channel message: {e}")

            logger.info(f"Closing channel listener for channel: {self.channel}")
        except Exception as e:
            logger.error(f"Error listening to channel: {e}")
        finally:
            await pubsub.unsubscribe()
            logger.info(f"Stopped listening on channel: {self.channel}")

        return Ok(None)

    async def stop(self) -> Result[None, Report]:
        """Stop listening for messages"""
        self.running = False
        logger.info("Channel listener stopping...")

        return Ok(None)

    async def handle_event(self, event):
        """Process incoming events - to be implemented by subclasses"""
        logger.debug(f"Received event: {event}")
