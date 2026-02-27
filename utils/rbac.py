import json
from datetime import date

ROLE_HOD = "HOD"
ROLE_ASSOC_PROF = "ASSOC_PROF"
ROLE_ASST_PROF = "ASST_PROF"
ROLE_STAFF = "STAFF"


PERMISSION_MATRIX = {
    ROLE_HOD: {
        "view_department_faculty",
        "approve_leave",
        "assign_subjects",
        "view_workload_analytics",
        "modify_timetable",
        "view_student_reports",
        "export_department_reports",
        "input_appraisal",
        "monitor_attendance_compliance",
        "mark_attendance",
        "enter_internal_marks",
        "upload_study_materials",
        "apply_leave",
        "view_own_workload",
    },
    ROLE_ASSOC_PROF: {
        "mark_attendance",
        "enter_internal_marks",
        "upload_study_materials",
        "view_own_timetable",
        "apply_leave",
        "view_own_workload",
        "view_assigned_students",
        "view_limited_analytics",
    },
    ROLE_ASST_PROF: {
        "mark_attendance",
        "enter_internal_marks",
        "upload_study_materials",
        "view_own_timetable",
        "apply_leave",
    },
    ROLE_STAFF: {
        "view_profile",
        "apply_leave",
        "view_assigned_tasks",
        "upload_documents",
    },
}


def normalize_role_from_designation(designation: str) -> str:
    d = str(designation or "").strip().upper()
    if "HOD" in d:
        return ROLE_HOD
    if "ASSOC" in d:
        return ROLE_ASSOC_PROF
    if "ASST" in d:
        return ROLE_ASST_PROF
    return ROLE_STAFF


def default_permissions_json_for_role(role: str) -> str:
    normalized = str(role or ROLE_STAFF).strip().upper()
    perms = sorted(PERMISSION_MATRIX.get(normalized, PERMISSION_MATRIX[ROLE_STAFF]))
    return json.dumps({"role": normalized, "permissions": perms}, ensure_ascii=False)


def permissions_from_json(value):
    if isinstance(value, dict):
        return set(value.get("permissions") or [])
    if isinstance(value, str):
        try:
            payload = json.loads(value)
            if isinstance(payload, dict):
                return set(payload.get("permissions") or [])
        except Exception:
            return set()
    return set()


def can_permission(permission: str, role: str, permissions_json=None) -> bool:
    if not permission:
        return False
    role_norm = str(role or ROLE_STAFF).strip().upper()
    if role_norm == "ADMIN":
        return True
    explicit = permissions_from_json(permissions_json)
    if explicit:
        return permission in explicit
    return permission in PERMISSION_MATRIX.get(role_norm, set())


def compute_experience_years(joining_date_value):
    if not joining_date_value:
        return 0
    raw = str(joining_date_value).strip()
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            from datetime import datetime
            dt = datetime.strptime(raw, fmt).date()
            today = date.today()
            years = today.year - dt.year - ((today.month, today.day) < (dt.month, dt.day))
            return max(0, years)
        except Exception:
            continue
    return 0
