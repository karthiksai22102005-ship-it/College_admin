from config import Config
from utils.data_store import load_faculty_data, save_data, ensure_faculty_schema_record


def main():
    rows = load_faculty_data(Config.FACULTY_STORE)
    normalized = [ensure_faculty_schema_record(r) for r in rows]
    save_data(Config.FACULTY_STORE, normalized)
    print(f"Normalized role/permission schema for {len(normalized)} faculty records.")


if __name__ == "__main__":
    main()
