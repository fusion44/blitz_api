import os
import sqlite3
from sqlite3 import Error

from alembic import command
from alembic.config import Config
from loguru import logger


def ensure_sqlite_db_file(db_file):
    """ensures that the SQlite database file exists"""

    logger.debug(f"Ensuring that SQLite the database file exists: {db_file}")

    # look up if the file exists
    if os.path.exists(db_file):
        return

    # look up if the file is in a subdirectory
    if os.path.dirname(db_file) != "":
        # if not, create the directory
        os.makedirs(os.path.dirname(db_file), exist_ok=True)

    # create the file
    conn = None
    try:
        conn = sqlite3.connect(db_file)
    except Error as e:
        print(e)
    finally:
        if conn:
            conn.close()


def run_migrations(db_url):
    """runs the database migrations"""

    ensure_sqlite_db_file(db_url.split("///")[1])

    alembic_cfg = Config()
    alembic_cfg.set_main_option("script_location", "./app/api/db/alembic")

    if "+aiosqlite" in db_url:
        # migrations are sync => remove aiosqlite from the url
        db_url = db_url.replace("+aiosqlite", "")

    alembic_cfg.set_main_option("sqlalchemy.url", db_url)

    logger.info(f"Running migrations: {db_url}")
    command.upgrade(alembic_cfg, "head")
    logger.success(f"Migrations OK")
