import asyncio
import os
from os import listdir
from os.path import isdir, join
from typing import Union

from cashu.core.settings import DEBUG, MINT_URL, VERSION
from fastapi import HTTPException

import app.cashu.constants as c
import app.cashu.exceptions as ce
from app.cashu.models import (
    CashuInfo,
    CashuMint,
    CashuMintInput,
    CashuPayEstimation,
    CashuWallet,
    CashuWalletBalance,
    CashuWalletData,
)
from app.lightning.models import PaymentStatus
from app.lightning.service import send_payment


class CashuService:
    _DEFAULT_WALLET: CashuWallet = None
    _DEFAULT_MINT: CashuMint = None
    _pinned_mint: CashuMint = None
    _pinned_wallet: CashuWallet = None
    _wallets: list[CashuWallet] = []
    _mints: list[CashuMint] = []

    async def init_wallets(self) -> None:
        if len(self._wallets) > 0:
            raise RuntimeError("Wallets are already initialized")

        if not os.path.exists(c.DATA_FOLDER):
            os.makedirs(c.DATA_FOLDER)

        self._pinned_mint = self._DEFAULT_MINT = CashuMint(
            url=c.DEFAULT_MINT_URL, pinned=True, default=True
        )
        self._mints.append(self._pinned_mint)

        wallets = [d for d in listdir(c.DATA_FOLDER) if isdir(join(c.DATA_FOLDER, d))]

        try:
            wallets.remove("mint")
        except ValueError:
            pass

        for wallet_name in wallets:
            wallet = CashuWallet(self._pinned_mint, wallet_name)
            await wallet.initialize()
            self._wallets.append(wallet)
            if wallet.name == c.DEFAULT_WALLET_NAME:
                self._DEFAULT_WALLET = wallet
                self._pinned_wallet = wallet

        if len(wallets) == 0:
            # First run, initialize default wallet
            self._pinned_wallet = self._DEFAULT_WALLET = CashuWallet(
                mint=self._pinned_mint, name=c.DEFAULT_WALLET_NAME
            )
            await self._DEFAULT_WALLET.initialize()
            self._wallets.append(self._DEFAULT_WALLET)

    def info(self) -> CashuInfo:
        return CashuInfo(
            version=VERSION,
            debug=DEBUG,
            default_wallet=c.DEFAULT_WALLET_NAME,
            default_mint=MINT_URL,
        )

    # add mint function
    async def add_mint(self, mint_in: CashuMintInput) -> CashuMint:
        if mint_in.url == c.DEFAULT_MINT_URL:
            raise ce.IsDefaultMintException()

        for m in self._mints:
            if m.url == mint_in.url:
                raise ce.MintExistsException(mint_in.url)

        m = CashuMint(url=mint_in.url)

        # pretend doing a DB operation
        await asyncio.sleep(0.01)

        self._mints.append(m)

        if mint_in.pinned:
            m = self.pin_mint(m.url)

        return m

    async def list_mints(self) -> list[CashuMint]:
        # pretend doing a DB operation
        await asyncio.sleep(0.01)

        return self._mints

    def get_mint(self, mint_name: str) -> CashuMint:
        for m in self._mints:
            if m.url == mint_name:
                return m

        return None

    def pin_mint(self, url: str) -> CashuMint:
        if not url or url == "":
            self._pinned_mint = self._DEFAULT_MINT
            return self._pinned_mint

        for m in self._mints:
            if m.url == url:
                m.pinned = True
                self._pinned_mint = m
                continue

            m.pinned = False

        return self._pinned_mint

    async def add_wallet(self, wallet_name: CashuWalletData):
        if self._resolve_wallet(wallet_name):
            raise ce.WalletExistsException(wallet_name)

        w = CashuWallet(mint=self._pinned_mint, name=wallet_name)
        await w.initialize()
        self._wallets.append(w)
        return w.get_wallet_data_for_client()

    def pin_wallet(self, wallet_name: str) -> str:
        if not wallet_name or wallet_name == "":
            self._pinned_wallet = self._DEFAULT_WALLET
            return self._pinned_wallet.name

        try:
            wallet = self._resolve_wallet(wallet_name)
            self._pinned_wallet = wallet
            return wallet.name
        except HTTPException:
            raise

    def balance(self) -> CashuWalletBalance:

        b = CashuWalletBalance()

        for w in self._wallets:
            b += w.balance_overview

        return b

    async def mint(
        self,
        amount: int,
        mint_name: Union[None, str] = None,
        wallet_name: Union[None, str] = None,
    ) -> bool:
        wallet = self._resolve_wallet(wallet_name)

        if mint_name and not self.get_mint(mint_name=mint_name):
            self.add_mint(mint_in=CashuMintInput(url=mint_name))
            wallet.url = mint_name

        await wallet.load_mint()

        wallet.status()  # TODO: remove me, debug only

        invoice = await wallet.request_mint(amount)

        res = await send_payment(
            pay_req=invoice.pr, timeout_seconds=5, fee_limit_msat=8000
        )

        if res.status == PaymentStatus.SUCCEEDED:
            try:
                await wallet.mint(amount, invoice.hash)
                wallet.status()  # TODO: remove me, debug only
                if mint_name != self._pinned_mint.url:
                    # If it is not the pinned mint, change it back to the pinned one
                    # We assume that the user want to mint one time on this one.
                    wallet.url = self._pinned_mint.url

                return True
            except Exception as e:
                # TODO: cashu wallet lib throws an Exception here =>
                #       submit PR with a more specific exception
                raise HTTPException(status_code=500, detail="Error while minting {e}")

    async def receive(
        self,
        coin: str,
        lock: str,
        mint_name: Union[None, str],
        wallet_name: Union[None, str],
    ) -> CashuWalletBalance:
        wallet = self._resolve_wallet(wallet_name)

        wallet.status()  # TODO: remove me, debug only

        await wallet.receive(coin, lock)

        wallet.status()  # TODO: remove me, debug only

        return wallet.balance_overview

    async def pay(
        self,
        invoice: str,
        mint_name: Union[None, str],
        wallet_name: Union[None, str],
    ):
        wallet = self._resolve_wallet(wallet_name)
        await wallet.load_mint()

        wallet.status()

        res = await self.estimate_pay(invoice, mint_name, wallet_name)

        _, send_proofs = await wallet.split_to_send(wallet.proofs, res.amount)
        await wallet.pay_lightning(send_proofs, invoice)
        wallet.status()

        return wallet.available_balance

    async def estimate_pay(
        self,
        invoice: str,
        mint_name: Union[None, str],
        wallet_name: Union[None, str],
    ) -> CashuPayEstimation:
        wallet = self._resolve_wallet(wallet_name)
        await wallet.load_mint()
        amount, fee = await wallet.get_pay_amount_with_fees(invoice)

        if amount < 1:
            raise ce.ZeroInvoiceException()

        return CashuPayEstimation(
            amount=amount,
            fee=fee,
            balance_ok=wallet.available_balance > amount,
        )

    async def list_wallets(
        self, include_balances: bool = False
    ) -> list[CashuWalletData]:
        wallets_data = []

        for w in self._wallets:
            wallets_data.append(w.get_wallet_data_for_client(include_balances))

        return wallets_data

    async def get_wallet(
        self,
        mint_name: Union[None, str] = None,
        wallet_name: Union[None, str] = None,
        include_balances: bool = False,
    ) -> CashuWalletData:
        wallet = self._resolve_wallet(wallet_name)
        return wallet.get_wallet_data_for_client(include_balances)

    def _resolve_wallet(self, wallet_name: Union[None, str]) -> CashuWallet:
        wallet = self._pinned_wallet

        if wallet_name and len(wallet_name) > 0:
            # User explicitly specified a wallet
            wallet = None
            for w in self._wallets:
                if w.name == wallet_name:
                    wallet = w
                    break

        if not wallet:
            ce.WalletNotFoundException(wallet_name)

        return wallet
