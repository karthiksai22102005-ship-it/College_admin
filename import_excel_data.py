import os
import sys

try:
    import pandas as pd
except ImportError:
    print("Install pandas and openpyxl first")
    sys.exit(1)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASE_DIR)

from utils.data_store import save_data
from utils.security import hash_password
from services.department_service import (
    canonicalize_department_code,
    infer_staff_type_from_designation,
    normalize_department_display,
    normalize_staff_type,
)

EXCEL_FILE = os.path.join(BASE_DIR, "TEACHING & NON TEACHING FINAL LIST WITH DOB.xlsx")
PKL_FILE = os.path.join(BASE_DIR, "data", "faculty.store")


def _sheet_staff_type(sheet_name):
    normalized = normalize_staff_type(sheet_name)
    if normalized:
        return normalized
    token = str(sheet_name).strip().lower()
    if token == "non teaching":
        return "NON_TEACHING"
    if token == "teaching":
        return "TEACHING"
    return None


def _safe_text(value):
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() == "nan":
        return ""
    return text


def import_data():
    print("Reading Excel...")

    xls_data = pd.read_excel(EXCEL_FILE, sheet_name=None, header=1)

    faculty_list = []
    existing = set()
    count = 0

    for sheet_name, df in xls_data.items():
        if str(sheet_name).strip().upper() == "RELIEVED STAFF":
            continue

        sheet_staff_type = _sheet_staff_type(sheet_name)
        if not sheet_staff_type:
            continue

        print(f"Processing sheet: {sheet_name}")

        for _, row in df.iterrows():
            name = _safe_text(row.get("First Name", ""))
            if not name:
                continue

            raw_department = _safe_text(row.get("Department", ""))
            department_code = canonicalize_department_code(raw_department)
            department_display = normalize_department_display(raw_department)

            designation = _safe_text(row.get("Designation", "Faculty"))
            staff_type = sheet_staff_type or infer_staff_type_from_designation(designation)

            dedupe_dept = department_code or department_display
            key = (name.lower(), str(dedupe_dept).lower(), staff_type)
            if key in existing:
                continue

            fid = f"FAC{1000 + count}"

            phone = _safe_text(row.get("Mobile Num", ""))
            dob = _safe_text(row.get("Date of Birth", "")).split()[0]

            profile = {
                "faculty_id": fid,
                "name": name,
                "department": department_display,
                "department_code": department_code,
                "staff_type": staff_type,
                "designation": designation,
                "email": "",
                "phone": phone,
                "dob": dob,
                "username": name.lower().replace(" ", ""),
                "password": hash_password("welcome123"),
                "photo": None,
                "qualifications": [],
                "subject_expertise": [],
                "publications": [],
                "books": [],
                "research_papers": [],
                "research_profiles": {},
                "certifications": [],
                "personal_documents": {
                    "aadhaar": None,
                    "pan": None,
                    "bank_passbook": None,
                    "others": [],
                },
            }

            faculty_list.append(profile)
            existing.add(key)
            count += 1

    save_data(PKL_FILE, faculty_list)

    print(f"Saved a total of {count} faculty profiles to {PKL_FILE}")
    print("Restart server now")


if __name__ == "__main__":
    import_data()
