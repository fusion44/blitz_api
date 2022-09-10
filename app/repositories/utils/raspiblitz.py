import asyncio
import logging
import re
import warnings
from decouple import config

from app.core_utils import ProcessResult


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


async def call_script(scriptPath) -> str:
    warnings.warn("call_script is deprecated. Use call_script2 instead.")

    cmd = f"bash {scriptPath}"
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


async def call_script2(script_path) -> ProcessResult:
    """
    Call a local bash script and return the results

    :param str script_path: full path with arguments
    :return: The process result
    :rtype: ProcessResult
    """

    cmd = f"bash {script_path}"
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()

    return ProcessResult(
        proc.returncode,
        stdout.decode() if stdout else "",
        stderr.decode() if stderr else "",
    )


async def call_sudo_script(scriptPath) -> str:
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
