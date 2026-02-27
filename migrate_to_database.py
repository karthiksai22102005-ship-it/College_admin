import os
from utils.data_store import load_data, save_data


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")

# Logical datasets currently used across the app.
LEGACY_DATASETS = [
    os.path.join(DATA_DIR, "faculty.store"),
    os.path.join(DATA_DIR, "users.store"),
    os.path.join(DATA_DIR, "audit_logs.store"),
    os.path.join(DATA_DIR, "notifications.store"),
]


def main():
    print("Starting data migration to database backend...")
    migrated = 0
    for dataset in LEGACY_DATASETS:
        data = load_data(dataset)
        save_data(dataset, data)
        print(f"Migrated dataset key from: {dataset}")
        migrated += 1
    print(f"Completed. Migrated {migrated} dataset(s).")


if __name__ == "__main__":
    main()
