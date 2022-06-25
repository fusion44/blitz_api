import array
import asyncio
import json
import logging
import random
import re
import time
from typing import Dict

from fastapi.encoders import jsonable_encoder
from fastapi_plugins import redis_plugin


async def send_sse_message(id: str, json_data: Dict):
    """Send a message to any SSE connections

    Parameters
    ----------
    id : str
        ID String von SSE class
    data : list, optional
        The data to include
    """

    await redis_plugin.redis.publish_json(
        "default", {"event": id, "data": json.dumps(jsonable_encoder(json_data))}
    )


async def redis_get(key: str) -> str:
    v = await redis_plugin.redis.get(key)

    if not v:
        logging.warning(f"Key '{key}' not found in Redis DB.")
        return ""

    return v.decode("utf-8")


# TODO
# idea is to have a second redis channel called system, that the API subscribes to. If for example
# the 'state' value gets changed by the _cache.sh script, it should publish this to this channel
# so the API can forward the change to thru the SSE to the WebUI


class SSE:
    SYSTEM_INFO = "system_info"
    SYSTEM_SHUTDOWN_NOTICE = "system_shutdown_initiated"
    SYSTEM_SHUTDOWN_ERROR = "system_shutdown_error"
    SYSTEM_STARTUP_INFO = "system_startup_info"
    SYSTEM_REBOOT_NOTICE = "system_reboot_initiated"
    SYSTEM_REBOOT_ERROR = "system_reboot_error"
    HARDWARE_INFO = "hardware_info"

    INSTALL_APP = "install"
    INSTALLED_APP_STATUS = "installed_app_status"

    BTC_NETWORK_STATUS = "btc_network_status"
    BTC_MEMPOOL_STATUS = "btc_mempool_status"
    BTC_NEW_BLOC = "btc_new_bloc"
    BTC_INFO = "btc_info"

    LN_INFO = "ln_info"
    LN_INFO_LITE = "ln_info_lite"
    LN_INVOICE_STATUS = "ln_invoice_status"
    LN_PAYMENT_STATUS = "ln_payment_status"
    LN_ONCHAIN_PAYMENT_STATUS = "ln_onchain_payment_status"
    LN_FEE_REVENUE = "ln_fee_revenue"
    LN_FORWARD_SUCCESSES = "ln_forward_successes"
    WALLET_BALANCE = "wallet_balance"


async def call_script(scriptPath) -> str:
    cmd = f"sudo bash {scriptPath}"
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if stdout:
        return stdout.decode()
    if stderr:
        logging.error(stderr.decode())
    return ""


def parse_key_value_lines(lines: list) -> dict:
    Dict = {}
    for line in lines:
        line = line.strip()
        if len(line) == 0:
            continue
        if not re.match("^[a-zA-Z0-9]*=", line):
            continue
        key, value = line.strip().split("=", 1)
        Dict[key] = value.strip('"').strip("'")
    return Dict


def parse_key_value_text(text: str) -> dict:
    return parse_key_value_lines(text.splitlines())


# https://gist.github.com/risent/4cab3878d995bec7d1c2
# https://firebase.blog/posts/2015/02/the-2120-ways-to-ensure-unique_68
# https://gist.github.com/mikelehen/3596a30bd69384624c11
class _PushID(object):
    # Modeled after base64 web-safe chars, but ordered by ASCII.
    PUSH_CHARS = (
        "-0123456789" "ABCDEFGHIJKLMNOPQRSTUVWXYZ" "_abcdefghijklmnopqrstuvwxyz"
    )

    def __init__(self):

        # Timestamp of last push, used to prevent local collisions if you
        # push twice in one ms.
        self.last_push_time = 0

        # We generate 72-bits of randomness which get turned into 12
        # characters and appended to the timestamp to prevent
        # collisions with other clients.  We store the last characters
        # we generated because in the event of a collision, we'll use
        # those same characters except "incremented" by one.
        self.last_rand_chars = array.array("i", [i for i in range(12)])

    def next_id(self):
        now = int(time.time() * 1000)
        duplicate_time = now == self.last_push_time
        self.last_push_time = now
        time_stamp_chars = array.array("u", "12345678")

        for i in range(7, -1, -1):
            time_stamp_chars[i] = self.PUSH_CHARS[now % 64]
            now = int(now / 64)

        if now != 0:
            raise ValueError("We should have converted the entire timestamp.")

        uid = "".join(time_stamp_chars)

        if not duplicate_time:
            for i in range(12):
                self.last_rand_chars[i] = int(random.random() * 64)
        else:
            # If the timestamp hasn't changed since last push, use the
            # same random number, except incremented by 1.
            for i in range(11, -1, -1):
                if self.last_rand_chars[i] == 63:
                    self.last_rand_chars[i] = 0
                else:
                    break
            self.last_rand_chars[i] += 1

        for i in range(12):
            uid += self.PUSH_CHARS[self.last_rand_chars[i]]

        if len(uid) != 20:
            raise ValueError("Length should be 20.")

        return uid


pid_gen = _PushID()


def next_push_id() -> str:
    """Generates a unique random 20 character long string id

    * They're based on timestamp so that they sort *after* any existing ids.
    * They contain 72-bits of random data after the timestamp so that IDs won't collide with other clients' IDs.
    * They sort *lexicographically* (so the timestamp is converted to characters that will sort properly).
    * They're monotonically increasing.  Even if you generate more than one in the same timestamp, the
      latter ones will sort after the former ones.  We do this by using the previous random bits
      but "incrementing" them by 1 (only in the case of a timestamp collision).
    """
    return pid_gen.next_id()
