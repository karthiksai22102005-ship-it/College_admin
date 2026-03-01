from flask import Blueprint, jsonify, send_file, request, session
from utils.data_store import export_faculty_to_excel, load_data, save_data, load_faculty_data, ensure_faculty_schema_record
from utils.file_handler import save_file, delete_file
from utils.audit_service import log_event
from utils.security import hash_password
from utils.password_policy import validate_password_strength
from utils.notification_service import push_notification, list_notifications, mark_as_read
from utils.rbac import normalize_role_from_designation, default_permissions_json_for_role
from services.department_service import (
    CANONICAL_DEPARTMENTS,
    canonicalize_department_code,
    get_department_codes,
    get_department_name,
    infer_staff_type_from_designation,
    normalize_department_display,
    normalize_staff_type,
)
from functools import wraps
import os
import uuid
import pandas as pd
from werkzeug.utils import secure_filename

admin_bp = Blueprint("admin_bp", __name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FACULTY_STORE = os.path.join(BASE_DIR, "data", "faculty.store")
ADMIN_PHOTO_UPLOAD_DIR = os.path.join(BASE_DIR, "static", "uploads", "faculty")
EXPORT_PATH = os.path.join(BASE_DIR, "data", "exports", "faculty_export.xlsx")
ALLOWED_PERSONAL_DOC_TYPES = {"aadhaar", "pan", "bank_passbook", "service_register", "joining_letter", "others"}
ALLOWED_QUAL_DOC_TYPES = {"ssc_memo", "inter_memo", "btech_memo", "mtech_memo", "phd_memo", "others"}
ALLOWED_PHOTO_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}
OTHER_DEPARTMENT_CODE = "OTHER"
OTHER_DEPARTMENT_NAME = "Other Units"


def _resolve_department_code(raw_code):
    if not raw_code:
        return None
    token = str(raw_code).strip().upper()
    if token == OTHER_DEPARTMENT_CODE:
        return OTHER_DEPARTMENT_CODE
    for code in get_department_codes():
        if code.lower() == str(raw_code).strip().lower():
            return code
    return None


def _load_faculty_rows():
    return load_faculty_data(FACULTY_STORE)


def _save_faculty_rows(rows):
    save_data(FACULTY_STORE, [ensure_faculty_schema_record(r) for r in rows])


def _admin_actor():
    return session.get("username") or session.get("user") or "admin"


def _allowed_photo(filename):
    if not filename or "." not in filename:
        return False
    return filename.rsplit(".", 1)[1].lower() in ALLOWED_PHOTO_EXTENSIONS


def _delete_photo_file_if_local(photo_path):
    if not photo_path:
        return
    normalized = str(photo_path).replace("\\", "/")
    if normalized.startswith("/static/uploads/faculty/"):
        file_name = normalized.split("/static/uploads/faculty/", 1)[1]
        abs_path = os.path.join(ADMIN_PHOTO_UPLOAD_DIR, file_name)
        if os.path.exists(abs_path):
            try:
                os.remove(abs_path)
            except OSError:
                pass


def _clear_personal_and_qualification_docs(faculty):
    personal = faculty.setdefault("personal_documents", {})
    qualification = faculty.setdefault("qualification_documents", {})

    for key in ("aadhaar", "pan", "bank_passbook", "service_register", "joining_letter"):
        path = personal.get(key)
        if path:
            delete_file(path)
        personal[key] = ""
    for path in list(personal.get("others", []) or []):
        delete_file(path)
    personal["others"] = []

    for key in ("ssc_memo", "inter_memo", "btech_memo", "mtech_memo", "phd_memo"):
        path = qualification.get(key)
        if path:
            delete_file(path)
        qualification[key] = ""
    for path in list(qualification.get("others", []) or []):
        delete_file(path)
    qualification["others"] = []


def _clear_rd_submissions(faculty):
    for cert in list(faculty.get("certifications", []) or []):
        if cert.get("file"):
            delete_file(cert.get("file"))
    for book in list(faculty.get("books", []) or []):
        if book.get("file"):
            delete_file(book.get("file"))
    for paper in list(faculty.get("research_papers", []) or []):
        if paper.get("file"):
            delete_file(paper.get("file"))

    faculty["certifications"] = []
    faculty["books"] = []
    faculty["research_papers"] = []


def _normalize_faculty_shape(faculty):
    dept_code = faculty.get("department_code") or canonicalize_department_code(faculty.get("department"))
    dept_name = normalize_department_display(faculty.get("department") or get_department_name(dept_code) or "")
    staff_type = normalize_staff_type(faculty.get("staff_type")) or infer_staff_type_from_designation(faculty.get("designation"))
    return dept_code, dept_name, staff_type


def _faculty_list_item(faculty):
    dept_code, dept_name, staff_type = _normalize_faculty_shape(faculty)
    personal_docs = faculty.get("personal_documents", {}) or {}
    qual_docs = faculty.get("qualification_documents", {}) or {}
    personal_count = sum(1 for k in ("aadhaar", "pan", "bank_passbook", "service_register", "joining_letter") if personal_docs.get(k))
    qual_count = sum(1 for k in ("ssc_memo", "inter_memo", "btech_memo", "mtech_memo", "phd_memo") if qual_docs.get(k))
    return {
        "faculty_id": faculty.get("faculty_id"),
        "name": faculty.get("name"),
        "username": faculty.get("username"),
        "normalized_role": faculty.get("normalized_role") or faculty.get("role"),
        "account_locked": bool(faculty.get("account_locked", False)),
        "department": dept_name,
        "department_code": dept_code,
        "staff_type": staff_type,
        "phone": faculty.get("phone"),
        "email": faculty.get("email"),
        "photo": faculty.get("photo"),
        "designation": faculty.get("designation"),
        "personal_docs_count": personal_count,
        "qualification_docs_count": qual_count,
    }


def _sanitize_faculty_response(faculty):
    payload = dict(faculty or {})
    payload.pop("password", None)
    payload.pop("password_hash", None)
    payload["has_password"] = bool(faculty and faculty.get("password"))
    return payload


def _department_faculty_item(faculty):
    dept_code, dept_name, staff_type = _normalize_faculty_shape(faculty)
    personal_docs = faculty.get("personal_documents", {}) or {}
    qual_docs = faculty.get("qualification_documents", {}) or {}
    personal_count = sum(1 for k in ("aadhaar", "pan", "bank_passbook", "service_register", "joining_letter") if personal_docs.get(k))
    qual_count = sum(1 for k in ("ssc_memo", "inter_memo", "btech_memo", "mtech_memo", "phd_memo") if qual_docs.get(k))
    return {
        "faculty_id": faculty.get("faculty_id"),
        "name": faculty.get("name"),
        "username": faculty.get("username"),
        "normalized_role": faculty.get("normalized_role") or faculty.get("role"),
        "account_locked": bool(faculty.get("account_locked", False)),
        "department": dept_name,
        "department_code": dept_code,
        "staff_type": staff_type,
        "designation": faculty.get("designation"),
        "email": faculty.get("email"),
        "phone": faculty.get("phone"),
        "photo": faculty.get("photo"),
        "personal_docs_count": personal_count,
        "qualification_docs_count": qual_count,
    }


# ======================================================
# DECORATORS
# ======================================================
def is_admin(f):
    """Decorator to ensure user is an admin."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "role" not in session or session.get("role") != "admin":
            return jsonify({"error": "admin only"}), 403
        return f(*args, **kwargs)
    return decorated_function


@admin_bp.route("/status", methods=["GET"])
def admin_status():
    return jsonify({"status": "admin routes active"})


# ======================================================
# EXPORT FACULTY
# ======================================================
@admin_bp.route("/export/faculty", methods=["GET"])
@is_admin
def export_faculty_excel():
    success = export_faculty_to_excel(FACULTY_STORE, EXPORT_PATH)

    if not success:
        return jsonify({"error": "No faculty data"}), 400

    return send_file(
        EXPORT_PATH,
        as_attachment=True,
        download_name="faculty_data.xlsx",
    )


# ======================================================
# GET DEPARTMENT SUMMARY (9 CANONICAL DEPARTMENTS)
# ======================================================
@admin_bp.route("/departments", methods=["GET"])
@is_admin
def get_departments():
    try:
        faculty_list = _load_faculty_rows()
        if not isinstance(faculty_list, list):
            faculty_list = []

        counts = {
            code: {"teaching_count": 0, "non_teaching_count": 0}
            for code in get_department_codes()
        }
        counts[OTHER_DEPARTMENT_CODE] = {"teaching_count": 0, "non_teaching_count": 0}

        for faculty in faculty_list:
            dept_code, _, staff_type = _normalize_faculty_shape(faculty)
            bucket = dept_code if dept_code in CANONICAL_DEPARTMENTS else OTHER_DEPARTMENT_CODE

            if staff_type == "NON_TEACHING":
                counts[bucket]["non_teaching_count"] += 1
            else:
                counts[bucket]["teaching_count"] += 1

        departments = []
        for code in get_department_codes():
            teaching_count = counts[code]["teaching_count"]
            non_teaching_count = counts[code]["non_teaching_count"]
            total_count = teaching_count + non_teaching_count

            departments.append({
                "department_code": code,
                "department_name": get_department_name(code),
                "teaching_count": teaching_count,
                "non_teaching_count": non_teaching_count,
                "total_count": total_count,
            })

        other_teaching = counts[OTHER_DEPARTMENT_CODE]["teaching_count"]
        other_non_teaching = counts[OTHER_DEPARTMENT_CODE]["non_teaching_count"]
        other_total = other_teaching + other_non_teaching
        if other_total > 0:
            departments.append({
                "department_code": OTHER_DEPARTMENT_CODE,
                "department_name": OTHER_DEPARTMENT_NAME,
                "teaching_count": other_teaching,
                "non_teaching_count": other_non_teaching,
                "total_count": other_total,
            })

        return jsonify({"departments": departments})
    except Exception as e:
        print(f"Error loading departments: {e}")
        return jsonify({"error": "Could not load departments"}), 500


@admin_bp.route("/departments/<string:department_code>/faculty", methods=["GET"])
@is_admin
def get_department_faculty(department_code):
    resolved_code = _resolve_department_code(department_code)
    if not resolved_code:
        return jsonify({"error": "Invalid department code"}), 400

    faculty_list = _load_faculty_rows()
    if not isinstance(faculty_list, list):
        faculty_list = []

    teaching = []
    non_teaching = []

    include_other = resolved_code == OTHER_DEPARTMENT_CODE
    for faculty in faculty_list:
        dept_code, _, staff_type = _normalize_faculty_shape(faculty)
        if include_other:
            if dept_code in CANONICAL_DEPARTMENTS:
                continue
        elif dept_code != resolved_code:
            continue
        row = _department_faculty_item(faculty)
        if staff_type == "NON_TEACHING":
            non_teaching.append(row)
        else:
            teaching.append(row)

    teaching.sort(key=lambda item: (item.get("name") or "").lower())
    non_teaching.sort(key=lambda item: (item.get("name") or "").lower())

    return jsonify({
        "department_code": resolved_code,
        "department_name": OTHER_DEPARTMENT_NAME if include_other else get_department_name(resolved_code),
        "teaching": teaching,
        "non_teaching": non_teaching,
    })


# ======================================================
# ADMIN - FACULTY PERSONAL LIST
# ======================================================
@admin_bp.route("/faculty-list", methods=["GET"])
@is_admin
def get_faculty_list():
    try:
        faculty = _load_faculty_rows()
        if not isinstance(faculty, list):
            faculty = []

        query = request.args.get("q", "").lower().strip()
        if query:
            faculty = [
                f for f in faculty
                if query in (f.get("name") or "").lower()
                or query in (f.get("faculty_id") or "").lower()
            ]

        faculty.sort(key=lambda x: (x.get("name") or "").lower())
        result = [_faculty_list_item(f) for f in faculty]
        return jsonify({"faculty": result, "count": len(result)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ======================================================
# UPLOAD PERSONAL DOCUMENT
# ======================================================
@admin_bp.route("/faculty/<faculty_id>/upload-doc", methods=["POST"])
@is_admin
def upload_personal_doc(faculty_id):
    try:
        if "file" not in request.files:
            return jsonify({"error": "No file part"}), 400

        file = request.files["file"]
        doc_type = request.form.get("doc_type")

        if not file or not file.filename:
            return jsonify({"error": "No file selected"}), 400

        rel_path = save_file(file, "personal", faculty_id, tag=doc_type)

        faculty_list = _load_faculty_rows()
        for fac in faculty_list:
            if fac.get("faculty_id") == faculty_id:
                if "personal_documents" not in fac:
                    fac["personal_documents"] = {}

                fac["personal_documents"][doc_type] = rel_path
                _save_faculty_rows(faculty_list)

                return jsonify({"message": "Uploaded successfully", "path": rel_path})

        return jsonify({"error": "Faculty not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@admin_bp.route("/upload-personal-doc/<faculty_id>", methods=["POST"])
@is_admin
def upload_personal_doc_admin(faculty_id):
    if "file" not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files["file"]
    doc_type = (request.form.get("doc_type") or "").strip()
    if doc_type not in ALLOWED_PERSONAL_DOC_TYPES:
        return jsonify({"error": "Invalid doc_type"}), 400

    rows = _load_faculty_rows()
    faculty = next((f for f in rows if f.get("faculty_id") == faculty_id), None)
    if not faculty:
        return jsonify({"error": "Faculty not found"}), 404

    rel_path = save_file(file, "personal", faculty_id, tag=doc_type)
    docs = faculty.setdefault("personal_documents", {})
    if doc_type == "others":
        docs.setdefault("others", []).append(rel_path)
    else:
        old = docs.get(doc_type)
        if old:
            delete_file(old)
        docs[doc_type] = rel_path

    _save_faculty_rows(rows)
    log_event("admin", _admin_actor(), "upload_personal_doc", "faculty", faculty_id, {"doc_type": doc_type})
    push_notification("faculty", faculty.get("username"), "Personal Document Updated", f"{doc_type} was uploaded/updated by admin.")
    return jsonify({"message": "Uploaded", "personal_documents": docs})


@admin_bp.route("/delete-personal-doc/<faculty_id>/<doc_type>", methods=["DELETE"])
@is_admin
def delete_personal_doc_admin(faculty_id, doc_type):
    if doc_type not in ALLOWED_PERSONAL_DOC_TYPES:
        return jsonify({"error": "Invalid doc_type"}), 400

    rows = _load_faculty_rows()
    faculty = next((f for f in rows if f.get("faculty_id") == faculty_id), None)
    if not faculty:
        return jsonify({"error": "Faculty not found"}), 404

    docs = faculty.setdefault("personal_documents", {})
    if doc_type == "others":
        target_path = request.args.get("path")
        if not target_path:
            return jsonify({"error": "path query param required for others"}), 400
        if target_path not in docs.get("others", []):
            return jsonify({"error": "Document not found"}), 404
        delete_file(target_path)
        docs["others"].remove(target_path)
    else:
        target_path = docs.get(doc_type)
        if not target_path:
            return jsonify({"error": "Document not found"}), 404
        delete_file(target_path)
        docs[doc_type] = ""

    _save_faculty_rows(rows)
    log_event("admin", _admin_actor(), "delete_personal_doc", "faculty", faculty_id, {"doc_type": doc_type})
    push_notification("faculty", faculty.get("username"), "Personal Document Removed", f"{doc_type} was removed by admin.")
    return jsonify({"message": "Deleted", "personal_documents": docs})


@admin_bp.route("/upload-qualification-doc/<faculty_id>", methods=["POST"])
@is_admin
def upload_qualification_doc_admin(faculty_id):
    if "file" not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files["file"]
    doc_type = (request.form.get("doc_type") or "").strip()
    if doc_type not in ALLOWED_QUAL_DOC_TYPES:
        return jsonify({"error": "Invalid doc_type"}), 400

    rows = _load_faculty_rows()
    faculty = next((f for f in rows if f.get("faculty_id") == faculty_id), None)
    if not faculty:
        return jsonify({"error": "Faculty not found"}), 404

    rel_path = save_file(file, "qualifications", faculty_id, tag=doc_type)
    docs = faculty.setdefault("qualification_documents", {})
    if doc_type == "others":
        docs.setdefault("others", []).append(rel_path)
    else:
        old = docs.get(doc_type)
        if old:
            delete_file(old)
        docs[doc_type] = rel_path

    _save_faculty_rows(rows)
    log_event("admin", _admin_actor(), "upload_qualification_doc", "faculty", faculty_id, {"doc_type": doc_type})
    push_notification("faculty", faculty.get("username"), "Qualification Document Updated", f"{doc_type} was uploaded/updated by admin.")
    return jsonify({"message": "Uploaded", "qualification_documents": docs})


@admin_bp.route("/delete-qualification-doc/<faculty_id>/<doc_type>", methods=["DELETE"])
@is_admin
def delete_qualification_doc_admin(faculty_id, doc_type):
    if doc_type not in ALLOWED_QUAL_DOC_TYPES:
        return jsonify({"error": "Invalid doc_type"}), 400

    rows = _load_faculty_rows()
    faculty = next((f for f in rows if f.get("faculty_id") == faculty_id), None)
    if not faculty:
        return jsonify({"error": "Faculty not found"}), 404

    docs = faculty.setdefault("qualification_documents", {})
    if doc_type == "others":
        target_path = request.args.get("path")
        if not target_path:
            return jsonify({"error": "path query param required for others"}), 400
        if target_path not in docs.get("others", []):
            return jsonify({"error": "Document not found"}), 404
        delete_file(target_path)
        docs["others"].remove(target_path)
    else:
        target_path = docs.get(doc_type)
        if not target_path:
            return jsonify({"error": "Document not found"}), 404
        delete_file(target_path)
        docs[doc_type] = ""

    _save_faculty_rows(rows)
    log_event("admin", _admin_actor(), "delete_qualification_doc", "faculty", faculty_id, {"doc_type": doc_type})
    push_notification("faculty", faculty.get("username"), "Qualification Document Removed", f"{doc_type} was removed by admin.")
    return jsonify({"message": "Deleted", "qualification_documents": docs})


@admin_bp.route("/verify-cert/<faculty_id>/<cert_id>", methods=["PUT"])
@is_admin
def verify_cert_admin(faculty_id, cert_id):
    rows = _load_faculty_rows()
    faculty = next((f for f in rows if f.get("faculty_id") == faculty_id), None)
    if not faculty:
        return jsonify({"error": "Faculty not found"}), 404

    cert = next((c for c in faculty.get("certifications", []) if c.get("cert_id") == cert_id), None)
    if not cert:
        return jsonify({"error": "Certification not found"}), 404

    cert["verified"] = True
    _save_faculty_rows(rows)
    log_event("admin", _admin_actor(), "verify_certification", "faculty", faculty_id, {"cert_id": cert_id})
    push_notification("faculty", faculty.get("username"), "Certification Verified", f"Certification '{cert.get('title', cert_id)}' has been verified.")
    return jsonify({"message": "Certification verified", "certification": cert})


@admin_bp.route("/delete-cert/<faculty_id>/<cert_id>", methods=["DELETE"])
@is_admin
def delete_cert_admin(faculty_id, cert_id):
    rows = _load_faculty_rows()
    faculty = next((f for f in rows if f.get("faculty_id") == faculty_id), None)
    if not faculty:
        return jsonify({"error": "Faculty not found"}), 404

    certs = faculty.get("certifications", [])
    idx = next((i for i, c in enumerate(certs) if c.get("cert_id") == cert_id), -1)
    if idx == -1:
        return jsonify({"error": "Certification not found"}), 404

    cert = certs.pop(idx)
    if cert.get("file"):
        delete_file(cert["file"])

    # unlink from subject expertise
    for item in faculty.get("subject_expertise", []):
        if isinstance(item, dict) and "cert_ids" in item:
            item["cert_ids"] = [x for x in (item.get("cert_ids") or []) if x != cert_id]

    _save_faculty_rows(rows)
    log_event("admin", _admin_actor(), "delete_certification", "faculty", faculty_id, {"cert_id": cert_id})
    push_notification("faculty", faculty.get("username"), "Certification Deleted", f"Certification '{cert.get('title', cert_id)}' was deleted by admin.")
    return jsonify({"message": "Certification deleted"})


@admin_bp.route("/faculty/<faculty_id>/subject-expertise", methods=["GET"])
@is_admin
def get_subject_expertise_admin(faculty_id):
    rows = _load_faculty_rows()
    faculty = next((f for f in rows if f.get("faculty_id") == faculty_id), None)
    if not faculty:
        return jsonify({"error": "Faculty not found"}), 404

    cert_ids = {c.get("cert_id") for c in faculty.get("certifications", [])}
    items = []
    for item in faculty.get("subject_expertise", []):
        if not isinstance(item, dict):
            continue
        linked = [cid for cid in (item.get("cert_ids") or []) if cid in cert_ids]
        items.append({
            "subject": item.get("subject"),
            "cert_ids": linked,
            "cert_count": len(linked),
        })
    return jsonify({"subject_expertise": items})


@admin_bp.route("/faculty/<faculty_id>/subject-expertise", methods=["POST"])
@is_admin
def add_subject_expertise_admin(faculty_id):
    data = request.json or {}
    subject = (data.get("subject") or "").strip()
    if not subject:
        return jsonify({"error": "subject is required"}), 400

    rows = _load_faculty_rows()
    faculty = next((f for f in rows if f.get("faculty_id") == faculty_id), None)
    if not faculty:
        return jsonify({"error": "Faculty not found"}), 404

    items = faculty.setdefault("subject_expertise", [])
    if any((x.get("subject") or "").lower() == subject.lower() for x in items if isinstance(x, dict)):
        return jsonify({"error": "Subject already exists"}), 409

    items.append({"subject": subject, "cert_ids": []})
    _save_faculty_rows(rows)
    return jsonify({"message": "Subject added", "subject_expertise": items})


@admin_bp.route("/faculty/<faculty_id>/subject-expertise/<path:subject>", methods=["DELETE"])
@is_admin
def delete_subject_expertise_admin(faculty_id, subject):
    rows = _load_faculty_rows()
    faculty = next((f for f in rows if f.get("faculty_id") == faculty_id), None)
    if not faculty:
        return jsonify({"error": "Faculty not found"}), 404

    items = faculty.setdefault("subject_expertise", [])
    new_items = [x for x in items if (x.get("subject") or "").lower() != subject.lower()]
    if len(new_items) == len(items):
        return jsonify({"error": "Subject not found"}), 404

    faculty["subject_expertise"] = new_items
    _save_faculty_rows(rows)
    return jsonify({"message": "Subject removed", "subject_expertise": new_items})


@admin_bp.route("/faculty/<faculty_id>/subject-expertise/<path:subject>/link-cert/<cert_id>", methods=["PUT"])
@is_admin
def link_subject_cert_admin(faculty_id, subject, cert_id):
    rows = _load_faculty_rows()
    faculty = next((f for f in rows if f.get("faculty_id") == faculty_id), None)
    if not faculty:
        return jsonify({"error": "Faculty not found"}), 404

    if not any(c.get("cert_id") == cert_id for c in faculty.get("certifications", [])):
        return jsonify({"error": "Certification not found"}), 404

    item = next((x for x in faculty.get("subject_expertise", []) if (x.get("subject") or "").lower() == subject.lower()), None)
    if not item:
        return jsonify({"error": "Subject not found"}), 404

    item.setdefault("cert_ids", [])
    if cert_id not in item["cert_ids"]:
        item["cert_ids"].append(cert_id)

    _save_faculty_rows(rows)
    return jsonify({"message": "Certification linked", "subject": item})


@admin_bp.route("/faculty/<faculty_id>/subject-expertise/<path:subject>/unlink-cert/<cert_id>", methods=["PUT"])
@is_admin
def unlink_subject_cert_admin(faculty_id, subject, cert_id):
    rows = _load_faculty_rows()
    faculty = next((f for f in rows if f.get("faculty_id") == faculty_id), None)
    if not faculty:
        return jsonify({"error": "Faculty not found"}), 404

    item = next((x for x in faculty.get("subject_expertise", []) if (x.get("subject") or "").lower() == subject.lower()), None)
    if not item:
        return jsonify({"error": "Subject not found"}), 404

    item["cert_ids"] = [x for x in (item.get("cert_ids") or []) if x != cert_id]
    _save_faculty_rows(rows)
    return jsonify({"message": "Certification unlinked", "subject": item})


# ======================================================
# FACULTY CRUD OPERATIONS
# ======================================================
def get_next_faculty_id(faculty_list):
    """Generates the next faculty ID, e.g., FAC1005 -> FAC1006"""
    if not faculty_list:
        return "FAC1001"
    max_id = 0
    for fac in faculty_list:
        try:
            num = int(fac.get("faculty_id", "FAC0").replace("FAC", ""))
            if num > max_id:
                max_id = num
        except (ValueError, AttributeError):
            continue
    return f"FAC{max_id + 1}"


@admin_bp.route("/faculty/<string:faculty_id>", methods=["GET"])
@is_admin
def get_faculty_by_id(faculty_id):
    faculty_list = _load_faculty_rows()
    faculty = next((f for f in faculty_list if f.get("faculty_id") == faculty_id), None)
    if faculty:
        dept_code, dept_name, staff_type = _normalize_faculty_shape(faculty)
        faculty["department"] = dept_name
        faculty["department_code"] = dept_code
        faculty["staff_type"] = staff_type
        return jsonify(_sanitize_faculty_response(faculty))
    return jsonify({"error": "Faculty not found"}), 404


@admin_bp.route("/faculty/<string:faculty_id>", methods=["PUT"])
@is_admin
def update_faculty(faculty_id):
    data = request.json or {}
    faculty_list = _load_faculty_rows()
    faculty_index = next((i for i, f in enumerate(faculty_list) if f.get("faculty_id") == faculty_id), -1)

    if faculty_index == -1:
        return jsonify({"error": "Faculty not found"}), 404

    faculty = faculty_list[faculty_index]

    new_username = (data.get("username") or "").strip() if "username" in data else None
    if new_username:
        for row in faculty_list:
            if row.get("faculty_id") != faculty_id and (row.get("username") or "").strip().lower() == new_username.lower():
                return jsonify({"error": "Username already exists"}), 409

    editable_fields = (
        "name",
        "designation",
        "normalized_role",
        "role",
        "permissions_json",
        "email",
        "official_email",
        "phone",
        "phone_number",
        "address",
        "emergency_contact_name",
        "emergency_contact_phone",
        "employment_type",
        "joining_date",
        "status",
        "account_locked",
        "assigned_subjects",
        "assigned_sections",
        "semester",
        "academic_year",
        "timetable_id",
        "weekly_workload_hours",
        "lecture_hours",
        "lab_hours",
        "highest_qualification",
        "qualifications_list",
        "research_area",
        "publications_list",
        "phd_status",
        "appraisal_score",
        "student_feedback_rating",
        "username",
        "qualifications",
        "publications",
        "subject_expertise",
        "department",
        "office_room",
        "extension",
        "admin_notes",
    )
    for field in editable_fields:
        if field in data:
            faculty[field] = data.get(field)

    if "department" in data:
        faculty["department"] = normalize_department_display(data.get("department"))
        faculty["department_code"] = canonicalize_department_code(data.get("department"))

    if "staff_type" in data:
        normalized_staff_type = normalize_staff_type(data.get("staff_type"))
        if normalized_staff_type:
            faculty["staff_type"] = normalized_staff_type
    elif "designation" in data and not faculty.get("staff_type"):
        faculty["staff_type"] = infer_staff_type_from_designation(faculty.get("designation"))

    # Role normalization: designation drives normalized role unless explicitly overridden by admin.
    if "designation" in data and "normalized_role" not in data:
        faculty["normalized_role"] = normalize_role_from_designation(faculty.get("designation"))
    if "normalized_role" in data:
        faculty["normalized_role"] = str(data.get("normalized_role") or "").strip().upper() or normalize_role_from_designation(faculty.get("designation"))
    faculty["role"] = faculty.get("normalized_role") or normalize_role_from_designation(faculty.get("designation"))
    if "permissions_json" in data and data.get("permissions_json"):
        faculty["permissions_json"] = data.get("permissions_json")
    elif not faculty.get("permissions_json"):
        faculty["permissions_json"] = default_permissions_json_for_role(faculty.get("normalized_role"))

    if data.get("password"):
        valid_pwd, pwd_msg = validate_password_strength(data.get("password"))
        if not valid_pwd:
            return jsonify({"error": pwd_msg}), 400
        faculty["password"] = hash_password(data.get("password"))

    _save_faculty_rows(faculty_list)
    log_event("admin", _admin_actor(), "update_faculty_profile", "faculty", faculty_id, {"fields": list(data.keys())})
    return jsonify(_sanitize_faculty_response(faculty))


@admin_bp.route("/faculty", methods=["POST"])
@is_admin
def create_faculty():
    data = request.json or {}
    faculty_list = _load_faculty_rows()
    if not isinstance(faculty_list, list):
        faculty_list = []

    if not all(k in data and data.get(k) for k in ("name", "department", "email")):
        return jsonify({"error": "Name, Department, and Email are required"}), 400

    if any(f.get("email") == data["email"] for f in faculty_list):
        return jsonify({"error": "Email already exists"}), 409

    requested_username = (data.get("username") or "").strip()
    if requested_username and any((f.get("username") or "").strip().lower() == requested_username.lower() for f in faculty_list):
        return jsonify({"error": "Username already exists"}), 409

    department_display = normalize_department_display(data.get("department"))
    department_code = canonicalize_department_code(data.get("department"))
    staff_type = (
        normalize_staff_type(data.get("staff_type"))
        or infer_staff_type_from_designation(data.get("designation"))
    )

    new_faculty_id = get_next_faculty_id(faculty_list)
    requested_password = str(data.get("password") or "password@123")
    valid_pwd, pwd_msg = validate_password_strength(requested_password)
    if not valid_pwd:
        return jsonify({"error": pwd_msg}), 400

    new_faculty = {
        "faculty_id": new_faculty_id,
        "name": data["name"],
        "full_name": data.get("full_name") or data["name"],
        "gender": data.get("gender", ""),
        "date_of_birth": data.get("date_of_birth", ""),
        "department": department_display,
        "department_code": department_code,
        "staff_type": staff_type,
        "designation": data.get("designation", ""),
        "normalized_role": str(data.get("normalized_role") or normalize_role_from_designation(data.get("designation", ""))).strip().upper(),
        "role": str(data.get("normalized_role") or normalize_role_from_designation(data.get("designation", ""))).strip().upper(),
        "email": data["email"],
        "official_email": data.get("official_email") or data["email"],
        "phone": data.get("phone", ""),
        "phone_number": data.get("phone_number") or data.get("phone", ""),
        "address": data.get("address", ""),
        "emergency_contact_name": data.get("emergency_contact_name", ""),
        "emergency_contact_phone": data.get("emergency_contact_phone", ""),
        "employment_type": data.get("employment_type", ""),
        "joining_date": data.get("joining_date", ""),
        "status": data.get("status", "Active"),
        "account_locked": bool(data.get("account_locked", False)),
        "username": requested_username or new_faculty_id.lower(),
        "password": hash_password(requested_password),
        "permissions_json": data.get("permissions_json") or default_permissions_json_for_role(
            str(data.get("normalized_role") or normalize_role_from_designation(data.get("designation", ""))).strip().upper()
        ),
        "photo": "",
        "qualifications": data.get("qualifications", []),
        "qualifications_list": data.get("qualifications_list", []),
        "highest_qualification": data.get("highest_qualification", ""),
        "research_area": data.get("research_area", ""),
        "publications": data.get("publications", []),
        "publications_list": data.get("publications_list", []),
        "subject_expertise": [
            {"subject": s.get("subject"), "cert_ids": list(s.get("cert_ids", []))}
            if isinstance(s, dict) else {"subject": str(s), "cert_ids": []}
            for s in data.get("subject_expertise", [])
            if s
        ],
        "assigned_subjects": data.get("assigned_subjects", []),
        "assigned_sections": data.get("assigned_sections", []),
        "semester": data.get("semester", ""),
        "academic_year": data.get("academic_year", ""),
        "timetable_id": data.get("timetable_id", ""),
        "weekly_workload_hours": data.get("weekly_workload_hours", 0),
        "lecture_hours": data.get("lecture_hours", 0),
        "lab_hours": data.get("lab_hours", 0),
        "personal_documents": {
            "aadhaar": "",
            "pan": "",
            "bank_passbook": "",
            "service_register": "",
            "joining_letter": "",
            "others": [],
        },
        "qualification_documents": {
            "ssc_memo": "",
            "inter_memo": "",
            "btech_memo": "",
            "mtech_memo": "",
            "phd_memo": "",
            "others": [],
        },
        "certifications": [],
        "phd_status": data.get("phd_status", ""),
        "appraisal_score": data.get("appraisal_score", 0),
        "student_feedback_rating": data.get("student_feedback_rating", 0),
        "research_profiles": {},
    }

    faculty_list.append(new_faculty)
    _save_faculty_rows(faculty_list)
    log_event("admin", _admin_actor(), "create_faculty_profile", "faculty", new_faculty_id)
    payload = _sanitize_faculty_response(new_faculty)
    payload["initial_password"] = requested_password
    return jsonify(payload), 201


@admin_bp.route("/faculty/<string:faculty_id>/upload-photo", methods=["POST"])
@is_admin
def admin_upload_faculty_photo(faculty_id):
    file = request.files.get("photo")
    if not file or not file.filename:
        return jsonify({"error": "Photo file is required"}), 400
    if not _allowed_photo(file.filename):
        return jsonify({"error": "Invalid image type"}), 400

    rows = _load_faculty_rows()
    faculty = next((f for f in rows if f.get("faculty_id") == faculty_id), None)
    if not faculty:
        return jsonify({"error": "Faculty not found"}), 404

    os.makedirs(ADMIN_PHOTO_UPLOAD_DIR, exist_ok=True)
    ext = secure_filename(file.filename).rsplit(".", 1)[1].lower()
    unique_name = f"{faculty_id}__photo__{uuid.uuid4().hex[:10]}.{ext}"
    abs_path = os.path.join(ADMIN_PHOTO_UPLOAD_DIR, unique_name)
    file.save(abs_path)

    old_photo = faculty.get("photo", "")
    faculty["photo"] = f"/static/uploads/faculty/{unique_name}"
    _save_faculty_rows(rows)
    _delete_photo_file_if_local(old_photo)
    log_event("admin", _admin_actor(), "upload_faculty_photo", "faculty", faculty_id)
    push_notification("faculty", faculty.get("username"), "Profile Photo Updated", "Your profile photo was updated by admin.")

    return jsonify({"message": "Photo uploaded", "photo": faculty["photo"]})


@admin_bp.route("/faculty/<string:faculty_id>/remove-photo", methods=["DELETE"])
@is_admin
def admin_remove_faculty_photo(faculty_id):
    rows = _load_faculty_rows()
    faculty = next((f for f in rows if f.get("faculty_id") == faculty_id), None)
    if not faculty:
        return jsonify({"error": "Faculty not found"}), 404

    old_photo = faculty.get("photo", "")
    faculty["photo"] = ""
    _save_faculty_rows(rows)
    _delete_photo_file_if_local(old_photo)
    log_event("admin", _admin_actor(), "remove_faculty_photo", "faculty", faculty_id)
    push_notification("faculty", faculty.get("username"), "Profile Photo Removed", "Your profile photo was removed by admin.")

    return jsonify({"message": "Photo removed", "photo": ""})


@admin_bp.route("/analytics/overview", methods=["GET"])
@is_admin
def admin_analytics_overview():
    rows = _load_faculty_rows()
    total = len(rows)
    completed_personal = 0
    completed_qualification = 0
    cert_pending = 0
    cert_verified = 0

    for row in rows:
        pdocs = row.get("personal_documents", {}) or {}
        qdocs = row.get("qualification_documents", {}) or {}
        pcount = sum(1 for k in ("aadhaar", "pan", "bank_passbook", "service_register", "joining_letter") if pdocs.get(k))
        qcount = sum(1 for k in ("ssc_memo", "inter_memo", "btech_memo", "mtech_memo", "phd_memo") if qdocs.get(k))
        if pcount == 5:
            completed_personal += 1
        if qcount == 5:
            completed_qualification += 1

        for cert in row.get("certifications", []) or []:
            if cert.get("verified"):
                cert_verified += 1
            else:
                cert_pending += 1

    return jsonify({
        "total_faculty": total,
        "personal_docs_complete": completed_personal,
        "qualification_docs_complete": completed_qualification,
        "certifications_verified": cert_verified,
        "certifications_pending": cert_pending,
    })


@admin_bp.route("/audit-logs", methods=["GET"])
@is_admin
def admin_audit_logs():
    limit = request.args.get("limit", 200, type=int)
    from utils.audit_service import get_logs
    return jsonify({"logs": get_logs(limit=limit)})


@admin_bp.route("/export/audit-logs", methods=["GET"])
@is_admin
def export_audit_logs_excel():
    from utils.audit_service import get_logs

    logs = get_logs(limit=request.args.get("limit", 5000, type=int))
    rows = []
    for item in logs:
        rows.append({
            "Timestamp (UTC)": item.get("timestamp", ""),
            "Actor Role": item.get("actor_role", ""),
            "Actor ID": item.get("actor_id", ""),
            "Action": item.get("action", ""),
            "Target Type": item.get("target_type", ""),
            "Target ID": item.get("target_id", ""),
            "Meta": str(item.get("meta", {})),
        })

    export_path = os.path.join(BASE_DIR, "data", "exports", "audit_logs_export.xlsx")
    os.makedirs(os.path.dirname(export_path), exist_ok=True)
    pd.DataFrame(rows).to_excel(export_path, index=False)

    return send_file(
        export_path,
        as_attachment=True,
        download_name="audit_logs.xlsx",
    )


@admin_bp.route("/notifications", methods=["GET"])
@is_admin
def admin_notifications():
    unread_only = request.args.get("unread") == "1"
    limit = request.args.get("limit", 100, type=int)
    notes = list_notifications("admin", _admin_actor(), unread_only=unread_only, limit=limit)
    return jsonify({"notifications": notes})


@admin_bp.route("/notifications/<notification_id>/read", methods=["PUT"])
@is_admin
def admin_notification_mark_read(notification_id):
    ok = mark_as_read("admin", _admin_actor(), notification_id)
    if not ok:
        return jsonify({"error": "Notification not found"}), 404
    return jsonify({"message": "Notification marked as read"})


@admin_bp.route("/impersonate/<string:faculty_id>", methods=["POST"])
@is_admin
def admin_impersonate_faculty(faculty_id):
    rows = _load_faculty_rows()
    faculty = next((f for f in rows if f.get("faculty_id") == faculty_id), None)
    if not faculty:
        return jsonify({"error": "Faculty not found"}), 404
    session["impersonate_faculty_id"] = faculty_id
    log_event("admin", _admin_actor(), "impersonate_faculty_dashboard", "faculty", faculty_id)
    return jsonify({"message": "Impersonation enabled", "faculty_id": faculty_id, "redirect": "/faculty-dashboard"})


@admin_bp.route("/impersonation/stop", methods=["POST"])
@is_admin
def admin_stop_impersonation():
    previous = session.pop("impersonate_faculty_id", None)
    if previous:
        log_event("admin", _admin_actor(), "stop_impersonation", "faculty", previous)
    return jsonify({"message": "Impersonation stopped"})


@admin_bp.route("/faculty/<string:faculty_id>/lock", methods=["PUT"])
@is_admin
def admin_lock_unlock_faculty(faculty_id):
    data = request.json or {}
    locked = bool(data.get("locked", True))
    rows = _load_faculty_rows()
    faculty = next((f for f in rows if f.get("faculty_id") == faculty_id), None)
    if not faculty:
        return jsonify({"error": "Faculty not found"}), 404
    faculty["account_locked"] = locked
    _save_faculty_rows(rows)
    action = "lock_account" if locked else "unlock_account"
    log_event("admin", _admin_actor(), action, "faculty", faculty_id)
    push_notification("faculty", faculty.get("username"), "Account Status Updated", f"Your account has been {'locked' if locked else 'unlocked'} by admin.")
    return jsonify({"message": f"Account {'locked' if locked else 'unlocked'}", "account_locked": locked})


@admin_bp.route("/faculty/<string:faculty_id>/reset-password", methods=["POST"])
@is_admin
def admin_reset_faculty_password(faculty_id):
    data = request.json or {}
    new_password = str(data.get("new_password") or "password@123").strip()
    valid_pwd, pwd_msg = validate_password_strength(new_password)
    if not valid_pwd:
        return jsonify({"error": pwd_msg}), 400

    rows = _load_faculty_rows()
    faculty = next((f for f in rows if f.get("faculty_id") == faculty_id), None)
    if not faculty:
        return jsonify({"error": "Faculty not found"}), 404
    faculty["password"] = hash_password(new_password)
    _save_faculty_rows(rows)
    log_event("admin", _admin_actor(), "reset_faculty_password", "faculty", faculty_id)
    push_notification("faculty", faculty.get("username"), "Password Reset", "Your password has been reset by admin.")
    return jsonify({"message": "Password reset successfully", "faculty_id": faculty_id, "temporary_password": new_password})


@admin_bp.route("/faculty/<string:faculty_id>/clear-doc-submissions", methods=["DELETE"])
@is_admin
def admin_clear_doc_submissions(faculty_id):
    rows = _load_faculty_rows()
    faculty = next((f for f in rows if f.get("faculty_id") == faculty_id), None)
    if not faculty:
        return jsonify({"error": "Faculty not found"}), 404

    _clear_personal_and_qualification_docs(faculty)
    _save_faculty_rows(rows)

    log_event("admin", _admin_actor(), "clear_doc_submissions", "faculty", faculty_id)
    push_notification("faculty", faculty.get("username"), "Document Submissions Cleared", "Your personal and qualification document submissions were cleared by admin.")
    return jsonify({
        "message": "Document submissions cleared",
        "personal_documents": faculty.get("personal_documents", {}),
        "qualification_documents": faculty.get("qualification_documents", {}),
    })


@admin_bp.route("/faculty/<string:faculty_id>/clear-rd-submissions", methods=["DELETE"])
@is_admin
def admin_clear_rd_submissions(faculty_id):
    rows = _load_faculty_rows()
    faculty = next((f for f in rows if f.get("faculty_id") == faculty_id), None)
    if not faculty:
        return jsonify({"error": "Faculty not found"}), 404

    _clear_rd_submissions(faculty)
    _save_faculty_rows(rows)

    log_event("admin", _admin_actor(), "clear_rd_submissions", "faculty", faculty_id)
    push_notification("faculty", faculty.get("username"), "R&D Submissions Cleared", "Your R&D submissions were cleared by admin.")
    return jsonify({"message": "R&D submissions cleared"})
