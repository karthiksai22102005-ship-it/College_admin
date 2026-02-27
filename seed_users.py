import os
from utils.data_store import load_data, save_data
from utils.security import hash_password

USERS_FILE = os.path.join("data", "users.store")


def seed():
    data = load_data(USERS_FILE)

    # ⚠️ prevent duplicate seeding
    if data.get("users"):
        print("Users already exist. Skipping seed.")
        return

    # ===== ADMIN =====
    admin_user = {
        "user_id": "ADMIN001",
        "role": "admin",
        "password_hash": hash_password("admin123"),
        "faculty_id": None
    }

    # ===== SAMPLE FACULTY =====
    faculty_user = {
        "user_id": "FAC001",
        "role": "faculty",
        "password_hash": hash_password("faculty123"),
        "faculty_id": "FAC-0001"
    }

    data["users"].append(admin_user)
    data["users"].append(faculty_user)

    save_data(USERS_FILE, data)
    print("Default users seeded.")


if __name__ == "__main__":
    seed()
