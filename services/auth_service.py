import os
from utils.data_store import load_data, save_data
from utils.security import verify_password, hash_password
from utils.id_generator import generate_user_id

USERS_FILE = os.path.join("data", "users.store")


def login_user(user_id: str, password: str):
    """Validate login credentials."""
    data = load_data(USERS_FILE)
    if not data:
        return None

    for user in data.get("users", []):
        if user["user_id"] == user_id:
            if verify_password(password, user["password_hash"]):
                return user
    return None


def create_user(role: str, password: str, faculty_id=None):
    """Create new user (admin or faculty)."""
    data = load_data(USERS_FILE)

    new_user = {
        "user_id": generate_user_id(),
        "role": role,
        "password_hash": hash_password(password),
        "faculty_id": faculty_id
    }

    data["users"].append(new_user)
    save_data(USERS_FILE, data)

    return new_user


def get_user_by_id(user_id: str):
    """Fetch user by ID."""
    data = load_data(USERS_FILE)
    for user in data.get("users", []):
        if user["user_id"] == user_id:
            return user
    return None
