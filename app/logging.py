import logging
import sys

from decouple import config as dconfig
from loguru import logger

# Sourced from LNbits project:
# https://github.com/lnbits/lnbits/blob/841e8e7bbd61fb942a776d82ca0b6d03668eb524/lnbits/app.py#L285


def configure_logger() -> None:
    level = dconfig("log_level", default="INFO", cast=str)
    log_file = dconfig("log_file", default="", cast=str)

    logger.remove()
    formatter = Formatter(level)
    logger.add(sys.stderr, level=level, format=formatter.format)

    if log_file is not None and log_file != "":
        logger.add(
            "blitz_api.log",
            level=level,
            format=formatter.format,
            rotation="10 MB",
            retention="30 days",
            compression="zip",
        )

    logging.getLogger("uvicorn").handlers = [InterceptHandler()]
    logging.getLogger("uvicorn.access").handlers = [InterceptHandler()]


class Formatter:
    def __init__(self, level: str):
        self.padding = 0
        self.minimal_fmt: str = "<green>{time:YYYY-MM-DD HH:mm:ss.SS}</green> | <level>{level}</level> | <level>{message}</level>\n"
        if level == "DEBUG":
            self.fmt: str = "<green>{time:YYYY-MM-DD HH:mm:ss.SS}</green> | <level>{level: <4}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | <level>{message}</level>\n"
        else:
            self.fmt: str = self.minimal_fmt

    def format(self, record):
        function = "{function}".format(**record)
        if function == "emit":  # uvicorn logs
            return self.minimal_fmt
        return self.fmt


class InterceptHandler(logging.Handler):
    def emit(self, record):
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno
        logger.log(level, record.getMessage())
