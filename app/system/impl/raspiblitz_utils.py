import re


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
