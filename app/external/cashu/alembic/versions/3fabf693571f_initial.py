"""initial

Revision ID: 3fabf693571f
Revises:
Create Date: 2023-02-17 21:21:34.224256

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.engine.reflection import Inspector

import app.external.cashu.wallet.models as wm

# revision identifiers, used by Alembic.
revision = "3fabf693571f"
down_revision = None
branch_labels = None
depends_on = None


conn = op.get_bind()
inspector = Inspector.from_engine(conn)
tables = inspector.get_table_names()


def create_table(name, *columns, **kwargs):
    if name not in tables:
        op.create_table(name, *columns, **kwargs)


def upgrade() -> None:
    # proofs table
    create_table(
        wm.proofs_table_name,
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("C", sa.String(), nullable=False),
        sa.Column("secret", sa.String(), nullable=False, unique=True),
        sa.Column("reserved", sa.Boolean()),
        sa.Column("send_id", sa.String()),
        sa.Column("time_created", sa.DateTime()),
        sa.Column("time_reserved", sa.DateTime()),
    )

    # proofs_used table
    create_table(
        wm.proofs_used_table_name,
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("C", sa.String(), nullable=False),
        sa.Column("secret", sa.String(), nullable=False, unique=True),
        sa.Column("time_used", sa.TIMESTAMP),
    )

    op.execute(
        """
        CREATE VIEW IF NOT EXISTS balance AS
        SELECT COALESCE(SUM(s), 0) AS balance FROM (
            SELECT SUM(amount) AS s
            FROM proofs
            WHERE amount > 0
        );
    """
    )

    op.execute(
        """
        CREATE VIEW IF NOT EXISTS balance_used AS
        SELECT COALESCE(SUM(s), 0) AS used FROM (
            SELECT SUM(amount) AS s
            FROM proofs_used
            WHERE amount > 0
        );
    """
    )

    create_table(
        wm.p2sh_table_name,
        sa.Column("address", sa.String(), nullable=False, unique=True),
        sa.Column("script", sa.String(), nullable=False, unique=True),
        sa.Column("signature", sa.String(), nullable=False, unique=True),
        sa.Column("used", sa.Boolean(), nullable=False),
    )

    create_table(
        wm.keysets_table_name,
        sa.Column("id", sa.String(), unique=True),
        sa.Column("mint_url", sa.String(), unique=True),
        sa.Column("valid_from", sa.DateTime(), default=sa.func.now()),
        sa.Column("valid_to", sa.DateTime(), default=sa.func.now()),
        sa.Column("first_seen", sa.DateTime(), default=sa.func.now()),
        sa.Column("active", sa.Boolean(), nullable=False, default=True),
    )

    create_table(
        wm.invoices_table_name,
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("pr", sa.String(), nullable=False),
        sa.Column("hash", sa.String(), unique=True),
        sa.Column("preimage", sa.String()),
        sa.Column("paid", sa.Boolean(), default=False),
        sa.Column("time_created", sa.DateTime(), default=sa.func.now()),
        sa.Column("time_paid", sa.DateTime(), default=sa.func.now()),
    )

    create_table(
        wm.nostr_table_name,
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("last", sa.DateTime(), default=None),
    )

    op.execute("INSERT INTO nostr (type, last) VALUES ('dm', NULL)")


def downgrade() -> None:
    op.drop_table(wm.proofs_table_name)
    op.drop_table(wm.proofs_used_table_name)
    op.drop_table(wm.p2sh_table_name)
    op.drop_table(wm.keysets_table_name)
    op.drop_table(wm.invoices_table_name)
    op.drop_table(wm.nostr_table_name)
