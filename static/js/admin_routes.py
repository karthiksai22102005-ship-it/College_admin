from flask import Blueprint, jsonify, request, session, abort
from functools import wraps
from utils.data_store import load_data, save_data

# ======================================================
# SETUP
# ======================================================
admin_bp = Blueprint("admin_bp", __name__)
FACULTY_STORE = "data/faculty.store"

# ======================================================
# DECORATORS
# ======================================================
def is_admin(f):
    """Decorator to ensure user is an admin."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'role' not in session or session.get('role') != 'admin':
            abort(403) # Forbidden
        return f(*args, **kwargs)
    return decorated_function

# ======================================================
# HELPERS
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

# ======================================================
# ADMIN API ROUTES
# ======================================================

@admin_bp.route("/faculty-list", methods=["GET"])
@is_admin
def get_all_faculty():
    faculty_list = load_data(FACULTY_STORE)
    summary_list = [{
        "faculty_id": f.get("faculty_id"), "name": f.get("name"),
        "department": f.get("department"), "designation": f.get("designation"),
        "email": f.get("email"), "photo": f.get("photo")
    } for f in faculty_list]
    return jsonify({"faculty": summary_list})

@admin_bp.route("/departments", methods=["GET"])
@is_admin
def get_departments():
    faculty_list = load_data(FACULTY_STORE)

    # 🔹 normalize department names (CRITICAL)
    def normalize_dept(dept):
        if not dept:
            return None

        d = dept.lower().strip().replace("&", "and")

        # AIML normalization
        if "ai" in d and "ml" in d:
            return "AIML"

        # AIDS normalization
        if "ai" in d and ("ds" in d or "data" in d):
            return "AIDS"

        # remove garbage departments
        if d in ["fed", "general", ""]:
            return None

        return dept.strip()

    # 🔹 collect normalized departments from faculty
    faculty_depts = set()
    for f in faculty_list:
        norm = normalize_dept(f.get("department"))
        if norm:
            faculty_depts.add(norm)

    # 🔹 ensure AIML and AIDS always present
    faculty_depts.update(["AIML", "AIDS"])

    departments = sorted(faculty_depts)

    return jsonify({"departments": departments})

@admin_bp.route("/faculty/<string:faculty_id>", methods=["GET"])
@is_admin
def get_faculty_by_id(faculty_id):
    faculty_list = load_data(FACULTY_STORE)
    faculty = next((f for f in faculty_list if f.get("faculty_id") == faculty_id), None)
    if faculty:
        return jsonify(faculty)
    return jsonify({"error": "Faculty not found"}), 404

@admin_bp.route("/faculty/<string:faculty_id>", methods=["PUT"])
@is_admin
def update_faculty(faculty_id):
    data = request.json
    faculty_list = load_data(FACULTY_STORE)
    faculty_index = next((i for i, f in enumerate(faculty_list) if f.get("faculty_id") == faculty_id), -1)

    if faculty_index == -1:
        return jsonify({"error": "Faculty not found"}), 404

    # Update fields from payload
    faculty_list[faculty_index].update({
        "name": data.get("name"), "designation": data.get("designation"),
        "email": data.get("email"), "phone": data.get("phone"),
        "username": data.get("username"), "qualifications": data.get("qualifications"),
        "publications": data.get("publications"), "subject_expertise": data.get("subject_expertise")
    })
    if data.get("password"):
        faculty_list[faculty_index]["password"] = data.get("password")

    save_data(FACULTY_STORE, faculty_list)
    return jsonify(faculty_list[faculty_index])

@admin_bp.route("/faculty", methods=["POST"])
@is_admin
def create_faculty():
    data = request.json
    faculty_list = load_data(FACULTY_STORE)

    if not all(k in data for k in ["name", "department", "email"]):
        return jsonify({"error": "Name, Department, and Email are required"}), 400

    if any(f.get("email") == data["email"] for f in faculty_list):
        return jsonify({"error": "Email already exists"}), 409

    new_faculty_id = get_next_faculty_id(faculty_list)
    new_faculty = {
        "faculty_id": new_faculty_id, "name": data["name"], "department": data["department"],
        "designation": data.get("designation", ""), "email": data["email"], "phone": data.get("phone", ""),
        "username": data.get("username", new_faculty_id.lower()), "password": data.get("password", "password@123"),
        "photo": "", "qualifications": [], "publications": [], "subject_expertise": [],
        "personal_documents": {
            "aadhaar": "", "pan": "", "bank_passbook": "", "service_register": "", "joining_letter": "", "others": []
        },
        "certifications": [], "research_profiles": {}
    }

    faculty_list.append(new_faculty)
    save_data(FACULTY_STORE, faculty_list)
    return jsonify(new_faculty), 201
