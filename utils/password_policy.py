import re


def validate_password_strength(password):
    pwd = str(password or "")
    if len(pwd) < 8:
        return False, "Password must be at least 8 characters long"
    if not re.search(r"[A-Z]", pwd):
        return False, "Password must include at least one uppercase letter"
    if not re.search(r"[a-z]", pwd):
        return False, "Password must include at least one lowercase letter"
    if not re.search(r"\d", pwd):
        return False, "Password must include at least one number"
    if not re.search(r"[^A-Za-z0-9]", pwd):
        return False, "Password must include at least one special character"
    return True, ""
