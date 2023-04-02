import time


def calc_fee_rate_str(sat_per_vbyte, target_conf) -> str:
    """Calculate fee rate as a string"""

    # feerate is an optional feerate to use.
    # It can be one of the strings urgent
    # (aim for next block), normal (next 4 blocks or so)
    # or slow (next 100 blocks or so) to use lightningd’s
    # internal estimates: normal is the default.

    fee_rate: str = ""
    if sat_per_vbyte != None and sat_per_vbyte > 0:
        fee_rate = f"{sat_per_vbyte}perkw"
    elif target_conf != None and target_conf == 1:
        fee_rate = "urgent"
    elif target_conf != None and target_conf >= 2:
        fee_rate = "normal"
    elif target_conf != None and target_conf >= 10:
        fee_rate = "slow"

    return fee_rate


def parse_cln_msat(msat) -> int:
    if isinstance(msat, str):
        return int(msat.replace("msat", ""))

    return msat


def cln_classify_fee_revenue(forwards: list):
    """Calculate revenue from fees"""
    day = week = month = year = total = 0

    now = time.time()
    t_day = now - 86400.0  # 1 day
    t_week = now - 604800.0  # 1 week
    t_month = now - 2592000.0  # 1 month
    t_year = now - 31536000.0  # 1 year

    # TODO: performance: cache this in redis
    for f in forwards:
        received_time = fee = 0
        if isinstance(f, dict):
            received_time = f["received_time"]
            fee = parse_cln_msat(f["fee_msat"])
        else:
            received_time = f.received_time
            fee = f.fee_msat.msat

        total += fee

        if received_time > t_day:
            day += fee
            week += fee
            month += fee
            year += fee
        elif received_time > t_week:
            week += fee
            month += fee
            year += fee
        elif received_time > t_month:
            month += fee
            year += fee
        elif received_time > t_year:
            year += fee
    return (day, week, month, year, total)
