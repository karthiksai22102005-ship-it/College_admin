import os
from utils.data_store import load_data, save_data

FACULTY_FILE = os.path.join("data", "faculty.store")


def add_publication(faculty_id: str, title: str, source=None, year=None):
    """Add a publication entry."""
    data = load_data(FACULTY_FILE)
    if not isinstance(data, list): return None

    for fac in data:
        if fac["faculty_id"] == faculty_id:
            new_pub = {
                "title": title,
                "source": source,
                "year": year
            }

            fac.setdefault("publications", []).append(new_pub)
            save_data(FACULTY_FILE, data)
            return new_pub

    return None


def get_publications(faculty_id: str):
    """Return publications list."""
    data = load_data(FACULTY_FILE)
    if not isinstance(data, list): return ["-"]

    for fac in data:
        if fac["faculty_id"] == faculty_id:
            pubs = fac.get("publications", [])
            return pubs if pubs else ["-"]

    return ["-"]


def delete_publication(faculty_id: str, title: str):
    """Remove publication by title."""
    data = load_data(FACULTY_FILE)
    if not isinstance(data, list): return False

    for fac in data:
        if fac["faculty_id"] == faculty_id:
            original_len = len(fac.get("publications", []))
            fac["publications"] = [
                p for p in fac.get("publications", [])
                if p["title"] != title
            ]
            save_data(FACULTY_FILE, data)
            return len(fac["publications"]) < original_len

    return False
