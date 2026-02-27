import os
from datetime import datetime

from utils.data_store import load_data, save_data
from services.department_service import (
    canonicalize_department_code,
    infer_staff_type_from_designation,
    normalize_department_display,
    normalize_staff_type,
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FACULTY_STORE = os.path.join(BASE_DIR, "data", "faculty.store")


def migrate():
    faculty_list = load_data(FACULTY_STORE)
    if not isinstance(faculty_list, list):
        print("faculty.store is not a list. Aborting.")
        return

    backup_path = FACULTY_STORE + ".bak." + datetime.now().strftime("%Y%m%d_%H%M%S")
    save_data(backup_path, faculty_list)

    updated = 0
    for faculty in faculty_list:
        original_code = faculty.get("department_code")
        original_staff_type = faculty.get("staff_type")

        department = faculty.get("department")
        if department:
            faculty["department"] = normalize_department_display(department)

        if not original_code:
            faculty["department_code"] = canonicalize_department_code(faculty.get("department"))

        normalized_staff = normalize_staff_type(original_staff_type)
        if normalized_staff:
            faculty["staff_type"] = normalized_staff
        else:
            faculty["staff_type"] = infer_staff_type_from_designation(faculty.get("designation"))

        if faculty.get("department_code") != original_code or faculty.get("staff_type") != original_staff_type:
            updated += 1

    save_data(FACULTY_STORE, faculty_list)

    print(f"Backup created: {backup_path}")
    print(f"Records updated: {updated}/{len(faculty_list)}")


if __name__ == "__main__":
    migrate()
