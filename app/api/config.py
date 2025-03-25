import os
from typing import Any

from decouple import (
    Config,
    RepositoryEmpty,
    RepositoryEnv,
    Undefined,
    UndefinedValueError,
)
from loguru import logger

_config: Config | None = None


def config(
    option: str,
    default: Any | Undefined = Undefined(),
    cast: Any | Undefined = Undefined(),
):
    if _config is None:
        _setup_config()
        logger.trace("Configuration was not initialized => calling setup_config()")

    try:
        if _config is not None:  # query again, to please the linter
            return _config(option, default=default, cast=cast)
    except UndefinedValueError as e:
        logger.debug(f"Type of _config: {_config}")
        raise e


def _setup_config():
    global _config
    file_path = os.environ.get("BAPI_ENV_PATH")
    file_path = "" if file_path is None else os.path.abspath(file_path)
    try:
        if os.path.isfile(file_path):
            logger.info(f"Using configuration from: {file_path}")
            _config = Config(RepositoryEnv(file_path))
        elif os.path.isfile(".env"):
            logger.info("Using configuration from: .env")
            _config = Config(RepositoryEnv(".env"))
        else:
            logger.info("No configuration file found, using empty repository")
            _config = Config(RepositoryEmpty())
    except Exception as e:
        logger.error(f"Exception {e}, using empty repository")
        _config = Config(RepositoryEmpty())
