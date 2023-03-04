import base64
import json
import math
import secrets as scrts
import time
import uuid
from itertools import groupby
from typing import Dict, List, Optional

import requests
from loguru import logger

import app.external.cashu.core.b_dhke as b_dhke
import app.external.cashu.core.bolt11 as bolt11
from app.cashu.errors import (
    CashuException,
    CashuReceiveFailReason,
    UntrustedMintException,
)
from app.external.cashu.core.base import (
    BlindedMessage,
    BlindedSignature,
    CheckFeesRequest,
    CheckSpendableRequest,
    CheckSpendableResponse,
    GetMintResponse,
    Invoice,
    KeysetsResponse,
    P2SHScript,
    PostMeltRequest,
    PostMintRequest,
    PostMintResponse,
    PostMintResponseLegacy,
    PostSplitRequest,
    Proof,
    TokenV2,
    TokenV2Mint,
    WalletKeyset,
)
from app.external.cashu.core.bolt11 import Invoice as InvoiceBolt11
from app.external.cashu.core.db import Database
from app.external.cashu.core.helpers import sum_proofs
from app.external.cashu.core.script import (
    step0_carol_checksig_redeemscrip,
    step0_carol_privkey,
    step1_carol_create_p2sh_address,
    step2_carol_sign_tx,
)
from app.external.cashu.core.secp import PublicKey
from app.external.cashu.core.settings import DEBUG, SOCKS_HOST, SOCKS_PORT, TOR, VERSION
from app.external.cashu.core.split import amount_split
from app.external.cashu.tor.tor import TorProxy
from app.external.cashu.wallet.crud import (
    get_keyset,
    get_proofs,
    invalidate_proof,
    secret_used,
    store_keyset,
    store_lightning_invoice,
    store_p2sh,
    store_proof,
    update_lightning_invoice,
    update_proof_reserved,
)


def async_set_requests(func):
    """
    Decorator that wraps around any async class method of LedgerAPI that makes
    API calls. Sets some HTTP headers and starts a Tor instance if none is
    already running and  and sets local proxy to use it.
    """

    async def wrapper(self, *args, **kwargs):
        self.s.headers.update({"Client-version": VERSION})
        if DEBUG:
            self.s.verify = False
        socks_host, socks_port = None, None
        if TOR and TorProxy().check_platform():
            self.tor = TorProxy(timeout=True)
            self.tor.run_daemon(verbose=True)
            socks_host, socks_port = "localhost", 9050
        else:
            socks_host, socks_port = SOCKS_HOST, SOCKS_PORT

        if socks_host and socks_port:
            proxies = {
                "http": f"socks5://{socks_host}:{socks_port}",
                "https": f"socks5://{socks_host}:{socks_port}",
            }
            self.s.proxies.update(proxies)
            self.s.headers.update({"User-Agent": scrts.token_urlsafe(8)})

        return await func(self, *args, **kwargs)

    return wrapper


class LedgerAPI:
    keys: Dict[int, PublicKey]
    keyset: str
    tor: TorProxy
    s: requests.Session

    _db: Database
    _initialized: bool = False

    @async_set_requests
    async def _init_s(self):
        """Dummy function that can be called from outside to use LedgerAPI.s"""
        return

    def __init__(self, url):
        self.url = url
        self.s = requests.Session()

    def _construct_proofs(
        self, promises: List[BlindedSignature], secrets: List[str], rs: List[str]
    ):
        """Returns proofs of promise from promises. Wants secrets and blinding factors rs."""
        proofs = []
        for promise, secret, r in zip(promises, secrets, rs):
            C_ = PublicKey(bytes.fromhex(promise.C_), raw=True)
            C = b_dhke.step3_alice(C_, r, self.keys[promise.amount])
            proof = Proof(
                id=self.keyset_id,
                amount=promise.amount,
                C=C.serialize().hex(),
                secret=secret,
            )
            proofs.append(proof)
        return proofs

    async def initialize(self):
        if self._initialized:
            raise RuntimeError("Cashu wallet is already initialized")

        await self._db.initialize()
        await self.load_proofs()

        self._initialized = True

    @property
    def database(self) -> Database:
        if not self._initialized:
            raise RuntimeError("Cashu wallet is not initialized")

        return self._db

    @staticmethod
    def raise_on_error(resp_dict):
        if "error" in resp_dict:
            raise Exception("Mint Error: {}".format(resp_dict["error"]))

    @staticmethod
    def _generate_secret(randombits=128):
        """Returns base64 encoded random string."""
        return scrts.token_urlsafe(randombits // 8)

    async def _load_mint(self, keyset_id: str = ""):
        """
        Loads the public keys of the mint. Either gets the keys for the specified
        `keyset_id` or loads the most recent one from the mint.
        Gets and the active keyset ids of the mint and stores in `self.keysets`.
        """
        assert len(
            self.url
        ), "Ledger not initialized correctly: mint URL not specified yet. "

        if keyset_id:
            # get requested keyset
            keyset = await self._get_keyset(self.url, keyset_id)
        else:
            # get current keyset
            keyset = await self._get_keys(self.url)

        # store current keyset
        assert keyset.public_keys
        assert keyset.id
        assert len(keyset.public_keys) > 0, "did not receive keys from mint."

        # check if current keyset is in db
        keyset_local: Optional[WalletKeyset] = await get_keyset(keyset.id, db=self._db)
        if keyset_local is None:
            await store_keyset(keyset=keyset, db=self._db)

        # get all active keysets of this mint
        mint_keysets = []
        try:
            keysets_resp = await self._get_keyset_ids(self.url)
            mint_keysets = keysets_resp["keysets"]
            # store active keysets
        except:
            pass
        self.keysets = mint_keysets if len(mint_keysets) else [keyset.id]

        logger.debug(f"Mint keysets: {self.keysets}")
        logger.debug(f"Current mint keyset: {keyset.id}")

        self.keys = keyset.public_keys
        self.keyset_id = keyset.id

    @staticmethod
    def _construct_outputs(amounts: List[int], secrets: List[str]):
        """Takes a list of amounts and secrets and returns outputs.
        Outputs are blinded messages `outputs` and blinding factors `rs`"""
        assert len(amounts) == len(
            secrets
        ), f"len(amounts)={len(amounts)} not equal to len(secrets)={len(secrets)}"
        outputs: List[BlindedMessage] = []
        rs = []
        for secret, amount in zip(secrets, amounts):
            B_, r = b_dhke.step1_alice(secret)
            rs.append(r)
            output: BlindedMessage = BlindedMessage(
                amount=amount, B_=B_.serialize().hex()
            )
            outputs.append(output)
        return outputs, rs

    async def _check_used_secrets(self, secrets):
        for s in secrets:
            if await secret_used(secret=s, db=self._db):
                raise Exception(f"secret already used: {s}")

    def generate_secrets(self, secret, n):
        """`secret` is the base string that will be tweaked n times"""
        if len(secret.split("P2SH:")) == 2:
            return [f"{secret}:{self._generate_secret()}" for i in range(n)]
        return [f"{i}:{secret}" for i in range(n)]

    """
    ENDPOINTS
    """

    @async_set_requests
    async def _get_keys(self, url: str):
        resp = self.s.get(
            url + "/keys",
        )
        resp.raise_for_status()
        keys = resp.json()
        assert len(keys), Exception("did not receive any keys")
        keyset_keys = {
            int(amt): PublicKey(bytes.fromhex(val), raw=True)
            for amt, val in keys.items()
        }
        keyset = WalletKeyset(public_keys=keyset_keys, mint_url=url)
        return keyset

    @async_set_requests
    async def _get_keyset(self, url: str, keyset_id: str):
        """
        keyset_id is base64, needs to be urlsafe-encoded.
        """
        keyset_id_urlsafe = keyset_id.replace("+", "-").replace("/", "_")
        resp = self.s.get(
            url + f"/keys/{keyset_id_urlsafe}",
        )
        resp.raise_for_status()
        keys = resp.json()
        assert len(keys), Exception("did not receive any keys")
        keyset_keys = {
            int(amt): PublicKey(bytes.fromhex(val), raw=True)
            for amt, val in keys.items()
        }
        keyset = WalletKeyset(public_keys=keyset_keys, mint_url=url)
        return keyset

    @async_set_requests
    async def _get_keyset_ids(self, url: str):
        resp = self.s.get(
            url + "/keysets",
        )
        resp.raise_for_status()
        keysets_dict = resp.json()
        keysets = KeysetsResponse.parse_obj(keysets_dict)
        assert len(keysets.keysets), Exception("did not receive any keysets")
        return keysets.dict()

    @async_set_requests
    async def request_mint(self, amount):
        """Requests a mint from the server and returns Lightning invoice."""
        resp = self.s.get(self.url + "/mint", params={"amount": amount})
        resp.raise_for_status()
        return_dict = resp.json()
        self.raise_on_error(return_dict)
        mint_response = GetMintResponse.parse_obj(return_dict)
        return Invoice(amount=amount, pr=mint_response.pr, hash=mint_response.hash)

    @async_set_requests
    async def mint(self, amounts, payment_hash=None):
        """Mints new coins and returns a proof of promise."""
        secrets = [self._generate_secret() for s in range(len(amounts))]
        await self._check_used_secrets(secrets)
        outputs, rs = self._construct_outputs(amounts, secrets)
        outputs_payload = PostMintRequest(outputs=outputs)
        resp = self.s.post(
            self.url + "/mint",
            json=outputs_payload.dict(),
            params={"payment_hash": payment_hash},
        )
        resp.raise_for_status()
        response_dict = resp.json()
        self.raise_on_error(response_dict)
        try:
            # backwards compatibility: parse promises < 0.8.0 with no "promises" field
            promises = PostMintResponseLegacy.parse_obj(response_dict).__root__
        except:
            promises = PostMintResponse.parse_obj(response_dict).promises

        return self._construct_proofs(promises, secrets, rs)

    @async_set_requests
    async def split(self, proofs, amount, scnd_secret: Optional[str] = None):
        """Consume proofs and create new promises based on amount split.
        If scnd_secret is None, random secrets will be generated for the tokens to keep (frst_outputs)
        and the promises to send (scnd_outputs).

        If scnd_secret is provided, the wallet will create blinded secrets with those to attach a
        predefined spending condition to the tokens they want to send."""

        total = sum_proofs(proofs)
        frst_amt, scnd_amt = total - amount, amount
        frst_outputs = amount_split(frst_amt)
        scnd_outputs = amount_split(scnd_amt)

        amounts = frst_outputs + scnd_outputs
        if scnd_secret is None:
            secrets = [self._generate_secret() for _ in range(len(amounts))]
        else:
            scnd_secrets = self.generate_secrets(scnd_secret, len(scnd_outputs))
            logger.debug(f"Creating proofs with custom secrets: {scnd_secrets}")
            assert len(scnd_secrets) == len(
                scnd_outputs
            ), "number of scnd_secrets does not match number of ouptus."
            # append predefined secrets (to send) to random secrets (to keep)
            secrets = [
                self._generate_secret() for s in range(len(frst_outputs))
            ] + scnd_secrets

        assert len(secrets) == len(
            amounts
        ), "number of secrets does not match number of outputs"
        await self._check_used_secrets(secrets)
        outputs, rs = self._construct_outputs(amounts, secrets)
        split_payload = PostSplitRequest(proofs=proofs, amount=amount, outputs=outputs)

        # construct payload
        def _split_request_include_fields(proofs):
            """strips away fields from the model that aren't necessary for the /split"""
            proofs_include = {"id", "amount", "secret", "C", "script"}
            return {
                "amount": ...,
                "outputs": ...,
                "proofs": {i: proofs_include for i in range(len(proofs))},
            }

        resp = self.s.post(
            self.url + "/split",
            json=split_payload.dict(include=_split_request_include_fields(proofs)),  # type: ignore
        )
        resp.raise_for_status()
        promises_dict = resp.json()
        self.raise_on_error(promises_dict)

        promises_fst = [BlindedSignature(**p) for p in promises_dict["fst"]]
        promises_snd = [BlindedSignature(**p) for p in promises_dict["snd"]]
        # Construct proofs from promises (i.e., unblind signatures)
        frst_proofs = self._construct_proofs(
            promises_fst, secrets[: len(promises_fst)], rs[: len(promises_fst)]
        )
        scnd_proofs = self._construct_proofs(
            promises_snd, secrets[len(promises_fst) :], rs[len(promises_fst) :]
        )

        return frst_proofs, scnd_proofs

    @async_set_requests
    async def check_spendable(self, proofs: List[Proof]):
        """
        Checks whether the secrets in proofs are already spent or not and returns a list of booleans.
        """
        payload = CheckSpendableRequest(proofs=proofs)

        def _check_spendable_include_fields(proofs):
            """strips away fields from the model that aren't necessary for the /split"""
            return {
                "proofs": {i: {"secret"} for i in range(len(proofs))},
            }

        resp = self.s.post(
            self.url + "/check",
            json=payload.dict(include=_check_spendable_include_fields(proofs)),  # type: ignore
        )
        resp.raise_for_status()
        return_dict = resp.json()
        self.raise_on_error(return_dict)
        spendable = CheckSpendableResponse.parse_obj(return_dict)
        return spendable

    @async_set_requests
    async def check_fees(self, payment_request: str):
        """Checks whether the Lightning payment is internal."""
        payload = CheckFeesRequest(pr=payment_request)
        resp = self.s.post(
            self.url + "/checkfees",
            json=payload.dict(),
        )
        resp.raise_for_status()
        return_dict = resp.json()
        self.raise_on_error(return_dict)
        return return_dict

    @async_set_requests
    async def pay_lightning(self, proofs: List[Proof], invoice: str):
        """
        Accepts proofs and a lightning invoice to pay in exchange.
        """
        payload = PostMeltRequest(proofs=proofs, pr=invoice)

        def _meltrequest_include_fields(proofs):
            """strips away fields from the model that aren't necessary for the /melt"""
            proofs_include = {"id", "amount", "secret", "C", "script"}
            return {
                "amount": ...,
                "pr": ...,
                "proofs": {i: proofs_include for i in range(len(proofs))},
            }

        resp = self.s.post(
            self.url + "/melt",
            json=payload.dict(include=_meltrequest_include_fields(proofs)),  # type: ignore
        )
        resp.raise_for_status()
        return_dict = resp.json()
        self.raise_on_error(return_dict)
        return return_dict


class Wallet(LedgerAPI):
    """Minimal wallet wrapper."""

    def __init__(self, url: str, db: str, name: str = "no_name"):
        super().__init__(url)
        self._db = Database(name)
        self.proofs: List[Proof] = []
        self.name = name
        logger.debug(f"Wallet initialized with mint URL {url}")

    # ---------- API ----------

    async def load_mint(self, keyset_id: str = ""):
        await super()._load_mint(keyset_id)

    async def load_proofs(self):
        self.proofs = await get_proofs(db=self._db)

    async def request_mint(self, amount):
        invoice = await super().request_mint(amount)
        invoice.time_created = int(time.time())
        await store_lightning_invoice(db=self._db, invoice=invoice)

        return invoice

    async def mint(self, amount: int, payment_hash: Optional[str] = None):
        split = amount_split(amount)
        proofs = await super().mint(split, payment_hash)
        if proofs == []:
            raise Exception("received no proofs.")
        await self._store_proofs(proofs)
        if payment_hash:
            await update_lightning_invoice(
                db=self._db, hash=payment_hash, paid=True, time_paid=int(time.time())
            )
        self.proofs += proofs

        return proofs

    async def redeem(
        self,
        proofs: List[Proof],
        scnd_script: Optional[str] = None,
        scnd_siganture: Optional[str] = None,
    ):
        if scnd_script and scnd_siganture:
            logger.debug(f"Unlock script: {scnd_script}")
            # attach unlock scripts to proofs
            for p in proofs:
                p.script = P2SHScript(script=scnd_script, signature=scnd_siganture)

        return await self.split(proofs, sum_proofs(proofs))

    async def split(
        self,
        proofs: List[Proof],
        amount: int,
        scnd_secret: Optional[str] = None,
    ):
        assert len(proofs) > 0, ValueError("no proofs provided.")
        frst_proofs, scnd_proofs = await super().split(proofs, amount, scnd_secret)
        if len(frst_proofs) == 0 and len(scnd_proofs) == 0:
            raise Exception("received no splits.")
        used_secrets = [p["secret"] for p in proofs]
        self.proofs = list(
            filter(lambda p: p["secret"] not in used_secrets, self.proofs)
        )
        self.proofs += frst_proofs + scnd_proofs
        await self._store_proofs(frst_proofs + scnd_proofs)

        # TODO: batch this db call
        for proof in proofs:
            await invalidate_proof(proof, db=self._db)

        return frst_proofs, scnd_proofs

    async def pay_lightning(self, proofs: List[Proof], invoice: str):
        """Pays a lightning invoice"""
        status = await super().pay_lightning(proofs, invoice)
        if status["paid"] == True:
            await self.invalidate(proofs)
            invoice_obj = Invoice(
                amount=-sum_proofs(proofs),
                pr=invoice,
                preimage=status.get("preimage"),
                paid=True,
                time_paid=time.time(),
            )
            await store_lightning_invoice(db=self._db, invoice=invoice_obj)
        else:
            raise Exception("could not pay invoice.")

        return status["paid"]

    async def check_spendable(self, proofs):
        return await super().check_spendable(proofs)

    # ---------- TOKEN MECHANICS ----------

    async def _store_proofs(self, proofs):
        # TODO: batch this db call
        for proof in proofs:
            await store_proof(proof=proof, db=self._db)

    @staticmethod
    def _get_proofs_per_keyset(proofs: List[Proof]):
        return {key: list(group) for key, group in groupby(proofs, lambda p: p.id)}

    async def _get_proofs_per_minturl(self, proofs: List[Proof]):
        ret = {}
        for id in set([p.id for p in proofs]):
            if id is None:
                continue
            keyset_crud = await get_keyset(id=id, db=self._db)
            assert keyset_crud is not None, "keyset not found"
            keyset: WalletKeyset = keyset_crud
            if keyset.mint_url not in ret:
                ret[keyset.mint_url] = [p for p in proofs if p.id == id]
            else:
                ret[keyset.mint_url].extend([p for p in proofs if p.id == id])

        return ret

    async def _make_token(self, proofs: List[Proof], include_mints=True):
        """
        Takes list of proofs and produces a TokenV2 by looking up
        the keyset id and mint URLs from the database.
        """
        # build token
        token = TokenV2(proofs=proofs)
        # add mint information to the token, if requested
        if include_mints:
            # dummy object to hold information about the mint
            mints: Dict[str, TokenV2Mint] = {}
            # dummy object to hold all keyset id's we need to fetch from the db later
            keysets: List[str] = []
            # iterate through all proofs and remember their keyset ids for the next step
            for proof in proofs:
                if proof.id:
                    keysets.append(proof.id)
            # iterate through unique keyset ids
            for id in set(keysets):
                # load the keyset from the db
                keyset = await get_keyset(id=id, db=self._db)
                if keyset and keyset.mint_url and keyset.id:
                    # we group all mints according to URL
                    if keyset.mint_url not in mints:
                        mints[keyset.mint_url] = TokenV2Mint(
                            url=keyset.mint_url,
                            ids=[keyset.id],
                        )
                    else:
                        # if a mint URL has multiple keysets, append to the already existing list
                        mints[keyset.mint_url].ids.append(keyset.id)
            if len(mints) > 0:
                # add mints grouped by url to the token
                token.mints = list(mints.values())

        return token

    async def _serialize_token_base64(self, token: TokenV2):
        """
        Takes a TokenV2 and serializes it in urlsafe_base64.
        """
        # encode the token as a base64 string
        token_base64 = base64.urlsafe_b64encode(
            json.dumps(token.to_dict()).encode()
        ).decode()

        return token_base64

    async def serialize_proofs(
        self, proofs: List[Proof], include_mints=True, legacy=False
    ):
        """
        Produces sharable token with proofs and mint information.
        """

        if legacy:
            proofs_serialized = [p.to_dict() for p in proofs]
            return base64.urlsafe_b64encode(
                json.dumps(proofs_serialized).encode()
            ).decode()

        token = await self._make_token(proofs, include_mints)

        return await self._serialize_token_base64(token)

    async def _select_proofs_to_send(self, proofs: List[Proof], amount_to_send: int):
        """
        Selects proofs that can be used with the current mint.
        Chooses:
        1) Proofs that are not marked as reserved
        2) Proofs that have a keyset id that is in self.keysets (active keysets of mint) - !!! optional for backwards compatibility with legacy clients
        """
        # select proofs that are in the active keysets of the mint
        proofs = [
            p for p in proofs if p.id in self.keysets or not p.id
        ]  # "or not p.id" is for backwards compatibility with proofs without a keyset id
        # select proofs that are not reserved
        proofs = [p for p in proofs if not p.reserved]
        # check that enough spendable proofs exist
        if sum_proofs(proofs) < amount_to_send:
            raise Exception("balance too low.")

        # coinselect based on amount to send
        sorted_proofs = sorted(proofs, key=lambda p: p.amount)
        send_proofs: List[Proof] = []
        while sum_proofs(send_proofs) < amount_to_send:
            send_proofs.append(sorted_proofs[len(send_proofs)])

        return send_proofs

    async def set_reserved(self, proofs: List[Proof], reserved: bool):
        """Mark a proof as reserved to avoid reuse or delete marking."""
        uuid_str = str(uuid.uuid1())
        for proof in proofs:
            proof.reserved = True
            # TODO: batch this db call
            await update_proof_reserved(
                proof, reserved=reserved, send_id=uuid_str, db=self._db
            )

    async def invalidate(self, proofs):
        """Invalidates all spendable tokens supplied in proofs."""
        spendables = await self.check_spendable(proofs)
        invalidated_proofs = []
        for i, spendable in enumerate(spendables.spendable):
            # TODO: batch this db call
            if not spendable:
                invalidated_proofs.append(proofs[i])
                await invalidate_proof(proofs[i], db=self._db)
        invalidate_secrets = [p["secret"] for p in invalidated_proofs]
        self.proofs = list(
            filter(lambda p: p["secret"] not in invalidate_secrets, self.proofs)
        )

    # ---------- TRANSACTION HELPERS ----------

    async def get_pay_amount_with_fees(self, invoice: str):
        """
        Decodes the amount from a Lightning invoice and returns the
        total amount (amount+fees) to be paid.
        """
        decoded_invoice: InvoiceBolt11 = bolt11.decode(invoice)
        # check if it's an internal payment
        fees = int((await self.check_fees(invoice))["fee"])
        amount = math.ceil((decoded_invoice.amount_msat + fees * 1000) / 1000)  # 1% fee

        return amount, fees

    async def split_to_pay(self, invoice: str):
        """
        Splits proofs such that a Lightning invoice can be paid.
        """
        amount, _ = await self.get_pay_amount_with_fees(invoice)
        # TODO: fix mypy asyncio return multiple values
        _, send_proofs = await self.split_to_send(self.proofs, amount)  # type: ignore

        return send_proofs

    async def split_to_send(
        self,
        proofs: List[Proof],
        amount,
        scnd_secret: Optional[str] = None,
        set_reserved: bool = False,
    ):
        """Like self.split but only considers non-reserved tokens."""
        if scnd_secret:
            logger.debug(f"Spending conditions: {scnd_secret}")
        spendable_proofs = await self._select_proofs_to_send(proofs, amount)

        keep_proofs, send_proofs = await self.split(
            [p for p in spendable_proofs if not p.reserved], amount, scnd_secret
        )
        if set_reserved:
            await self.set_reserved(send_proofs, reserved=True)

        return keep_proofs, send_proofs

    # ---------- P2SH ----------

    async def create_p2sh_lock(self):
        alice_privkey = step0_carol_privkey()
        txin_redeemScript = step0_carol_checksig_redeemscrip(alice_privkey.pub)
        txin_p2sh_address = step1_carol_create_p2sh_address(txin_redeemScript)
        txin_signature = step2_carol_sign_tx(txin_redeemScript, alice_privkey).scriptSig
        txin_redeemScript_b64 = base64.urlsafe_b64encode(txin_redeemScript).decode()
        txin_signature_b64 = base64.urlsafe_b64encode(txin_signature).decode()
        p2shScript = P2SHScript(
            script=txin_redeemScript_b64,
            signature=txin_signature_b64,
            address=str(txin_p2sh_address),
        )
        await store_p2sh(p2shScript, db=self._db)

        return p2shScript

    # ---------- BALANCE CHECKS ----------

    @property
    def balance(self):
        return sum_proofs(self.proofs)

    @property
    def available_balance(self):
        return sum_proofs([p for p in self.proofs if not p.reserved])

    def status(self):
        # print(
        #     f"Balance: {self.balance} sat (available: {self.available_balance} sat in {len([p for p in self.proofs if not p.reserved])} tokens)"
        # )
        print(f"Balance: {self.available_balance} sat")

    def balance_per_keyset(self):
        return {
            key: {
                "balance": sum_proofs(proofs),
                "available": sum_proofs([p for p in proofs if not p.reserved]),
            }
            for key, proofs in self._get_proofs_per_keyset(self.proofs).items()
        }

    async def balance_per_minturl(self):
        balances = await self._get_proofs_per_minturl(self.proofs)
        balances_return = {
            key: {
                "balance": sum_proofs(proofs),
                "available": sum_proofs([p for p in proofs if not p.reserved]),
            }
            for key, proofs in balances.items()
        }

        return dict(sorted(balances_return.items(), key=lambda item: item[1]["available"], reverse=True))  # type: ignore

    def proof_amounts(self):
        return [p["amount"] for p in sorted(self.proofs, key=lambda p: p["amount"])]

    async def _verify_mints(self, token: TokenV2, trust_mints: bool = False):
        """
        A helper function that iterates through all mints in the token and if it has
        not been encountered before, asks the user to confirm.

        It will instantiate a Wallet with each keyset and check whether the mint supports it.
        It will then get the keys for that keyset from the mint and check whether the keyset id is correct.
        """

        if token.mints is None:
            return

        proofs_keysets = set([p.id for p in token.proofs])

        logger.debug(f"Verifying mints for wallet {self.name}")
        for mint in token.mints:
            for keyset in set([id for id in mint.ids if id in proofs_keysets]):
                mint_keysets = await self._get_keyset_ids(mint.url)

                if not keyset in mint_keysets["keysets"]:
                    raise CashuException(
                        message="Mint does not have this keyset.",
                        reason=CashuReceiveFailReason.MINT_KEYSET_MISMATCH,
                    )

                # we validate the keyset id by fetching the keys from
                # the mint and computing the id locally
                mint_keyset = await self._get_keyset(mint.url, keyset)

                if keyset != mint_keyset.id:
                    raise CashuException(
                        message="keyset not valid.",
                        reason=CashuReceiveFailReason.MINT_KEYSET_INVALID,
                    )

                if trust_mints:
                    continue

                # we check the db whether we know this mint already and ask the user if not
                mint_keysets = await get_keyset(mint_url=mint.url, db=self.database)

                if mint_keysets is None:
                    # we encountered a new mint and ask for a user confirmation
                    logger.debug(
                        f"Encountered untrusted mint {mint.url} with keyset {mint_keyset.id}"
                    )

                    raise UntrustedMintException(mint_url=mint.url, mint_keyset=keyset)

    async def _redeem_multimint(self, token: TokenV2, script, signature):
        """
        Helper function to iterate thruogh a token with multiple mints and redeem them from
        these mints one keyset at a time.
        """
        # we get the mint information in the token and load the keys of each mint
        # we then redeem the tokens for each keyset individually
        if token.mints is None:
            return

        proofs_keysets = set([p.id for p in token.proofs])

        for mint in token.mints:
            for keyset in set([id for id in mint.ids if id in proofs_keysets]):
                logger.debug(f"Redeeming tokens from keyset {keyset}")
                await self.load_mint(keyset_id=keyset)

                # redeem proofs of this keyset
                redeem_proofs = [p for p in token.proofs if p.id == keyset]
                _, _ = await self.redeem(
                    redeem_proofs, scnd_script=script, scnd_siganture=signature
                )

                logger.trace(f"Received {sum_proofs(redeem_proofs)} sats")
