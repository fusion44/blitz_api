import logging
import sys

from decouple import config as dconfig
from loguru import logger

# Sourced from LNbits project:
# https://github.com/lnbits/lnbits/blob/841e8e7bbd61fb942a776d82ca0b6d03668eb524/lnbits/app.py#L285

# More info: https://loguru.readthedocs.io/en/stable/api/logger.html


def configure_logger() -> None:
    level = dconfig("log_level", default="INFO", cast=str)
    log_file = dconfig("log_file", default="", cast=str)

    logger.remove()
    formatter = Formatter(level)
    logger.add(sys.stdout, level=level, format=formatter.format, colorize=True)

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
        self.fmt_default: str = (
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            + "<level>{level.icon}</level> | "
            + "<level>{file}:{line}</level> | "
            + "<level>{message}</level>\n"
        )

        self.fmt_default_exception: str = (
            self.fmt_default + "<level>{exception}</level>\n"
        )

        self.fmt_warning: str = (
            "<yellow>{time:YYYY-MM-DD HH:mm:ss}</yellow> | "
            + "<level>{level.icon}</level> | "
            + "<level>{file}:{line}</level> | "
            + "<level>{message}</level>\n"
        )
        self.fmt_warning_exception: str = (
            self.fmt_warning + "<level>{exception}</level>\n"
        )

        self.fmt_error: str = (
            "<red>{time:YYYY-MM-DD HH:mm:ss}</red> | "
            + "<level>{level.icon}</level> | "
            + "<level>{file}:{line}</level> | "
            + "<level>{message}</level>\n"
        )

        self.fmt_error_exception: str = self.fmt_error + "<level>{exception}</level>\n"

    def format(self, record):
        level = record["level"]
        e = record["exception"] is not None

        if level.no < 30:
            return self.fmt_default_exception if e else self.fmt_default

        if level.no == 30:
            return self.fmt_warning_exception if e else self.fmt_warning

        return self.fmt_error_exception if e else self.fmt_error


class InterceptHandler(logging.Handler):
    def emit(self, record):
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno
        logger.log(level, record.getMessage())
