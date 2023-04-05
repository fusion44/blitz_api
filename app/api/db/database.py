from enum import Enum
from typing import AsyncGenerator

import sqlalchemy
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from app.api.db.utils import run_migrations

Base = declarative_base()


class DatabaseType(Enum):
    SQLITE = 1
    UNSUPPORTED = 2


class Database:
    initialized = False

    def __init__(self, db_url: str) -> None:
        # only SQlite for now
        self.db_type = DatabaseType.SQLITE
        self.db_url = db_url

    async def initialize(self) -> None:
        if self.initialized:
            raise RuntimeError(f"Database {self.db_url} already initialized.")

        run_migrations(self.db_url)

        # connect_args={"check_same_thread": False} is only necessary for SQlite
        self.engine = create_async_engine(
            self.db_url, connect_args={"check_same_thread": False}, echo=False
        )
        self.async_session_builder = sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )

        self._literal_processor = sqlalchemy.String("").literal_processor(
            dialect=self.engine.dialect
        )

        self.initialized = True

    @property
    def async_session(self) -> AsyncSession:
        if not self.initialized:
            raise RuntimeError("Database not initialized.")

        return self.async_session_builder()

    @property
    def l_proc(self):
        if not self.initialized:
            raise RuntimeError("Database not initialized.")

        return self._literal_processor

    async def get_async_session(self) -> AsyncGenerator[AsyncSession, None]:
        if not self.initialized:
            raise RuntimeError("Database not initialized.")

        async with self.async_session_builder() as session:
            yield
