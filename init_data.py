import pickle
import os
from datetime import datetime

DATA_DIR = "data"


def safe_init_file(path, default_data):
    """Create PKL file only if it does not exist."""
    if not os.path.exists(path):
        with open(path, "wb") as f:
            pickle.dump(default_data, f)
        print(f"Created: {path}")
    else:
        print(f"Already exists: {path}")


def main():
    os.makedirs(DATA_DIR, exist_ok=True)

    # Users store
    safe_init_file(
        os.path.join(DATA_DIR, "users.store"),
        {
            "meta": {
                "version": 1,
                "created_at": datetime.utcnow().isoformat()
            },
            "users": []
        }
    )

    # Faculty store - simple list for easy append/iteration
    safe_init_file(
        os.path.join(DATA_DIR, "faculty.store"),
        []
    )

    # Departments store
    safe_init_file(
        os.path.join(DATA_DIR, "departments.store"),
        {
            "meta": {
                "version": 1,
                "created_at": datetime.utcnow().isoformat()
            },
            "departments": [
                "AIML",
                "AIDS",
                "CSE",
                "EEE",
                "ECE",
                "Mech",
                "IoT",
                "Civil",
                "Cyber",
                "MBA",
                "Examcell",
                "Library",
                "Office",
                "Health Care",
                "TPO"
            ]
        }
    )

    print("\nData initialization complete.")


if __name__ == "__main__":
    main()
