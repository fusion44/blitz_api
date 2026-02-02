# Based on the original fastapi-plugins implementation
# Re-implemented to remove the dependency on the unmaintained library

import asyncio
import enum
import typing
from typing import Any, Dict, List, Optional, Union

import redis.asyncio as aioredis
import redis.asyncio.sentinel as aioredis_sentinel
from fastapi import FastAPI
from pydantic_settings import BaseSettings

__all__ = [
    "RedisError",
    "RedisType",
    "RedisSettings",
    "RedisPlugin",
    "redis_plugin",
    "registered_configuration",
    "get_config",
]


class RedisError(Exception):
    pass


@enum.unique
class RedisType(str, enum.Enum):
    redis = "redis"
    sentinel = "sentinel"
    fakeredis = "fakeredis"


class RedisSettings(BaseSettings):
    redis_type: RedisType = RedisType.redis
    redis_url: Optional[str] = None
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_user: Optional[str] = None
    redis_password: Optional[str] = None
    redis_db: Optional[int] = None
    redis_max_connections: Optional[int] = None
    redis_decode_responses: bool = True
    redis_ttl: int = 3600
    redis_sentinels: Optional[str] = None
    redis_sentinel_master: str = "mymaster"
    redis_prestart_tries: int = 60 * 5  # 5 min
    redis_prestart_wait: int = 1  # 1 second

    def get_redis_address(self) -> str:
        if self.redis_url:
            return self.redis_url
        elif self.redis_db:
            return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"
        else:
            return f"redis://{self.redis_host}:{self.redis_port}"

    def get_sentinels(self) -> List:
        if self.redis_sentinels:
            try:
                return [
                    (_conn.split(":")[0].strip(), int(_conn.split(":")[1].strip()))
                    for _conn in self.redis_sentinels.split(",")
                    if _conn.strip()
                ]
            except Exception as e:
                raise RuntimeError(
                    "bad sentinels string :: "
                    f"{type(e)} :: {str(e)} :: {self.redis_sentinels}"
                )
        else:
            return []


class RedisPlugin:
    def __init__(self):
        self.redis: Union[aioredis.Redis, aioredis_sentinel.Sentinel, None] = None
        self.config: Optional[RedisSettings] = None

    async def init_app(
        self, app: FastAPI, config: Optional[RedisSettings] = None
    ) -> None:
        self.config = config or RedisSettings()
        if self.config is None:
            raise RedisError("Redis configuration is not initialized")
        elif not isinstance(self.config, RedisSettings):
            raise RedisError("Redis configuration is not valid")
        # Store the plugin instance in app.state for access if needed,
        # mirroring the original behavior.
        app.state.REDIS = self

    async def init(self) -> None:
        if self.redis is not None:
            raise RedisError("Redis is already initialized")

        if self.config is None:
            raise RedisError("Redis configuration is not initialized")

        opts = dict(
            db=self.config.redis_db,
            username=self.config.redis_user,
            password=self.config.redis_password,
            max_connections=self.config.redis_max_connections,
            decode_responses=self.config.redis_decode_responses,
        )

        address: Any = None
        method: Any = None

        if self.config.redis_type == RedisType.redis:
            address = self.config.get_redis_address()
            method = aioredis.from_url
        elif self.config.redis_type == RedisType.fakeredis:
            try:
                import fakeredis.aioredis  # type: ignore
            except ImportError:
                raise RedisError(
                    f"{self.config.redis_type} requires fakeredis to be installed"
                )
            else:
                address = self.config.get_redis_address()
                method = fakeredis.aioredis.FakeRedis.from_url
        elif self.config.redis_type == RedisType.sentinel:
            address = self.config.get_sentinels()
            method = aioredis_sentinel.Sentinel
        else:
            raise NotImplementedError(
                f"Redis type {self.config.redis_type} is not implemented"
            )

        if not address:
            raise ValueError("Redis address is empty")

        tries = 0
        while True:
            try:
                self.redis = method(address, **opts)
                if self.redis:
                    await self.ping()
                break
            except Exception as e:
                tries += 1
                if tries >= self.config.redis_prestart_tries:
                    raise RedisError(
                        f"Could not connect to Redis after {tries} attempts: {e}"
                    ) from e
                await asyncio.sleep(self.config.redis_prestart_wait)

    async def terminate(self) -> None:
        self.config = None
        if self.redis is not None:
            if isinstance(self.redis, aioredis.Redis):
                await self.redis.close()
            self.redis = None

    async def health(self) -> Dict:
        if self.config is None:
            return dict(status="down", reason="Configuration not initialized")

        address = (
            self.config.get_sentinels()
            if self.config.redis_type == RedisType.sentinel
            else self.config.get_redis_address()
        )

        return dict(
            redis_type=self.config.redis_type,
            redis_address=address,
            redis_pong=(await self.ping()),
        )

    async def ping(self) -> bool:
        if self.redis is None or self.config is None:
            return False

        if self.config.redis_type == RedisType.redis:
            return await self.redis.ping()  # type: ignore
        elif self.config.redis_type == RedisType.fakeredis:
            return await self.redis.ping()  # type: ignore
        elif self.config.redis_type == RedisType.sentinel:
            sentinel: aioredis_sentinel.Sentinel = self.redis  # type: ignore
            master = sentinel.master_for(self.config.redis_sentinel_master)
            return await master.ping()
        else:
            raise NotImplementedError(
                f"Redis type {self.config.redis_type}.ping() is not implemented"
            )

    async def __call__(self) -> Any:
        # Support dependency injection style usage: await redis_plugin()
        if self.redis is None:
            raise RedisError("Redis is not initialized")

        if self.config is None:
            raise RedisError("Redis configuration is not initialized")

        if self.config.redis_type == RedisType.sentinel:
            sentinel: aioredis_sentinel.Sentinel = self.redis  # type: ignore
            conn = sentinel.master_for(self.config.redis_sentinel_master)
        elif self.config.redis_type == RedisType.redis:
            conn = self.redis
        elif self.config.redis_type == RedisType.fakeredis:
            conn = self.redis
        else:
            raise NotImplementedError(
                f"Redis type {self.config.redis_type} is not implemented"
            )

        # Note: aioredis connection objects don't have a simple TTL attribute like this
        # in the newer versions usually, but we keep the logic from the original plugin
        # if it was attaching it dynamically or if older versions had it.
        # However, purely attaching it to the object might be harmless.
        # conn.TTL = self.config.redis_ttl
        return conn


# Singleton instance
redis_plugin = RedisPlugin()


# Configuration Registry Logic
# To support the @registered_configuration and get_config() pattern
_config_class: Optional[typing.Type[RedisSettings]] = None


def registered_configuration(cls):
    global _config_class
    _config_class = cls
    return cls


def get_config() -> RedisSettings:
    global _config_class
    if _config_class:
        return _config_class()
    return RedisSettings()
