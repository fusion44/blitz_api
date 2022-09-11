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
