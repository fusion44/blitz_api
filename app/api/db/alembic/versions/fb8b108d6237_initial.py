"""initial

Revision ID: fb8b108d6237
Revises:
Create Date: 2023-04-05 19:23:40.096500

"""
import sqlalchemy as sa
from alembic import op
from loguru import logger
from sqlalchemy.engine.reflection import Inspector

import app.api.db.schemas as schemas

# revision identifiers, used by Alembic.
revision = "fb8b108d6237"
down_revision = None
branch_labels = None
depends_on = None

conn = op.get_bind()
inspector = Inspector.from_engine(conn)
tables = inspector.get_table_names()


def create_table(name, *columns, **kwargs):
    logger.trace(f"Creating table: {name}")

    if name not in tables:
        op.create_table(name, *columns, **kwargs)


def upgrade() -> None:
    logger.trace(f"Upgrading database to revision: {revision}")

    create_table(
        schemas.Transaction.__tablename__,
        sa.Column("id", sa.String(50), primary_key=True),
        sa.Column("timestamp", sa.BigInteger(), nullable=False),
        sa.Column("api", sa.SmallInteger(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table(schemas.Transaction.__tablename__)
