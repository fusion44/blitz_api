import sqlalchemy as sa

from app.api.db.database import Base


# Transaction data model
class Transaction(Base):
    __tablename__ = "transactions"

    id = sa.Column(sa.String, primary_key=True)
    timestamp = sa.Column(sa.BigInteger)
    api = sa.Column(sa.Integer)
