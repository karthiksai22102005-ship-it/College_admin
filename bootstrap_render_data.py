import argparse
import os
from utils.data_store import load_data, save_data
from utils.security import hash_password


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
USERS_STORE = os.path.join(BASE_DIR, "data", "users.store")
FACULTY_STORE = os.path.join(BASE_DIR, "data", "faculty.store")


def ensure_admin_user():
    users_data = load_data(USERS_STORE)
    if not isinstance(users_data, dict):
        users_data = {"meta": {"version": 1}, "users": []}

    users = users_data.get("users")
    if not isinstance(users, list):
        users = []
        users_data["users"] = users

    for user in users:
        if str(user.get("user_id", "")).strip().upper() == "ADMIN001":
            return False

    users.append(
        {
            "user_id": "ADMIN001",
            "role": "admin",
            "password_hash": hash_password("admin123"),
            "faculty_id": None,
        }
    )
    save_data(USERS_STORE, users_data)
    return True


def maybe_import_excel(force_excel=False):
    from import_excel_data import import_data

    faculty = load_data(FACULTY_STORE)
    if force_excel or not isinstance(faculty, list) or len(faculty) == 0:
        import_data()
        return True
    return False


def summary():
    users_data = load_data(USERS_STORE)
    users = users_data.get("users", []) if isinstance(users_data, dict) else []
    faculty = load_data(FACULTY_STORE)
    faculty = faculty if isinstance(faculty, list) else []

    print("\nBootstrap Summary")
    print(f"- users count: {len(users)}")
    print(f"- faculty count: {len(faculty)}")
    print("- admin login: ADMIN001 / admin123")
    if faculty:
        sample = faculty[0]
        print(
            "- sample faculty login: "
            f"{sample.get('username', '(missing username)')} / "
            f"{'welcome123' if sample.get('username') else '(unknown)'}"
        )


def main():
    parser = argparse.ArgumentParser(description="Bootstrap Render data for College Admin")
    parser.add_argument(
        "--force-excel",
        action="store_true",
        help="Re-import faculty data from Excel even if faculty data already exists",
    )
    args = parser.parse_args()

    db_backend = str(os.getenv("DB_BACKEND", "")).strip().lower()
    database_url = str(os.getenv("DATABASE_URL", "")).strip()

    if db_backend != "postgres":
        print("Warning: DB_BACKEND is not 'postgres'. Current value:", db_backend or "(empty)")
    if not database_url:
        print("Warning: DATABASE_URL is empty. Set it before running on Render.")

    admin_added = ensure_admin_user()
    excel_imported = maybe_import_excel(force_excel=args.force_excel)

    print("\nActions")
    print(f"- admin created: {'yes' if admin_added else 'no (already exists)'}")
    print(f"- excel imported: {'yes' if excel_imported else 'no (faculty already exists)'}")
    summary()


if __name__ == "__main__":
    main()
