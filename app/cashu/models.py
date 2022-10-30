import base64
import json
from os.path import join

from cashu.core.migrations import migrate_databases
from cashu.wallet import migrations
from cashu.wallet.crud import get_unused_locks
from cashu.wallet.wallet import Proof, Wallet
from fastapi import Query
from pydantic import BaseModel

import app.cashu.exceptions as ce
from app.cashu.constants import DATA_FOLDER


# Public
class CashuMintInput(BaseModel):
    url: str = Query("http://localhost:3338", description="URL of the mint.")
    pinned: bool = Query(False, description="Whether the mint is pinned.")


class CashuMint(CashuMintInput):
    default: bool = Query(False, description="Whether the mint is the system default.")


class CashuInfo(BaseModel):
    version: str = Query(..., description="Cashu library version")
    debug: bool = Query(
        ..., description="Whether Cashu is running in debug mode or not."
    )
    default_wallet: str = Query(..., description="Default Cashu wallet name")
    default_mint: str = Query(..., description="Default Cashu mint server URL")


class CashuPayEstimation(BaseModel):
    amount: int = Query(..., description="Amount to pay in satoshis")
    fee: int = Query(..., description="Fee to pay in satoshis")
    balance_ok: bool = Query(..., description="Whether the balance is sufficient")


class CashuWalletBalance(BaseModel):
    total: int = Query(0, description="Total cashu wallet balance")
    available: int = Query(0, description="Available cashu wallet balance")
    tokens: int = Query(0, description="Number of tokens in the cashu wallet")

    def __add__(self, o):
        return CashuWalletBalance(
            total=self.total + o.total,
            available=self.available + o.available,
            tokens=self.tokens + o.tokens,
        )

    def __sub__(self, o):
        return CashuWalletBalance(
            total=self.total - o.total,
            available=self.available - o.available,
            tokens=self.tokens - o.tokens,
        )


class CashuMintBalance(BaseModel):
    mint: str = Query(None, description="Mint server URL")
    total: int = Query(..., description="Total cashu wallet balance for this mint")
    available: int = Query(
        ..., description="Available cashu wallet balance for this mint"
    )
    tokens: int = Query(
        ..., description="Number of tokens in the cashu wallet for this mint"
    )


class CashuWalletData(BaseModel):
    name: str
    balance: CashuWalletBalance = Query(
        ..., description="Total cashu wallet balance. This includes all mints"
    )
    balances_per_mint: list[CashuMintBalance]


# Internal only
class CashuWallet(Wallet):
    initialized: bool = False

    def __init__(self, mint: CashuMint, name: str = "no_name") -> None:
        super().__init__(url=mint.url, db=join(DATA_FOLDER, name), name=name)

    async def initialize(self):
        if self.initialized:
            raise RuntimeError("Cashu wallet is already initialized")

        await migrate_databases(self.db, migrations)
        await self.load_proofs()

    @property
    def balance_overview(self) -> CashuWalletBalance:
        return CashuWalletBalance(
            total=self.balance,
            available=self.available_balance,
            tokens=len([p for p in self.proofs if not p.reserved]),
        )

    async def receive(self, coin: str, lock: str):
        await super().load_mint()

        script, signature = None, None
        if lock:
            # load the script and signature of this address from the database
            if len(lock.split("P2SH:")) != 2:
                raise ce.LockFormatException()

            address_split = lock.split("P2SH:")[1]
            p2sh_scripts = await get_unused_locks(address_split, db=self.db)

            if len(p2sh_scripts) == 0:
                raise ce.LockNotFoundException()

            script = p2sh_scripts[0].script
            signature = p2sh_scripts[0].signature
        try:
            proofs = [Proof(**p) for p in json.loads(base64.urlsafe_b64decode(coin))]
            _, _ = await self.redeem(
                proofs, scnd_script=script, scnd_siganture=signature
            )
        except Exception as e:
            if "Mint Error: tokens already spent. Secret:" in e.args[0]:
                raise ce.TokensSpentException(secret=e.args[0].split("Secret:")[1])

            raise

    def get_wallet_data_for_client(
        self, include_mint_balances: bool = False
    ) -> CashuWalletData:
        balances = []

        if include_mint_balances:
            balances.append(
                CashuMintBalance(
                    mint=self.url,
                    total=self.balance,
                    available=self.available_balance,
                    tokens=len([p for p in self.proofs if not p.reserved]),
                )
            )

        return CashuWalletData(
            name=self.name,
            balance=self.balance_overview,
            balances_per_mint=balances,
        )
