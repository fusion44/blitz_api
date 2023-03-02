import os
import urllib.parse

from app.external.cashu.core.settings import CASHU_DIR, MINT_HOST
from app.external.cashu.wallet.crud import get_keyset
from app.external.cashu.wallet.wallet import Wallet


async def print_mint_balances(wallet: Wallet, show_mints=False):
    """
    Helper function that prints the balances for each mint URL that we have tokens from.
    """
    # get balances per mint
    mint_balances = await wallet.balance_per_minturl()

    # if we have a balance on a non-default mint, we show its URL
    keysets = [k for k, v in wallet.balance_per_keyset().items()]
    for k in keysets:
        ks = await get_keyset(id=str(k), db=wallet.database)
        if ks and ks.mint_url != MINT_HOST:
            show_mints = True

    # or we have a balance on more than one mint
    # show balances per mint
    if len(mint_balances) > 1 or show_mints:
        print(f"You have balances in {len(mint_balances)} mints:")
        print("")
        for i, (k, v) in enumerate(mint_balances.items()):
            print(
                f"Mint {i+1}: Balance: {v['available']} sat (pending: {v['balance']-v['available']} sat) URL: {k}"
            )
        print("")


async def get_mint_wallet(wallet: Wallet, wallet_name: str):
    """
    Helper function that asks the user for an input to select which mint they want to load.
    Useful for selecting the mint that the user wants to send tokens from.
    """
    await wallet.load_mint()

    mint_balances = await wallet.balance_per_minturl()

    if len(mint_balances) > 1:
        await print_mint_balances(wallet, show_mints=True)

        mint_nr_str = (
            input(f"Select mint [1-{len(mint_balances)}, press enter for default 1]: ")
            or "1"
        )
        if not mint_nr_str.isdigit():
            raise Exception("invalid input.")
        mint_nr = int(mint_nr_str)
    else:
        mint_nr = 1

    mint_url = list(mint_balances.keys())[mint_nr - 1]

    # load this mint_url into a wallet
    mint_wallet = Wallet(mint_url, os.path.join(CASHU_DIR, wallet_name))
    mint_keysets: WalletKeyset = await get_keyset(mint_url=mint_url, db=mint_wallet.database)  # type: ignore

    # load the keys
    assert mint_keysets.id
    await mint_wallet.load_mint(keyset_id=mint_keysets.id)

    return mint_wallet


# LNbits token link parsing
# can extract mint URL from LNbits token links like:
# https://lnbits.server/cashu/wallet?mint_id=aMintId&recv_token=W3siaWQiOiJHY2...
def token_from_lnbits_link(link):
    url, token = "", ""
    if len(link.split("&recv_token=")) == 2:
        # extract URL params
        params = urllib.parse.parse_qs(link.split("?")[1])
        # extract URL
        if "mint_id" in params:
            url = (
                link.split("?")[0].split("/wallet")[0]
                + "/api/v1/"
                + params["mint_id"][0]
            )
        # extract token
        token = params["recv_token"][0]
        return token, url
    else:
        return link, ""


# async def send_nostr(ctx: Context, amount: int, pubkey: str, verbose: bool, yes: bool):
#     """
#     Sends tokens via nostr.
#     """
#     # load a wallet for the chosen mint
#     wallet = await get_mint_wallet(ctx)
#     await wallet.load_proofs()
#     _, send_proofs = await wallet.split_to_send(
#         wallet.proofs, amount, set_reserved=True
#     )
#     token = await wallet.serialize_proofs(send_proofs)

#     print("")
#     print(token)

#     if not yes:
#         print("")
#         click.confirm(
#             f"Send {amount} sat to nostr pubkey {pubkey}?",
#             abort=True,
#             default=True,
#         )

#     # we only use ephemeral private keys for sending
#     client = NostrClient(relays=NOSTR_RELAYS)
#     if verbose:
#         print(f"Your ephemeral nostr private key: {client.private_key.bech32()}")

#     if pubkey.startswith("npub"):
#         pubkey_to = PublicKey().from_npub(pubkey)
#     else:
#         pubkey_to = PublicKey(bytes.fromhex(pubkey))

#     client.dm(token, pubkey_to)
#     print(f"Token sent to {pubkey}")
#     client.close()


# async def receive_nostr(ctx: Context, verbose: bool):
#     if NOSTR_PRIVATE_KEY is None:
#         print(
#             "Warning: No nostr private key set! You don't have NOSTR_PRIVATE_KEY set in your .env file. I will create a random private key for this session but I will not remember it."
#         )
#         print("")
#     client = NostrClient(private_key=NOSTR_PRIVATE_KEY, relays=NOSTR_RELAYS)
#     print(f"Your nostr public key: {client.public_key.bech32()}")
#     if verbose:
#         print(f"Your nostr private key (do not share!): {client.private_key.bech32()}")
#     await asyncio.sleep(2)

#     def get_token_callback(event: Event, decrypted_content):
#         if verbose:
#             print(
#                 f"From {event.public_key[:3]}..{event.public_key[-3:]}: {decrypted_content}"
#             )
#         try:
#             # call the receive method
#             from cashu.wallet.cli import receive

#             asyncio.run(receive(ctx, decrypted_content, ""))
#         except Exception as e:
#             pass

#     # determine timestamp of last check so we don't scan all historical DMs
#     wallet: Wallet = ctx.obj["WALLET"]
#     last_check = await get_nostr_last_check_timestamp(db=wallet.database)
#     if last_check:
#         last_check -= 60 * 60  # 1 hour tolerance
#     await set_nostr_last_check_timestamp(timestamp=int(time.time()), db=wallet.database)

#     t = threading.Thread(
#         target=client.get_dm,
#         args=(client.public_key, get_token_callback, {"since": last_check}),
#         name="Nostr DM",
#     )
#     t.start()
