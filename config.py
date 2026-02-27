import os
from datetime import timedelta


def _as_bool(value: str, default: bool = False) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


BASE_DIR = os.path.dirname(os.path.abspath(__file__))


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "super-secret-key-change-later")

    PERMANENT_SESSION_LIFETIME = timedelta(hours=int(os.getenv("SESSION_LIFETIME_HOURS", "24")))
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = os.getenv("SESSION_COOKIE_SAMESITE", "Lax")
    SESSION_COOKIE_SECURE = _as_bool(os.getenv("SESSION_COOKIE_SECURE"), default=False)

    FACULTY_STORE = os.path.join(BASE_DIR, "data", "faculty.store")
    USERS_STORE = os.path.join(BASE_DIR, "data", "users.store")
    UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
    FACULTY_PHOTO_UPLOAD_DIR = os.path.join(BASE_DIR, "static", "uploads", "faculty")
