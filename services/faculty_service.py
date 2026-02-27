import os
from utils.data_store import load_data, save_data
from utils.id_generator import generate_faculty_id

FACULTY_FILE = os.path.join("data", "faculty.store")


def get_all_faculty():
    """Return all faculty records."""
    data = load_data(FACULTY_FILE)
    return data if isinstance(data, list) else []


def get_faculty_by_id(faculty_id: str):
    """Fetch single faculty profile."""
    data = load_data(FACULTY_FILE)
    for fac in (data if isinstance(data, list) else []):
        if fac["faculty_id"] == faculty_id:
            return fac
    return None


def get_faculty_by_department(department: str):
    """Filter faculty by department."""
    data = load_data(FACULTY_FILE)
    return [
        fac for fac in (data if isinstance(data, list) else [])
        if fac.get("department") == department
    ]


def create_faculty(name: str, department: str):
    """Create new faculty profile."""
    data = load_data(FACULTY_FILE)
    if not isinstance(data, list):
        data = []

    new_faculty = {
        "faculty_id": generate_faculty_id(),
        "name": name,
        "department": department,
        "photo": None,
        "subject_expertise": [],
        "qualifications": [],
        "publications": []
    }

    data.append(new_faculty)
    save_data(FACULTY_FILE, data)

    return new_faculty


def update_faculty(faculty_id: str, updates: dict):
    """Update faculty basic fields."""
    data = load_data(FACULTY_FILE)
    if not isinstance(data, list): return None

    for fac in data:
        if fac["faculty_id"] == faculty_id:
            fac.update(updates)
            save_data(FACULTY_FILE, data)
            return fac

    return None


def delete_faculty(faculty_id: str):
    """Remove faculty record."""
    data = load_data(FACULTY_FILE)
    if not isinstance(data, list): return False

    original_len = len(data)
    data = [
        fac for fac in data
        if fac["faculty_id"] != faculty_id
    ]

    save_data(FACULTY_FILE, data)
    return len(data) < original_len
