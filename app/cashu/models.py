import base64
import json
from os.path import join
from typing import List

from fastapi import Query
from loguru import logger
from pydantic import BaseModel

import app.cashu.errors as errors
from app.cashu.constants import DATA_FOLDER, DEFAULT_MINT_URL, DEFAULT_WALLET_NAME
from app.external.cashu.core.base import TokenV2, TokenV2Mint
from app.external.cashu.core.helpers import sum_proofs
from app.external.cashu.core.settings import MINT_URL
from app.external.cashu.wallet.crud import get_keyset, get_unused_locks
from app.external.cashu.wallet.wallet import Proof, Wallet
from app.external.cashu.wallet.wallet_helpers import token_from_lnbits_link


# Public
class CashuMintInput(BaseModel):
    url: str = Query(DEFAULT_MINT_URL, description="URL of the mint.")
    pinned: bool = Query(False, description="Whether the mint is pinned.")


class CashuMintKeyInput(BaseModel):
    wallet_name: str = Query(DEFAULT_WALLET_NAME, description="Name of the wallet.")
    url: str = Query(DEFAULT_MINT_URL, description="URL of the mint.")
    key: str = Query(..., description="The keyset id for which to update the data.")
    trusted: bool = Query(..., description="Whether this keyset is to be trusted.")


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


class CashuReceiveResult(BaseModel):
    is_success: bool = Query(
        False, description="Whether the token was received successfully or not."
    )

    sats_received: int = Query(
        0, description="Amount of satoshis received. 0 if the tokens was on error."
    )

    fail_reason: errors.CashuReceiveFailReason = Query(
        None, description="Reason why the token could not be received."
    )

    # Message explaining why the token could not be received.
    fail_message: str = Query(
        None, description="Message explaining why the token could not be received."
    )

    untrusted_mint_url: str = Query(None, description="URL of the untrusted mint.")
    untrusted_mint_keyset: str = Query(
        None, description="Keyset of the untrusted mint."
    )

    @staticmethod
    def from_exception(e: errors.CashuException) -> "CashuReceiveResult":
        if isinstance(e, errors.UntrustedMintException):
            return CashuReceiveResult(
                fail_reason=errors.CashuReceiveFailReason.MINT_UNTRUSTED,
                fail_message=e.message,
                untrusted_mint_url=e.mint_url,
                untrusted_mint_keyset=e.mint_keyset,
            )

        return CashuReceiveResult(fail_reason=e.reason, fail_message=e.message)

    @staticmethod
    def success(sats_received: int) -> "CashuReceiveResult":
        return CashuReceiveResult(success=True, sats_received=sats_received)


# Internal only
class CashuWallet(Wallet):
    def __init__(self, mint: CashuMint, name: str = "no_name") -> None:
        super().__init__(url=mint.url, db=join(DATA_FOLDER, name), name=name)

    @property
    def balance_overview(self) -> CashuWalletBalance:
        return CashuWalletBalance(
            total=self.balance,
            available=self.available_balance,
            tokens=len([p for p in self.proofs if not p.reserved]),
        )

    async def receive(self, token: str, lock: str, trust_mint: bool = False):
        # check for P2SH locks
        script, signature = None, None
        if lock:
            # load the script and signature of this address from the database
            if len(lock.split("P2SH:")) != 2:
                raise errors.CashuException(
                    message="lock has wrong format. Expected P2SH:<address>.",
                    reason=errors.CashuReceiveFailReason.FORMAT_ERROR,
                )

            address_split = lock.split("P2SH:")[1]
            p2shscripts = await get_unused_locks(address_split, db=self.database)

            if len(p2shscripts) != 1:
                raise errors.CashuException(
                    message="lock not found.",
                    reason=errors.CashuReceiveFailReason.LOCK_ERROR,
                )

            script, signature = p2shscripts[0].script, p2shscripts[0].signature

        # deserialize token

        # ----- backwards compatibility -----

        # we support old tokens (< 0.7) without mint information and (W3siaWQ...)
        # new tokens (>= 0.7) with multiple mint support (eyJ0b2...)
        try:
            # backwards compatibility: tokens without mint information
            # supports tokens of the form W3siaWQiOiJH

            # if it's an lnbits https:// link with a token as an argument, special treatment
            token, url = token_from_lnbits_link(token)

            # assume W3siaWQiOiJH.. token
            # next line trows an error if the deserialization with the old format doesn't
            # work and we can assume it's the new format
            proofs = [Proof(**p) for p in json.loads(base64.urlsafe_b64decode(token))]

            # we take the proofs parsed from the old format token and produce a new format token with it
            token = await self._proofs_to_serialized_token_v2(self, proofs, url)
        except:
            pass

        # ----- receive token -----

        # deserialize token
        dtoken = json.loads(base64.urlsafe_b64decode(token))

        # backwards compatibility wallet to wallet < 0.8.0: V2 tokens renamed "tokens" field to "proofs"
        if "tokens" in dtoken:
            dtoken["proofs"] = dtoken.pop("tokens")

        # backwards compatibility wallet to wallet < 0.8.3: V2 tokens got rid of the "MINT_NAME" key in "mints" and renamed "ks" to "ids"
        if "mints" in dtoken and isinstance(dtoken["mints"], dict):
            dtoken["mints"] = list(dtoken["mints"].values())
            for m in dtoken["mints"]:
                m["ids"] = m.pop("ks")

        tokenObj = TokenV2.parse_obj(dtoken)

        if len(tokenObj.proofs) == 0:
            raise errors.CashuException(
                message="no proofs in token",
                reason=errors.CashuReceiveFailReason.PROOF_ERROR,
            )

        includes_mint_info: bool = (
            tokenObj.mints is not None and len(tokenObj.mints) > 0
        )

        # if there is a `mints` field in the token
        # we check whether the token has mints that we don't know yet
        # and ask the user if they want to trust the new mints
        if includes_mint_info:
            # we ask the user to confirm any new mints the tokens may include
            await self._verify_mints(tokenObj, trust_mint)
            # redeem tokens with new wallet instances
            await self._redeem_multimint(tokenObj, script, signature)
            # reload main wallet so the balance updates
            await self.load_proofs()

            return CashuReceiveResult.success(sum_proofs(tokenObj.proofs))

        else:
            # no mint information present, we extract the proofs and use wallet's default mint
            proofs = [Proof(**p) for p in dtoken["proofs"]]
            _, _ = await self.redeem(proofs, script, signature)
            logger.info(f"Received {sum_proofs(proofs)} sats")

            return CashuReceiveResult.success(sum_proofs(proofs))

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

    async def _proofs_to_serialized_token_v2(self, proofs: List[Proof], url: str):
        """
        Ingests list of proofs and produces a serialized TokenV2
        """
        # and add url and keyset id to token
        token: TokenV2 = await self._make_token(proofs, include_mints=False)
        token.mints = []

        # get keysets of proofs
        keysets = list(set([p.id for p in proofs if p.id is not None]))

        # check whether we know the mint urls for these proofs
        for k in keysets:
            ks = await get_keyset(id=k, db=self.database)
            url = ks.mint_url if ks and ks.mint_url else ""

        if not url:
            Exception("mint url not found")

        token.mints.append(TokenV2Mint(url=url, ids=keysets))
        token_serialized = await self._serialize_token_base64(token)
        return token_serialized
