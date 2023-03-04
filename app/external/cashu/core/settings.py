import os
import sys
from pathlib import Path

from environs import Env  # type: ignore

env = Env()

# env file: default to current dir, else home dir
ENV_FILE = os.path.join(os.getcwd(), ".cashu")
if not os.path.isfile(ENV_FILE):
    ENV_FILE = os.path.join(str(Path.home()), ".cashu", ".env")
if os.path.isfile(ENV_FILE):
    env.read_env(ENV_FILE)
else:
    ENV_FILE = ""
    env.read_env(recurse=False)

DEBUG = env.bool("DEBUG", default=False)
if not DEBUG:
    sys.tracebacklimit = 0

CASHU_DIR = env.str("CASHU_DIR", default=os.path.join(str(Path.home()), ".cashu"))
CASHU_DIR = CASHU_DIR.replace("~", str(Path.home()))
assert len(CASHU_DIR), "CASHU_DIR not defined"

TOR = env.bool("TOR", default=True)

SOCKS_HOST = env.str("SOCKS_HOST", default=None)
SOCKS_PORT = env.int("SOCKS_PORT", default=9050)

LIGHTNING = env.bool("LIGHTNING", default=True)
LIGHTNING_FEE_PERCENT = env.float("LIGHTNING_FEE_PERCENT", default=1.0)
assert LIGHTNING_FEE_PERCENT >= 0, "LIGHTNING_FEE_PERCENT must be at least 0"
LIGHTNING_RESERVE_FEE_MIN = env.float("LIGHTNING_RESERVE_FEE_MIN", default=2000)

MINT_PRIVATE_KEY = env.str("MINT_PRIVATE_KEY", default=None)

MINT_SERVER_HOST = env.str("MINT_SERVER_HOST", default="127.0.0.1")
MINT_SERVER_PORT = env.int("MINT_SERVER_PORT", default=3338)

MINT_URL = env.str("MINT_URL", default=None)
MINT_HOST = env.str("MINT_HOST", default="8333.space")
MINT_PORT = env.int("MINT_PORT", default=3338)

if not MINT_URL:
    if MINT_HOST in ["localhost", "127.0.0.1"]:
        MINT_URL = f"http://{MINT_HOST}:{MINT_PORT}"
    else:
        MINT_URL = f"https://{MINT_HOST}:{MINT_PORT}"

LNBITS_ENDPOINT = env.str("LNBITS_ENDPOINT", default=None)
LNBITS_KEY = env.str("LNBITS_KEY", default=None)

NOSTR_PRIVATE_KEY = env.str("NOSTR_PRIVATE_KEY", default=None)
NOSTR_RELAYS = env.list(
    "NOSTR_RELAYS",
    default=[
        "wss://nostr-pub.wellorder.net",
        "wss://relay.damus.io",
        "wss://nostr.zebedee.cloud",
        "wss://relay.snort.social",
        "wss://nostr.fmt.wiz.biz",
    ],
)

MAX_ORDER = 64
VERSION = "0.9.3"
