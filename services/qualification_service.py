import os
from utils.data_store import load_data, save_data

FACULTY_FILE = os.path.join("data", "faculty.store")


def add_or_update_qualification(
    faculty_id: str,
    qual_type: str,
    year=None,
    document_path=None
):
    """
    Add new qualification or update existing one.
    qual_type examples: SSC, Inter, B.Tech, PhD, MBA, MCA
    """
    data = load_data(FACULTY_FILE)
    if not isinstance(data, list): return None

    for fac in data:
        if fac["faculty_id"] == faculty_id:

            # check if qualification already exists
            for qual in fac.get("qualifications", []):
                if qual["type"] == qual_type:
                    # update existing
                    if year is not None:
                        qual["year"] = year
                    if document_path is not None:
                        qual["document"] = document_path
                    save_data(FACULTY_FILE, data)
                    return qual

            # add new qualification
            new_qual = {
                "type": qual_type,
                "year": year,
                "document": document_path
            }

            fac.setdefault("qualifications", []).append(new_qual)
            save_data(FACULTY_FILE, data)
            return new_qual

    return None


def get_qualifications(faculty_id: str):
    """Return all qualifications of a faculty."""
    data = load_data(FACULTY_FILE)
    if not isinstance(data, list): return []

    for fac in data:
        if fac["faculty_id"] == faculty_id:
            return fac.get("qualifications", [])

    return []


def remove_qualification(faculty_id: str, qual_type: str):
    """Delete a qualification entry."""
    data = load_data(FACULTY_FILE)
    if not isinstance(data, list): return False

    for fac in data:
        if fac["faculty_id"] == faculty_id:
            original_len = len(fac.get("qualifications", []))
            fac["qualifications"] = [
                q for q in fac.get("qualifications", [])
                if q["type"] != qual_type
            ]
            save_data(FACULTY_FILE, data)
            return len(fac["qualifications"]) < original_len

    return False
