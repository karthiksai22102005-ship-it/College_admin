from werkzeug.security import generate_password_hash, check_password_hash


def hash_password(password: str) -> str:
    """Hash plain password."""
    return generate_password_hash(password)


def verify_password(password: str, hashed: str) -> bool:
    """Verify password."""
    try:
        return check_password_hash(hashed, password)
    except Exception:
        return False


def check_password(password: str, hashed: str) -> bool:
    """Backward-compatible alias."""
    return verify_password(password, hashed)


def is_password_hash(value: str) -> bool:
    token = str(value or "").strip().lower()
    if not token:
        return False
    return (
        token.startswith("scrypt:")
        or token.startswith("pbkdf2:")
        or token.startswith("argon2")
        or token.startswith("$2a$")
        or token.startswith("$2b$")
        or token.startswith("$2y$")
    )
