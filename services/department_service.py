from collections import OrderedDict


CANONICAL_DEPARTMENTS = OrderedDict([
    ("AIDS", "AI & DS"),
    ("AIML", "AI & ML"),
    ("CSE", "CSE"),
    ("ECE", "ECE"),
    ("EEE", "EEE"),
    ("Civil", "Civil"),
    ("Mech", "Mech"),
    ("IoT", "IoT"),
    ("Cyber", "Cyber"),
    ("FED", "FED"),
])

EXCLUDED_DEPARTMENTS = {
    "office",
    "library",
    "tpo",
    "examcell",
    "health care",
    "mba",
}


def _normalize_token(value):
    if value is None:
        return ""
    return str(value).strip().lower().replace("&", "and")


def canonicalize_department_code(department_name):
    token = _normalize_token(department_name)
    if not token:
        return None

    if ("ai" in token and ("ds" in token or "data" in token)) or "aids" in token:
        return "AIDS"
    if "ai" in token and "ml" in token:
        return "AIML"
    if "cse" in token:
        return "CSE"
    if "ece" in token:
        return "ECE"
    if "eee" in token:
        return "EEE"
    if "civil" in token:
        return "Civil"
    if "mech" in token:
        return "Mech"
    if "iot" in token:
        return "IoT"
    if "cyber" in token:
        return "Cyber"
    if "fed" in token:
        return "FED"

    return None


def normalize_department_display(department_name):
    token = _normalize_token(department_name)
    if not token:
        return ""

    code = canonicalize_department_code(department_name)
    if code:
        return CANONICAL_DEPARTMENTS[code]

    if "exam" in token:
        return "Examcell"
    if "library" in token:
        return "Library"
    if "office" in token:
        return "Office"
    if "health" in token:
        return "Health Care"
    if "tpo" in token:
        return "TPO"
    if "fed" in token:
        return "FED"
    if "mba" in token:
        return "MBA"

    return str(department_name).strip()


def is_excluded_department(department_name):
    token = _normalize_token(department_name)
    return token in EXCLUDED_DEPARTMENTS


def normalize_staff_type(raw_value):
    token = _normalize_token(raw_value).replace("-", " ").replace("_", " ")
    if token in ("teaching", "teaching faculty"):
        return "TEACHING"
    if token in ("non teaching", "non teaching staff", "nonteaching", "nonteaching staff"):
        return "NON_TEACHING"
    return None


def infer_staff_type_from_designation(designation):
    token = _normalize_token(designation)
    non_teaching_markers = (
        "deo",
        "lab tech",
        "lab technician",
        "programmer",
        "jr.admin",
        "jr asst",
        "admin",
        "assistant",
        "attender",
        "civil engineer",
        "librarian",
        "technician",
    )
    if any(marker in token for marker in non_teaching_markers):
        return "NON_TEACHING"
    return "TEACHING"


def get_department_name(department_code):
    return CANONICAL_DEPARTMENTS.get(department_code)


def get_department_codes():
    return list(CANONICAL_DEPARTMENTS.keys())
