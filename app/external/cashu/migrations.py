import os
import sqlite3
from sqlite3 import Error

from alembic import command
from alembic.config import Config


def ensure_sqlite_db_file(db_file):
    """ensures that the SQlite database file exists"""

    # look up if the file exists
    if os.path.exists(db_file):
        return

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
    ensure_sqlite_db_file(db_url.split("///")[1])

    alembic_cfg = Config()
    alembic_cfg.set_main_option("script_location", "./app/external/cashu/alembic")

    if "+aiosqlite" in db_url:
        db_url = db_url.replace("+aiosqlite", "")

    alembic_cfg.set_main_option("sqlalchemy.url", db_url)
    command.upgrade(alembic_cfg, "head")


# PYTHONPATH=. python app/external/cashu/migrations.py

# file_name = "/home/f44/dev/blitz/api/add-cashu/cashu.db/test1.sqlite3"

# # create the database file
# ensure_sqlite_db_file(file_name)

# # now run alembic on the file
# run_migrations(file_name)
