import time
from typing import Any, List

from loguru import logger
from sqlalchemy.engine import Result
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import text

from app.external.cashu.core.base import Invoice, P2SHScript, Proof, WalletKeyset
from app.external.cashu.core.db import Base, Database
from app.external.cashu.core.errors import DatabaseException


def _to_values(data: tuple):
    key_string = ", ".join([f":{i}" for i in range(len(data))])
    values = {f"{i}": data[i] for i in range(len(data))}

    return key_string, values


async def _exec_and_raise(
    session: AsyncSession, query, values={}, commit: bool = False
) -> Result:
    try:
        q = query
        if isinstance(q, str):
            q = text(q)

        res = await session.execute(q, values)

        if commit:
            await session.commit()

        return res
    except SQLAlchemyError as e:
        logger.error(e)
        session.rollback()

        raise DatabaseException(e)


async def store_proof(db: Database, proof: Proof):
    async with db.async_session as session:
        keys, values = _to_values(
            (proof.id, proof.amount, str(proof.C), str(proof.secret), int(time.time()))
        )

        query = f"""
            INSERT INTO proofs (id, amount, C, secret, time_created)
            VALUES ({keys})
            """

        await _exec_and_raise(query=query, values=values, session=session, commit=True)


async def get_proofs(db: Database) -> List[Proof]:
    async with db.async_session as session:
        cursor = await _exec_and_raise(
            session=session, query="SELECT * from proofs", values={}
        )

        return [Proof(**r._mapping) for r in cursor.fetchall()]


async def get_reserved_proofs(db: Database):
    async with db.async_session as session:
        query = "SELECT * from proofs WHERE reserved"
        cursor = await _exec_and_raise(session=session, query=query, values={})

        return [Proof(**r._mapping) for r in cursor.fetchall()]


async def invalidate_proof(proof: Proof, db: Database):
    async with db.async_session as session:
        keys, values = _to_values((str(proof["secret"]),))
        query = f"DELETE FROM proofs WHERE secret = {keys}"
        await _exec_and_raise(session=session, query=query, values=values, commit=True)

        keys, values = _to_values(
            (proof.amount, str(proof.C), str(proof.secret), int(time.time()), proof.id)
        )
        query = f"""
            INSERT INTO proofs_used
            (amount, C, secret, time_used, id)
            VALUES ({keys})
            """

        await _exec_and_raise(session=session, query=query, values=values, commit=True)


async def update_proof_reserved(
    proof: Proof,
    reserved: bool,
    db: Database,
    send_id: str = None,
):
    clauses = []
    values: dict[str, Any] = {}
    clauses.append("reserved = :reserved")
    values["reserved"] = reserved

    if send_id:
        clauses.append("send_id = :send_id")
        values["send_id"] = send_id

    if reserved:
        # set the time of reserving
        clauses.append("time_reserved = :time_reserved")
        values["time_reserved"] = int(time.time())

    async with db.async_session as session:
        query = f"UPDATE proofs SET {', '.join(clauses)} WHERE secret = :secret"
        values["secret"] = str(proof.secret)

        await _exec_and_raise(session=session, query=query, values=values, commit=True)


async def secret_used(db: Database, secret: str):
    async with db.async_session as session:
        query = "SELECT * from proofs WHERE secret = :s"
        values = {"s": secret}
        cursor = await _exec_and_raise(session=session, query=query, values=values)
        rows = cursor.fetchone()

        return rows is not None


async def store_p2sh(db: Database, p2sh: P2SHScript):
    async with db.async_session as session:
        keys = values = _to_values((p2sh.address, p2sh.script, p2sh.signature, False))
        query = f"""
            INSERT INTO p2sh (address, script, signature, used)
            VALUES ({keys})
            """

        await _exec_and_raise(session=session, query=query, values=values, commit=True)


async def get_unused_locks(db: Database, address: str = None):
    clause: List[str] = []
    values: dict[str, Any] = {}

    clause.append("used = 0")

    if address:
        clause.append("address = :address")
        values["address"] = address

    where = ""
    if clause:
        where = f"WHERE {' AND '.join(clause)}"

    async with db.async_session as session:
        query = f"SELECT * from p2sh {where}"
        cursor = await _exec_and_raise(session=session, query=query, values=values)
        rows = cursor.fetchall()

        return [P2SHScript(**r._mapping) for r in rows]


async def update_p2sh_used(db: Database, p2sh: P2SHScript, used: bool):
    clauses = []
    values: dict[str, Any] = {"address": str(p2sh.address)}
    clauses.append("used = :used")
    values["used"] = used

    async with db.async_session as session:
        query = f"UPDATE proofs SET {', '.join(clauses)} WHERE address = :address"

        await _exec_and_raise(session=session, query=query, values=values, commit=True)


async def store_keyset(db: Database, keyset: WalletKeyset, mint_url: str = None):
    async with db.async_session as session:
        keys, values = _to_values(
            (
                keyset.id,
                mint_url or keyset.mint_url,
                keyset.valid_from or int(time.time()),
                keyset.valid_to or int(time.time()),
                keyset.first_seen or int(time.time()),
                True,
            )
        )
        query = f"""
            INSERT INTO keysets
            (id, mint_url, valid_from, valid_to, first_seen, active)
            VALUES ({keys})
            """

        await _exec_and_raise(session=session, query=query, values=values, commit=True)


async def get_keyset(id: str = "", mint_url: str = "", db: Database = None):
    logger.trace(f"get_keyset({id}, {mint_url}, {db.name}) called")
    clauses = []
    values: dict[str, Any] = {}
    clauses.append("active = :active")
    values["active"] = True

    if id:
        clauses.append("id = :id")
        values["id"] = id

    if mint_url:
        clauses.append("mint_url = :mint_url")
        values["mint_url"] = db.l_proc(mint_url)

    where = ""
    if clauses:
        where = f"WHERE {' AND '.join(clauses)}"

    async with db.async_session as session:
        query = f"SELECT * FROM keysets {where}"

        if mint_url:
            # TODO: this is a dirty hack, fix it. SQLAlchemy has trouble replacing
            # :mint_url with the value of mint_url, and thus, never finds the db entry
            query = query.replace(":mint_url", values["mint_url"])

        c = await _exec_and_raise(session=session, query=query, values=values)
        row = c.fetchone()

        return WalletKeyset(**row._mapping) if row is not None else None


async def store_lightning_invoice(db: Database, invoice: Invoice):
    async with db.async_session as session:
        keys, values = _to_values(
            (
                invoice.amount,
                invoice.pr,
                invoice.hash,
                invoice.preimage,
                invoice.paid,
                invoice.time_created,
                invoice.time_paid,
            )
        )
        query = f"""
            INSERT INTO invoices
            (amount, pr, hash, preimage, paid, time_created, time_paid)
            VALUES ({keys})
            """

        await _exec_and_raise(session=session, query=query, values=values, commit=True)


async def get_lightning_invoice(db: Database, hash: str = None):
    clauses = []
    values: dict[str, Any] = {}
    if hash:
        clauses.append("hash = :hash")
        values["hash"] = hash

    where = ""
    if clauses:
        where = f"WHERE {' AND '.join(clauses)}"

    async with db.async_session as session:
        query = f"SELECT * from invoices {where}"
        cursor = await _exec_and_raise(session=session, query=query, values=values)
        row = cursor.fetchone()

        return Invoice(**row._mapping)


async def get_lightning_invoices(db: Database, paid: bool = None):
    clauses: List[Any] = []
    values: dict[str, Any] = {}

    if paid is not None:
        clauses.append("paid = :paid")
        values["paid"] = paid

    where = ""
    if clauses:
        where = f"WHERE {' AND '.join(clauses)}"

    async with db.async_session as session:
        query = f"SELECT * from invoices {where}"
        cursor = await _exec_and_raise(session=session, query=query, values=values)
        rows = cursor.fetchall()

        return [Invoice(**r._mapping) for r in rows]


async def update_lightning_invoice(
    db: Database, hash: str, paid: bool, time_paid: int = None
):
    clauses = []
    values: dict[str, Any] = {}
    clauses.append("paid = :paid")
    values["paid"] = paid

    if time_paid:
        clauses.append("time_paid = :time_paid")
        values["time_paid"] = time_paid

    async with db.async_session as session:
        query = f"UPDATE invoices SET {', '.join(clauses)} WHERE hash = :hash"
        values["hash"] = hash

        await _exec_and_raise(session=session, query=query, values=values)


async def set_nostr_last_check_timestamp(db: Database, timestamp: int):
    async with db.async_session as session:
        query = ("UPDATE nostr SET last = :last WHERE type = :type",)
        values = ({"last": timestamp, "type": "dm"},)

        await _exec_and_raise(session=session, query=query, values=values, commit=True)


async def get_nostr_last_check_timestamp(db: Database):
    async with db.async_session as session:
        query = "SELECT last from nostr WHERE type = :type"
        values = {"type": "dm"}
        cursor = await _exec_and_raise(session=session, query=query, values=values)
        row = await cursor.fetchone()

        return row[0] if row else None
