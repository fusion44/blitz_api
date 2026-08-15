import re

# These values reach shell command strings, so this charset is the boundary.
# fullmatch, not match: `$` would also match before a trailing newline.
_ALLOWED = re.compile(r"^[.a-zA-Z0-9\-_]*$")


def password_valid(password: str):
    if len(password) < 8:
        return False
    if password.find(" ") >= 0:
        return False
    return _ALLOWED.fullmatch(password) is not None


def name_valid(password: str):
    if len(password) < 3:
        return False
    if password.find(" ") >= 0:
        return False
    return _ALLOWED.fullmatch(password) is not None
