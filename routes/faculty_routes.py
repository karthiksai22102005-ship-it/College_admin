from flask import Blueprint, request, jsonify, session
from utils.data_store import load_data, save_data, load_faculty_data, ensure_faculty_schema_record
from utils.id_generator import generate_faculty_id
from utils.guards import faculty_self_required, role_required
from utils.file_handler import save_file, delete_file
from utils.security import hash_password, check_password, is_password_hash
from utils.audit_service import log_event
from utils.notification_service import push_notification, list_notifications, mark_as_read
from utils.password_policy import validate_password_strength
from utils.rbac import normalize_role_from_designation, default_permissions_json_for_role
import os
from werkzeug.utils import secure_filename
import json
import uuid

faculty_bp = Blueprint("faculty_bp", __name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FACULTY_STORE = os.path.join(BASE_DIR, "data", "faculty.store")
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads", "photos")
FACULTY_PHOTO_UPLOAD_DIR = os.path.join(BASE_DIR, "static", "uploads", "faculty")
ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'gif'}
ALLOWED_PERSONAL_DOC_TYPES = {"aadhaar", "pan", "bank_passbook", "service_register", "joining_letter", "others"}
ALLOWED_QUAL_DOC_TYPES = {"ssc_memo", "inter_memo", "btech_memo", "mtech_memo", "phd_memo", "others"}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def _load_rows():
    return load_faculty_data(FACULTY_STORE)


def _save_rows(rows):
    save_data(FACULTY_STORE, [ensure_faculty_schema_record(r) for r in rows])


def _sanitize_faculty_response(fac):
    payload = dict(fac or {})
    payload.pop("password", None)
    payload.pop("password_hash", None)
    return payload


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def _delete_faculty_photo_if_local(photo_path):
    if not photo_path:
        return
    normalized = str(photo_path).replace("\\", "/")
    if normalized.startswith("/static/uploads/faculty/"):
        file_name = normalized.split("/static/uploads/faculty/", 1)[1]
        abs_path = os.path.join(FACULTY_PHOTO_UPLOAD_DIR, file_name)
        if os.path.exists(abs_path):
            try:
                os.remove(abs_path)
            except OSError:
                pass


# ================= CREATE =================
@faculty_bp.route("/create", methods=["POST"])
@role_required("admin")
def create_faculty():
    try:
        data = request.json
        
        if not data:
            return jsonify({"error": "No data provided"}), 400
        
        faculty_list = load_data(FACULTY_STORE)
        
        # Handle if faculty_list is None or not a list
        if not isinstance(faculty_list, list):
            faculty_list = []

        faculty_id = f"FAC{len(faculty_list)+1:03d}"
        
        # Use provided username/password or auto-generate
        username = data.get("username", "").strip()
        password = data.get("password", "").strip()
        
        if not username:
            username = faculty_id
        if not password:
            password = faculty_id
        valid_pwd, pwd_msg = validate_password_strength(password)
        if not valid_pwd:
            return jsonify({"error": pwd_msg}), 400
        
        new_faculty = {
            "faculty_id": faculty_id,
            "name": data.get("name"),
            "full_name": data.get("full_name") or data.get("name"),
            "department": data.get("department"),
            "designation": data.get("designation", ""),
            "normalized_role": normalize_role_from_designation(data.get("designation", "")),
            "role": normalize_role_from_designation(data.get("designation", "")),
            "email": data.get("email", ""),
            "official_email": data.get("official_email") or data.get("email", ""),
            "phone": data.get("phone", ""),
            "phone_number": data.get("phone_number") or data.get("phone", ""),
            "dob": data.get("dob", ""),
            "date_of_birth": data.get("date_of_birth") or data.get("dob", ""),
            "username": username,
            "password": hash_password(password),
            "permissions_json": default_permissions_json_for_role(normalize_role_from_designation(data.get("designation", ""))),
            "photo": "",
            "qualifications": data.get("qualifications", []),
            "subject_expertise": data.get("subject_expertise", []),
            "publications": data.get("publications", []),
            "books": [],
            "research_papers": []
        }

        faculty_list.append(new_faculty)
        save_data(FACULTY_STORE, faculty_list)

        return jsonify({
            "message": "Faculty created",
            "faculty_id": new_faculty["faculty_id"],
            "username": new_faculty["username"],
            "password": password
        }), 201
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ================= CREATE WITH PHOTO =================
@faculty_bp.route("/create-with-photo", methods=["POST"])
@role_required("admin")
def create_faculty_with_photo():
    try:
        file = request.files.get("photo")
        faculty_data_str = request.form.get("faculty_data")
        
        if not faculty_data_str:
            return jsonify({"error": "No faculty data"}), 400
        
        try:
            data = json.loads(faculty_data_str)
        except:
            return jsonify({"error": "Invalid faculty data format"}), 400

        faculty_list = load_data(FACULTY_STORE)
        
        # Handle if faculty_list is None or not a list
        if not isinstance(faculty_list, list):
            faculty_list = []
        
        faculty_id = f"FAC{len(faculty_list)+1:03d}"
        photo_path = ""
        
        if file and file.filename and allowed_file(file.filename):
            filename = secure_filename(f"{faculty_id}_{file.filename}")
            photo_path = os.path.join(UPLOAD_FOLDER, filename)
            os.makedirs(os.path.dirname(photo_path), exist_ok=True)
            file.save(photo_path)
            photo_path = "/" + photo_path.replace("\\", "/")

        # Use provided username/password or auto-generate
        username = data.get("username", "").strip()
        password = data.get("password", "").strip()
        
        if not username:
            username = faculty_id
        if not password:
            password = faculty_id
        valid_pwd, pwd_msg = validate_password_strength(password)
        if not valid_pwd:
            return jsonify({"error": pwd_msg}), 400

        new_faculty = {
            "faculty_id": faculty_id,
            "name": data.get("name"),
            "full_name": data.get("full_name") or data.get("name"),
            "department": data.get("department"),
            "designation": data.get("designation", ""),
            "normalized_role": normalize_role_from_designation(data.get("designation", "")),
            "role": normalize_role_from_designation(data.get("designation", "")),
            "email": data.get("email", ""),
            "official_email": data.get("official_email") or data.get("email", ""),
            "phone": data.get("phone", ""),
            "phone_number": data.get("phone_number") or data.get("phone", ""),
            "dob": data.get("dob", ""),
            "date_of_birth": data.get("date_of_birth") or data.get("dob", ""),
            "username": username,
            "password": hash_password(password),
            "permissions_json": default_permissions_json_for_role(normalize_role_from_designation(data.get("designation", ""))),
            "photo": photo_path,
            "qualifications": data.get("qualifications", []),
            "subject_expertise": data.get("subject_expertise", []),
            "publications": data.get("publications", []),
            "books": [],
            "research_papers": []
        }

        faculty_list.append(new_faculty)
        save_data(FACULTY_STORE, faculty_list)

        return jsonify({
            "message": "Faculty created",
            "faculty_id": new_faculty["faculty_id"],
            "username": new_faculty["username"],
            "password": password
        }), 201
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ================= GET BY ID =================
@faculty_bp.route("/<faculty_id>", methods=["GET"])
def get_faculty(faculty_id):
    role = session.get("role")
    if role == "faculty" and session.get("faculty_id") != faculty_id:
        return jsonify({"error": "Forbidden"}), 403
    if role not in ("admin", "faculty"):
        return jsonify({"error": "Not authorized"}), 401

    faculty_list = load_data(FACULTY_STORE)

    for fac in faculty_list:
        if fac.get("faculty_id") == faculty_id:
            return jsonify(_sanitize_faculty_response(fac))

    return jsonify({"error": "Faculty not found"}), 404


# ================= GET BY DEPARTMENT =================
# ================= GET BY DEPARTMENT =================
@faculty_bp.route("/department/<dept>", methods=["GET"])
@role_required("admin")
def get_by_department(dept):
    faculty_list = load_data(FACULTY_STORE)
    
    # Helper to normalize for comparison
    def normalize(d):
        s = str(d).lower().strip().replace("&", "and")
        if "aids" in s or "data" in s or "ai and ds" in s: return "aids"
        if "aiml" in s or "machine" in s or "ai and ml" in s: return "aiml"
        if "cyber" in s: return "cyber security"
        return s

    target = normalize(dept)

    # ✅ Normalized match to handle "AI & ML" vs "AIML"
    result = [
        f for f in faculty_list
        if normalize(f.get("department", "")) == target
    ]

    return jsonify(result)


# ================= UPDATE (CRITICAL) =================
@faculty_bp.route("/update/<faculty_id>", methods=["PUT"])
@role_required("admin")
def update_faculty(faculty_id):
    data = request.json
    faculty_list = load_data(FACULTY_STORE)

    for fac in faculty_list:
        if fac.get("faculty_id") == faculty_id:

            fac["name"] = data.get("name", fac.get("name"))
            fac["designation"] = data.get("designation", fac.get("designation"))
            fac["email"] = data.get("email", fac.get("email"))
            fac["phone"] = data.get("phone", fac.get("phone"))
            fac["dob"] = data.get("dob", fac.get("dob"))
            fac["department"] = data.get("department", fac.get("department")) # Allow department correction

            # Credentials persistence - can be updated multiple times
            fac["username"] = data.get("username", fac.get("username"))
            if "password" in data and str(data.get("password") or "").strip():
                valid_pwd, pwd_msg = validate_password_strength(data.get("password"))
                if not valid_pwd:
                    return jsonify({"error": pwd_msg}), 400
                fac["password"] = hash_password(data.get("password"))

            save_data(FACULTY_STORE, faculty_list)
            
            # Return updated faculty data
            return jsonify({
                "message": "Updated successfully",
                "faculty": _sanitize_faculty_response(fac)
            }), 200

    return jsonify({"error": "Faculty not found"}), 404


# ================= DELETE =================
@faculty_bp.route("/delete/<faculty_id>", methods=["DELETE"])
@role_required("admin")
def delete_faculty(faculty_id):
    faculty_list = load_data(FACULTY_STORE)

    for i, fac in enumerate(faculty_list):
        if fac.get("faculty_id") == faculty_id:
            faculty_list.pop(i)
            save_data(FACULTY_STORE, faculty_list)
            return jsonify({"message": "Deleted"}), 200

    return jsonify({"error": "Faculty not found"}), 404


# ================= GET SELF PROFILE (FACULTY DASHBOARD) =================
@faculty_bp.route("/my-profile", methods=["GET"])
def get_faculty_self():
    if "faculty_id" not in session:
        return jsonify({"error": "Not authorized"}), 401
    
    faculty_id = session.get("faculty_id")
    faculty_list = load_data(FACULTY_STORE)

    for fac in faculty_list:
        if fac.get("faculty_id") == faculty_id:
            return jsonify(_sanitize_faculty_response(fac)), 200

    return jsonify({"error": "Faculty not found"}), 404


# ================= UPDATE SELF (FACULTY ONLY) =================
@faculty_bp.route("/update-self", methods=["PUT"])
def update_faculty_self():
    if "faculty_id" not in session:
        return jsonify({"error": "Not authorized"}), 401
    
    try:
        data = request.json
        faculty_id = session.get("faculty_id")
        faculty_list = load_data(FACULTY_STORE)

        for fac in faculty_list:
            if fac.get("faculty_id") == faculty_id:
                # Only allow these fields to be updated by faculty
                if "email" in data:
                    fac["email"] = data["email"]
                if "phone" in data:
                    fac["phone"] = data["phone"]
                if "subject_expertise" in data:
                    fac["subject_expertise"] = data["subject_expertise"]
                if "qualifications" in data:
                    fac["qualifications"] = data["qualifications"]
                if "publications" in data:
                    fac["publications"] = data["publications"]

                save_data(FACULTY_STORE, faculty_list)
                
                return jsonify({
                    "message": "Profile updated successfully",
                    "faculty": fac
                }), 200

        return jsonify({"error": "Faculty not found"}), 404
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ================= UPDATE PHOTO (FACULTY) =================
@faculty_bp.route("/update-photo", methods=["POST"])
def update_faculty_photo():
    if "faculty_id" not in session:
        return jsonify({"error": "Not authorized"}), 401
    
    try:
        file = request.files.get("photo")
        
        if not file or not file.filename:
            return jsonify({"error": "No file provided"}), 400
        
        if not allowed_file(file.filename):
            return jsonify({"error": "Invalid file type"}), 400
        
        faculty_id = session.get("faculty_id")
        faculty_list = load_data(FACULTY_STORE)

        for fac in faculty_list:
            if fac.get("faculty_id") == faculty_id:
                filename = secure_filename(f"{faculty_id}_{file.filename}")
                photo_path = os.path.join(UPLOAD_FOLDER, filename)
                os.makedirs(os.path.dirname(photo_path), exist_ok=True)
                file.save(photo_path)
                photo_path = "/" + photo_path.replace("\\", "/")
                
                fac["photo"] = photo_path
                save_data(FACULTY_STORE, faculty_list)
                
                return jsonify({
                    "message": "Photo updated successfully",
                    "photo": photo_path
                }), 200

        return jsonify({"error": "Faculty not found"}), 404
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ================= ADD QUALIFICATION =================
@faculty_bp.route("/add-qualification/<faculty_id>", methods=["POST"])
@role_required("admin")
def add_qualification(faculty_id):
    data = request.json
    faculty_list = load_data(FACULTY_STORE)

    for fac in faculty_list:
        if fac.get("faculty_id") == faculty_id:
            qualification = {
                "type": data.get("type"),
                "year": data.get("year", "")
            }
            if "qualifications" not in fac:
                fac["qualifications"] = []
            fac["qualifications"].append(qualification)
            save_data(FACULTY_STORE, faculty_list)
            return jsonify({"message": "Qualification added"}), 201

    return jsonify({"error": "Faculty not found"}), 404


# ================= ADD EXPERTISE =================
@faculty_bp.route("/add-expertise/<faculty_id>", methods=["POST"])
@role_required("admin")
def add_expertise(faculty_id):
    data = request.json
    faculty_list = load_data(FACULTY_STORE)

    for fac in faculty_list:
        if fac.get("faculty_id") == faculty_id:
            if "subject_expertise" not in fac:
                fac["subject_expertise"] = []
            fac["subject_expertise"].append(data.get("subject"))
            save_data(FACULTY_STORE, faculty_list)
            return jsonify({"message": "Expertise added"}), 201

    return jsonify({"error": "Faculty not found"}), 404


# ================= ADD PUBLICATION =================
@faculty_bp.route("/add-publication/<faculty_id>", methods=["POST"])
@role_required("admin")
def add_publication(faculty_id):
    data = request.json
    faculty_list = load_data(FACULTY_STORE)

    for fac in faculty_list:
        if fac.get("faculty_id") == faculty_id:
            publication = {
                "title": data.get("title"),
                "year": data.get("year", ""),
                "journal": data.get("journal", ""),
                "doi": data.get("doi", "")
            }
            if "publications" not in fac:
                fac["publications"] = []
            fac["publications"].append(publication)
            save_data(FACULTY_STORE, faculty_list)
            return jsonify({"message": "Publication added"}), 201

    return jsonify({"error": "Faculty not found"}), 404


# ================= ADD BOOK =================
@faculty_bp.route("/add-book/<faculty_id>", methods=["POST"])
@role_required("admin")
def add_book(faculty_id):
    data = request.json
    faculty_list = load_data(FACULTY_STORE)

    for fac in faculty_list:
        if fac.get("faculty_id") == faculty_id:
            book = {
                "title": data.get("title"),
                "author": data.get("author", ""),
                "isbn": data.get("isbn", ""),
                "year": data.get("year", "")
            }
            if "books" not in fac:
                fac["books"] = []
            fac["books"].append(book)
            save_data(FACULTY_STORE, faculty_list)
            return jsonify({"message": "Book added"}), 201

    return jsonify({"error": "Faculty not found"}), 404


# ================= ADD RESEARCH PAPER =================
@faculty_bp.route("/add-paper/<faculty_id>", methods=["POST"])
@role_required("admin")
def add_research_paper(faculty_id):
    data = request.json
    faculty_list = load_data(FACULTY_STORE)

    for fac in faculty_list:
        if fac.get("faculty_id") == faculty_id:
            paper = {
                "title": data.get("title"),
                "year": data.get("year", ""),
                "journal": data.get("journal", ""),
                "doi": data.get("doi", "")
            }
            if "research_papers" not in fac:
                fac["research_papers"] = []
            fac["research_papers"].append(paper)
            save_data(FACULTY_STORE, faculty_list)
            return jsonify({"message": "Research paper added"}), 201

    return jsonify({"error": "Faculty not found"}), 404


# ================= UPDATE RESEARCH PROFILES =================
@faculty_bp.route("/update-research-profiles", methods=["POST"])
def update_research_profiles():
    if "faculty_id" not in session:
        return jsonify({"error": "Not authorized"}), 401
    
    try:
        data = request.json
        faculty_id = session.get("faculty_id")
        faculty_list = load_data(FACULTY_STORE)

        for fac in faculty_list:
            if fac.get("faculty_id") == faculty_id:
                # Store research profiles
                if "research_profiles" not in fac:
                    fac["research_profiles"] = {}
                
                if data.get("vidwan"):
                    fac["research_profiles"]["vidwan"] = data["vidwan"]
                if data.get("google_scholar"):
                    fac["research_profiles"]["google_scholar"] = data["google_scholar"]
                if data.get("orcid"):
                    fac["research_profiles"]["orcid"] = data["orcid"]
                if data.get("research_id"):
                    fac["research_profiles"]["research_id"] = data["research_id"]
                
                save_data(FACULTY_STORE, faculty_list)
                return jsonify({
                    "message": "Research profiles updated",
                    "research_profiles": fac["research_profiles"]
                }), 200

        return jsonify({"error": "Faculty not found"}), 404

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ======================================================
# ENTERPRISE FACULTY SELF API (REQUIRED CONTRACT)
# ======================================================
@faculty_bp.route("/me", methods=["GET"])
@faculty_self_required
def get_me():
    faculty_id = session.get("faculty_id")
    rows = _load_rows()
    fac = next((f for f in rows if f.get("faculty_id") == faculty_id), None)
    if not fac:
        return jsonify({"error": "Faculty not found"}), 404
    return jsonify(_sanitize_faculty_response(fac))


@faculty_bp.route("/me", methods=["PUT"])
@faculty_self_required
def update_me():
    faculty_id = session.get("faculty_id")
    data = request.json or {}
    rows = _load_rows()
    fac = next((f for f in rows if f.get("faculty_id") == faculty_id), None)
    if not fac:
        return jsonify({"error": "Faculty not found"}), 404

    # faculty editable fields only (admin-controlled fields like designation/role are blocked)
    if "phone" in data:
        fac["phone"] = str(data.get("phone") or "").strip()
        fac["phone_number"] = fac["phone"]
    if "email" in data:
        fac["email"] = str(data.get("email") or "").strip()
        fac["official_email"] = fac["email"]
    if "official_email" in data:
        fac["official_email"] = str(data.get("official_email") or "").strip()
    if "phone_number" in data:
        fac["phone_number"] = str(data.get("phone_number") or "").strip()

    _save_rows(rows)
    log_event("faculty", session.get("username"), "update_own_profile", "faculty", faculty_id, {"fields": list(data.keys())})
    push_notification("admin", "*", "Faculty Profile Updated", f"{fac.get('name')} updated profile.")
    return jsonify({"message": "Profile updated", "faculty": _sanitize_faculty_response(fac)})


@faculty_bp.route("/upload-photo", methods=["POST"])
@faculty_self_required
def upload_photo():
    faculty_id = session.get("faculty_id")
    file = request.files.get("photo")
    if not file or not file.filename:
        return jsonify({"error": "Photo file is required"}), 400
    if not allowed_file(file.filename):
        return jsonify({"error": "Only image files are allowed"}), 400

    rows = _load_rows()
    fac = next((f for f in rows if f.get("faculty_id") == faculty_id), None)
    if not fac:
        return jsonify({"error": "Faculty not found"}), 404

    os.makedirs(FACULTY_PHOTO_UPLOAD_DIR, exist_ok=True)
    ext = secure_filename(file.filename).rsplit(".", 1)[1].lower()
    unique_name = f"{faculty_id}__photo__{uuid.uuid4().hex[:10]}.{ext}"
    abs_path = os.path.join(FACULTY_PHOTO_UPLOAD_DIR, unique_name)
    file.save(abs_path)

    old = fac.get("photo") or ""
    rel_path = f"/static/uploads/faculty/{unique_name}"
    fac["photo"] = rel_path
    if old and old != rel_path:
        _delete_faculty_photo_if_local(old)
    _save_rows(rows)
    log_event("faculty", session.get("username"), "upload_photo", "faculty", faculty_id)
    push_notification("admin", "*", "Faculty Photo Uploaded", f"{fac.get('name')} uploaded/updated profile photo.")
    return jsonify({"message": "Photo uploaded successfully", "photo": rel_path})


@faculty_bp.route("/remove-photo", methods=["DELETE"])
@faculty_self_required
def remove_photo():
    faculty_id = session.get("faculty_id")
    rows = _load_rows()
    fac = next((f for f in rows if f.get("faculty_id") == faculty_id), None)
    if not fac:
        return jsonify({"error": "Faculty not found"}), 404

    old = fac.get("photo") or ""
    if old:
        _delete_faculty_photo_if_local(old)
    fac["photo"] = ""
    _save_rows(rows)
    log_event("faculty", session.get("username"), "remove_photo", "faculty", faculty_id)
    push_notification("admin", "*", "Faculty Photo Removed", f"{fac.get('name')} removed profile photo.")
    return jsonify({"message": "Photo removed", "photo": ""})


@faculty_bp.route("/publications", methods=["POST"])
@faculty_self_required
def add_my_publication_text():
    faculty_id = session.get("faculty_id")
    data = request.form if request.form else (request.get_json(silent=True) or {})
    publication_text = str(data.get("publication", "")).strip()
    if not publication_text:
        return jsonify({"error": "Publication text is required"}), 400

    rows = _load_rows()
    fac = next((f for f in rows if f.get("faculty_id") == faculty_id), None)
    if not fac:
        return jsonify({"error": "Faculty not found"}), 404

    publications = fac.get("publications")
    if not isinstance(publications, list):
        publications = []
    publications.append(publication_text)
    fac["publications"] = publications
    _save_rows(rows)
    log_event("faculty", session.get("username"), "add_publication", "faculty", faculty_id)
    push_notification("admin", "*", "Faculty Publication Added", f"{fac.get('name')} added a publication.")
    return jsonify({"message": "Publication added", "publications": publications})


@faculty_bp.route("/upload-personal-doc", methods=["POST"])
@faculty_self_required
def upload_personal_doc():
    faculty_id = session.get("faculty_id")
    file = request.files.get("file")
    doc_type = str(request.form.get("doc_type", "")).strip()
    if not file or not file.filename:
        return jsonify({"error": "File is required"}), 400
    if doc_type not in ALLOWED_PERSONAL_DOC_TYPES:
        return jsonify({"error": "Invalid personal doc type"}), 400

    rows = _load_rows()
    fac = next((f for f in rows if f.get("faculty_id") == faculty_id), None)
    if not fac:
        return jsonify({"error": "Faculty not found"}), 404

    rel_path = save_file(file, "personal", faculty_id, tag=doc_type)
    docs = fac.setdefault("personal_documents", {})
    if doc_type == "others":
        docs.setdefault("others", []).append(rel_path)
    else:
        old = docs.get(doc_type)
        if old:
            delete_file(old)
        docs[doc_type] = rel_path

    _save_rows(rows)
    log_event("faculty", session.get("username"), "upload_personal_doc", "faculty", faculty_id, {"doc_type": doc_type})
    push_notification("admin", "*", "Personal Document Uploaded", f"{fac.get('name')} uploaded {doc_type}.")
    return jsonify({"message": "Uploaded", "personal_documents": docs})


@faculty_bp.route("/upload-qualification-doc", methods=["POST"])
@faculty_self_required
def upload_qualification_doc():
    faculty_id = session.get("faculty_id")
    file = request.files.get("file")
    doc_type = str(request.form.get("doc_type", "")).strip()
    if not file or not file.filename:
        return jsonify({"error": "File is required"}), 400
    if doc_type not in ALLOWED_QUAL_DOC_TYPES:
        return jsonify({"error": "Invalid qualification doc type"}), 400

    rows = _load_rows()
    fac = next((f for f in rows if f.get("faculty_id") == faculty_id), None)
    if not fac:
        return jsonify({"error": "Faculty not found"}), 404

    rel_path = save_file(file, "qualifications", faculty_id, tag=doc_type)
    docs = fac.setdefault("qualification_documents", {})
    if doc_type == "others":
        docs.setdefault("others", []).append(rel_path)
    else:
        old = docs.get(doc_type)
        if old:
            delete_file(old)
        docs[doc_type] = rel_path

    _save_rows(rows)
    log_event("faculty", session.get("username"), "upload_qualification_doc", "faculty", faculty_id, {"doc_type": doc_type})
    push_notification("admin", "*", "Qualification Document Uploaded", f"{fac.get('name')} uploaded {doc_type}.")
    return jsonify({"message": "Uploaded", "qualification_documents": docs})


@faculty_bp.route("/delete-doc", methods=["DELETE"])
@faculty_self_required
def delete_doc():
    faculty_id = session.get("faculty_id")
    data = request.get_json(silent=True) or {}
    category = str(data.get("category", "")).strip().lower()
    doc_type = str(data.get("doc_type", "")).strip()
    target_path = str(data.get("path", "")).strip()

    if category not in ("personal", "qualification"):
        return jsonify({"error": "Invalid category"}), 400

    rows = _load_rows()
    fac = next((f for f in rows if f.get("faculty_id") == faculty_id), None)
    if not fac:
        return jsonify({"error": "Faculty not found"}), 404

    if category == "personal":
        allowed = ALLOWED_PERSONAL_DOC_TYPES
        docs = fac.setdefault("personal_documents", {})
    else:
        allowed = ALLOWED_QUAL_DOC_TYPES
        docs = fac.setdefault("qualification_documents", {})

    if doc_type not in allowed:
        return jsonify({"error": "Invalid doc type"}), 400

    if doc_type == "others":
        items = docs.setdefault("others", [])
        if not target_path or target_path not in items:
            return jsonify({"error": "Document not found"}), 404
        delete_file(target_path)
        items.remove(target_path)
    else:
        old = docs.get(doc_type)
        if not old:
            return jsonify({"error": "Document not found"}), 404
        delete_file(old)
        docs[doc_type] = ""

    _save_rows(rows)
    action = "delete_personal_doc" if category == "personal" else "delete_qualification_doc"
    log_event("faculty", session.get("username"), action, "faculty", faculty_id, {"doc_type": doc_type})
    push_notification("admin", "*", "Faculty Document Deleted", f"{fac.get('name')} deleted {doc_type} ({category}).")
    return jsonify({
        "message": "Document deleted",
        "personal_documents": fac.get("personal_documents", {}),
        "qualification_documents": fac.get("qualification_documents", {}),
    })


@faculty_bp.route("/notifications", methods=["GET"])
@faculty_self_required
def my_notifications():
    unread_only = request.args.get("unread") == "1"
    limit = request.args.get("limit", 50, type=int)
    notes = list_notifications("faculty", session.get("username"), unread_only=unread_only, limit=limit)
    return jsonify({"notifications": notes})


@faculty_bp.route("/notifications/<notification_id>/read", methods=["PUT"])
@faculty_self_required
def mark_my_notification_read(notification_id):
    ok = mark_as_read("faculty", session.get("username"), notification_id)
    if not ok:
        return jsonify({"error": "Notification not found"}), 404
    return jsonify({"message": "Notification marked as read"})


@faculty_bp.route("/change-password", methods=["PUT"])
@faculty_self_required
def change_password():
    faculty_id = session.get("faculty_id")
    data = request.json or {}
    old_password = data.get("old_password")
    new_password = data.get("new_password")

    if not old_password or not new_password:
        return jsonify({"error": "old_password and new_password are required"}), 400
    valid_pwd, pwd_msg = validate_password_strength(new_password)
    if not valid_pwd:
        return jsonify({"error": pwd_msg}), 400

    rows = _load_rows()
    fac = next((f for f in rows if f.get("faculty_id") == faculty_id), None)
    if not fac:
        return jsonify({"error": "Faculty not found"}), 404

    stored_password = fac.get("password", "")
    if is_password_hash(stored_password):
        valid = check_password(old_password, stored_password)
    else:
        valid = stored_password == old_password
    if not valid:
        return jsonify({"error": "Current password is incorrect"}), 400

    fac["password"] = hash_password(new_password)
    _save_rows(rows)
    log_event("faculty", session.get("username"), "change_password", "faculty", faculty_id)
    push_notification("admin", "*", "Faculty Password Changed", f"{fac.get('name')} changed password.")
    return jsonify({"message": "Password updated successfully"})


@faculty_bp.route("/me/upload-cert", methods=["POST"])
@faculty_self_required
def upload_my_cert():
    faculty_id = session.get("faculty_id")
    return _upload_cert_common(faculty_id, force_unverified=True)


@faculty_bp.route("/upload-cert/<faculty_id>", methods=["POST"])
@faculty_self_required
def upload_cert_for_id(faculty_id):
    if faculty_id != session.get("faculty_id"):
        return jsonify({"error": "Forbidden"}), 403
    return _upload_cert_common(faculty_id, force_unverified=True)


def _upload_cert_common(faculty_id, force_unverified=True):
    if "file" not in request.files:
        return jsonify({"error": "No file part"}), 400

    title = (request.form.get("title") or "").strip()
    issuer = (request.form.get("issuer") or "").strip()
    year = (request.form.get("year") or "").strip()
    file = request.files["file"]

    if not all([title, issuer, year, file]):
        return jsonify({"error": "title, issuer, year and file are required"}), 400

    rows = _load_rows()
    fac = next((f for f in rows if f.get("faculty_id") == faculty_id), None)
    if not fac:
        return jsonify({"error": "Faculty not found"}), 404

    rel_path = save_file(file, "rd", faculty_id, tag=f"cert_{title}")
    cert = {
        "cert_id": "cert-" + uuid.uuid4().hex,
        "title": title,
        "issuer": issuer,
        "year": year,
        "file": rel_path,
        "verified": False if force_unverified else bool(request.form.get("verified")),
    }
    fac.setdefault("certifications", []).append(cert)
    _save_rows(rows)
    log_event("faculty", session.get("username"), "upload_certification", "faculty", faculty_id, {"cert_id": cert.get("cert_id")})
    push_notification("admin", "*", "Certification Uploaded", f"{fac.get('name')} uploaded certification '{title}'.")
    push_notification("faculty", fac.get("username"), "Certification Submitted", f"Certification '{title}' submitted for review.")
    return jsonify({"message": "Certification uploaded", "certification": cert}), 201


@faculty_bp.route("/<faculty_id>/certifications", methods=["GET"])
def get_certifications(faculty_id):
    role = session.get("role")
    session_faculty_id = session.get("faculty_id")

    if role not in ("admin", "faculty"):
        return jsonify({"error": "Unauthorized"}), 401
    if role == "faculty" and faculty_id != session_faculty_id:
        return jsonify({"error": "Forbidden"}), 403

    rows = _load_rows()
    fac = next((f for f in rows if f.get("faculty_id") == faculty_id), None)
    if not fac:
        return jsonify({"error": "Faculty not found"}), 404

    return jsonify({"certifications": fac.get("certifications", [])})
