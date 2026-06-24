import re

PASSWORD_RULE_TEXT = (
    "Password must be at least 8 characters and include uppercase, "
    "lowercase, number, and special character."
)


def is_strong_password(password):
    if not password or len(password) < 8:
        return False
    if not re.search(r"[A-Z]", password):
        return False
    if not re.search(r"[a-z]", password):
        return False
    if not re.search(r"\d", password):
        return False
    if not re.search(r"[^A-Za-z0-9]", password):
        return False
    return True
