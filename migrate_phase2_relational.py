from utils.erp_repository import init_erp_tables


def main():
    init_erp_tables()
    print("Phase 2 relational ERP tables initialized successfully.")


if __name__ == "__main__":
    main()
