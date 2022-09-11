import re

from decouple import config

SHELL_SCRIPT_PATH = config("shell_script_path")

available_app_ids = {
    "btc-rpc-explorer",
    "rtl",
    # Specter is deactivated for now because it uses its own self signed HTTPS cert that makes trouble in Chrome on last test
    # "specter",
    "btcpayserver",
    "lnbits",
    "mempool",
    "thunderhub",
}


def password_valid(password: str):
    if len(password) < 8:
        return False
    if password.find(" ") >= 0:
        return False
    return re.match("^[a-zA-Z0-9]*$", password)


def name_valid(password: str):
    if len(password) < 3:
        return False
    if password.find(" ") >= 0:
        return False
    return re.match("^[\.a-zA-Z0-9-_]*$", password)
