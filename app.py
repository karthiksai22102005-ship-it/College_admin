from flask import Flask, render_template, session, redirect, url_for, request, jsonify, send_from_directory, abort, send_file
from routes.auth_routes import auth_bp
from routes.faculty_routes import faculty_bp
from routes.admin_routes import admin_bp
from routes.personal_routes import personal_bp
from routes.research_routes import research_bp
from routes.erp_routes import erp_bp
from utils.data_store import load_data, save_data, load_faculty_data
from utils.security import hash_password, check_password, is_password_hash
from utils.audit_service import log_event
from utils.notification_service import push_notification, list_notifications, mark_as_read
from utils.file_handler import save_file, delete_file
from utils.password_policy import validate_password_strength
from utils.storage_backend import read_upload_rel_path, using_s3
from datetime import timedelta
from werkzeug.utils import secure_filename
from datetime import datetime
from io import BytesIO
import mimetypes
import uuid
import os
from config import Config


# ======================================================
# APP INIT
# ======================================================
app = Flask(__name__, template_folder="templates", static_folder="static")
app.config.from_object(Config)

# 🔐 SECURITY
app.secret_key = app.config["SECRET_KEY"]

# ======================================================
# SESSION CONFIG
# ======================================================
app.config['SESSION_COOKIE_DURATION'] = app.config.get('PERMANENT_SESSION_LIFETIME', timedelta(hours=24))
app.config['PERMANENT_SESSION_LIFETIME'] = app.config.get('PERMANENT_SESSION_LIFETIME', timedelta(hours=24))
app.config['SESSION_COOKIE_SECURE'] = app.config.get('SESSION_COOKIE_SECURE', False)
app.config['SESSION_COOKIE_HTTPONLY'] = app.config.get('SESSION_COOKIE_HTTPONLY', True)
app.config['SESSION_COOKIE_SAMESITE'] = app.config.get('SESSION_COOKIE_SAMESITE', 'Lax')


# ======================================================
# PATHS
# ======================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FACULTY_STORE = os.path.join(BASE_DIR, "data", "faculty.store")
USERS_STORE = os.path.join(BASE_DIR, "data", "users.store")
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
FACULTY_PHOTO_UPLOAD_DIR = os.path.join(BASE_DIR, "static", "uploads", "faculty")
ALLOWED_FACULTY_PHOTO_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}
ALLOWED_PERSONAL_DOC_TYPES = {"aadhaar", "pan", "bank_passbook", "service_register", "joining_letter", "others"}
ALLOWED_QUAL_DOC_TYPES = {"ssc_memo", "inter_memo", "btech_memo", "mtech_memo", "phd_memo", "others"}


# ======================================================
# REGISTER BLUEPRINTS (ORDER MATTERS)
# ======================================================
app.register_blueprint(auth_bp, url_prefix="/auth") #login blueprint added
app.register_blueprint(faculty_bp, url_prefix="/faculty")
app.register_blueprint(admin_bp, url_prefix="/admin")
app.register_blueprint(personal_bp, url_prefix="/api/personal")
app.register_blueprint(research_bp, url_prefix="/api/research")
app.register_blueprint(erp_bp, url_prefix="/api/erp")


# ======================================================
# PAGE ROUTES
# ======================================================
@app.route("/")
def home():
    return render_template("login.html")


@app.route("/login")
def login_page():
    return render_template("login.html")


@app.route("/dashboard")
def dashboard_page():
    if "role" not in session:
        return redirect(url_for("login_page", next=request.url))
    if session.get("role") != "admin":
        return redirect(url_for("faculty_dashboard_page"))
    return render_template("admin_dashboard.html")


@app.route("/admin-dashboard")
def admin_dashboard_page():
    if "role" not in session:
        return redirect(url_for("login_page", next=request.url))
    if session.get("role") != "admin":
        return redirect(url_for("faculty_dashboard_page"))
    return render_template("admin_dashboard.html")


@app.route("/faculty-dashboard")
def faculty_dashboard_page():
    if "role" not in session:
        return redirect(url_for("login_page", next=request.url))
    is_admin_impersonation = session.get("role") == "admin" and bool(session.get("impersonate_faculty_id"))
    if session.get("role") != "faculty" and not is_admin_impersonation:
        return redirect(url_for("admin_dashboard_page"))

    faculty = None
    if is_admin_impersonation:
        target_id = session.get("impersonate_faculty_id")
        rows = load_faculty_data(FACULTY_STORE)
        faculty = next((r for r in rows if r.get("faculty_id") == target_id), None)
    else:
        faculty = _get_current_faculty_by_session_username()

    if not faculty:
        if is_admin_impersonation:
            session.pop("impersonate_faculty_id", None)
            return redirect(url_for("admin_dashboard_page"))
        session.clear()
        return redirect(url_for("login_page"))

    faculty["last_login"] = datetime.utcnow().isoformat()
    if not is_admin_impersonation:
        rows = load_faculty_data(FACULTY_STORE)
        for i, row in enumerate(rows):
            if str(row.get("username", "")).strip().lower() == str(session.get("username", "")).strip().lower():
                rows[i] = faculty
                break
        save_data(FACULTY_STORE, rows)

    return render_template("faculty_dashboard.html", faculty=faculty, impersonated_by_admin=is_admin_impersonation)


def _allowed_photo_file(filename):
    if "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in ALLOWED_FACULTY_PHOTO_EXTENSIONS


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


def _get_current_faculty_by_session_username():
    username = (session.get("username") or "").strip()
    if not username:
        return None

    rows = load_faculty_data(FACULTY_STORE)
    for row in rows:
        if str(row.get("username", "")).strip().lower() == username.lower():
            row.setdefault("photo", "")
            row.setdefault("publications", [])
            workload = row.get("workload") if isinstance(row.get("workload"), dict) else {}
            row["workload"] = {
                "subjects": list(workload.get("subjects") or []),
                "hours_per_week": workload.get("hours_per_week") or 0,
            }
            row.setdefault("last_login", row.get("last_login"))
            return row
    return None


def _faculty_auth_guard():
    if "role" not in session or session.get("role") != "faculty":
        return jsonify({"status": "error", "message": "Unauthorized"}), 403
    if not session.get("username"):
        return jsonify({"status": "error", "message": "Invalid session"}), 401
    return None


def _current_faculty_for_dashboard():
    """
    Resolve active faculty record for dashboard APIs.
    Supports normal faculty sessions and admin impersonation mode.
    """
    role = session.get("role")
    if role == "faculty":
        return _get_current_faculty_by_session_username()

    if role == "admin" and session.get("impersonate_faculty_id"):
        target_id = session.get("impersonate_faculty_id")
        rows = load_faculty_data(FACULTY_STORE)
        return next((r for r in rows if r.get("faculty_id") == target_id), None)

    return None


@app.route("/faculty-me", methods=["GET"])
def faculty_me():
    faculty = _current_faculty_for_dashboard()
    if not faculty:
        return jsonify({"status": "error", "message": "Unauthorized"}), 401

    payload = dict(faculty)
    payload.pop("password", None)
    payload.pop("password_hash", None)
    return jsonify(payload)


@app.route("/update-faculty-profile", methods=["POST"])
def update_faculty_profile():
    denied = _faculty_auth_guard()
    if denied:
        return denied

    faculty = _get_current_faculty_by_session_username()
    if not faculty:
        return jsonify({"status": "error", "message": "Faculty not found"}), 404

    data = request.form if request.form else (request.get_json(silent=True) or {})
    faculty["email"] = str(data.get("email", faculty.get("email", ""))).strip()
    faculty["phone"] = str(data.get("phone", faculty.get("phone", ""))).strip()
    faculty["designation"] = str(data.get("designation", faculty.get("designation", ""))).strip()

    rows = load_faculty_data(FACULTY_STORE)
    username = str(session.get("username", "")).strip().lower()
    for i, row in enumerate(rows):
        if str(row.get("username", "")).strip().lower() == username:
            rows[i] = faculty
            break
    save_data(FACULTY_STORE, rows)
    log_event("faculty", session.get("username"), "update_own_profile", "faculty", faculty.get("faculty_id"), {"fields": ["email", "phone", "designation"]})
    push_notification("admin", "*", "Faculty Profile Updated", f"{faculty.get('name')} updated profile details.")

    return jsonify({
        "status": "success",
        "message": "Profile updated",
        "faculty": {
            "name": faculty.get("name", ""),
            "username": faculty.get("username", ""),
            "department": faculty.get("department", ""),
            "designation": faculty.get("designation", ""),
            "email": faculty.get("email", ""),
            "phone": faculty.get("phone", ""),
        }
    })


@app.route("/faculty-change-password", methods=["POST"])
def faculty_change_password():
    denied = _faculty_auth_guard()
    if denied:
        return denied

    faculty = _get_current_faculty_by_session_username()
    if not faculty:
        return jsonify({"status": "error", "message": "Faculty not found"}), 404

    data = request.form if request.form else (request.get_json(silent=True) or {})
    current_password = str(data.get("current_password", "")).strip()
    new_password = str(data.get("new_password", "")).strip()

    if not current_password or not new_password:
        return jsonify({"status": "error", "message": "Current and new password are required"}), 400
    ok, reason = validate_password_strength(new_password)
    if not ok:
        return jsonify({"status": "error", "message": reason}), 400

    stored_password = faculty.get("password", "")
    if is_password_hash(stored_password):
        valid_current = check_password(current_password, stored_password)
    else:
        valid_current = stored_password == current_password
    if not valid_current:
        return jsonify({"status": "error", "message": "Current password is incorrect"}), 400

    faculty["password"] = hash_password(new_password)

    rows = load_faculty_data(FACULTY_STORE)
    username = str(session.get("username", "")).strip().lower()
    for i, row in enumerate(rows):
        if str(row.get("username", "")).strip().lower() == username:
            rows[i] = faculty
            break
    save_data(FACULTY_STORE, rows)
    log_event("faculty", session.get("username"), "change_password", "faculty", faculty.get("faculty_id"))
    push_notification("admin", "*", "Faculty Password Changed", f"{faculty.get('name')} changed password.")

    return jsonify({"status": "success", "message": "Password updated successfully"})


@app.route("/faculty-upload-photo", methods=["POST"])
def faculty_upload_photo():
    denied = _faculty_auth_guard()
    if denied:
        return denied

    faculty = _get_current_faculty_by_session_username()
    if not faculty:
        return jsonify({"status": "error", "message": "Faculty not found"}), 404

    file = request.files.get("photo")
    if not file or not file.filename:
        return jsonify({"status": "error", "message": "Photo file is required"}), 400

    if not _allowed_photo_file(file.filename):
        return jsonify({"status": "error", "message": "Only image files are allowed"}), 400

    os.makedirs(FACULTY_PHOTO_UPLOAD_DIR, exist_ok=True)
    original_name = secure_filename(file.filename)
    ext = original_name.rsplit(".", 1)[1].lower()
    unique_name = f"{faculty.get('faculty_id', 'FAC')}__photo__{uuid.uuid4().hex[:10]}.{ext}"
    save_path = os.path.join(FACULTY_PHOTO_UPLOAD_DIR, unique_name)
    file.save(save_path)

    old_photo = faculty.get("photo", "")
    faculty["photo"] = f"/static/uploads/faculty/{unique_name}"

    rows = load_faculty_data(FACULTY_STORE)
    username = str(session.get("username", "")).strip().lower()
    for i, row in enumerate(rows):
        if str(row.get("username", "")).strip().lower() == username:
            rows[i] = faculty
            break
    save_data(FACULTY_STORE, rows)
    _delete_faculty_photo_if_local(old_photo)
    log_event("faculty", session.get("username"), "upload_photo", "faculty", faculty.get("faculty_id"))
    push_notification("admin", "*", "Faculty Photo Uploaded", f"{faculty.get('name')} uploaded/updated profile photo.")

    return jsonify({
        "status": "success",
        "message": "Photo uploaded successfully",
        "photo": faculty["photo"]
    })


@app.route("/faculty-remove-photo", methods=["DELETE"])
def faculty_remove_photo():
    denied = _faculty_auth_guard()
    if denied:
        return denied

    faculty = _get_current_faculty_by_session_username()
    if not faculty:
        return jsonify({"status": "error", "message": "Faculty not found"}), 404

    old_photo = faculty.get("photo", "")
    faculty["photo"] = ""

    rows = load_faculty_data(FACULTY_STORE)
    username = str(session.get("username", "")).strip().lower()
    for i, row in enumerate(rows):
        if str(row.get("username", "")).strip().lower() == username:
            rows[i] = faculty
            break
    save_data(FACULTY_STORE, rows)
    _delete_faculty_photo_if_local(old_photo)
    log_event("faculty", session.get("username"), "remove_photo", "faculty", faculty.get("faculty_id"))
    push_notification("admin", "*", "Faculty Photo Removed", f"{faculty.get('name')} removed profile photo.")

    return jsonify({"status": "success", "message": "Photo removed", "photo": ""})


@app.route("/faculty-publications", methods=["POST"])
def faculty_publications():
    denied = _faculty_auth_guard()
    if denied:
        return denied

    faculty = _get_current_faculty_by_session_username()
    if not faculty:
        return jsonify({"status": "error", "message": "Faculty not found"}), 404

    data = request.form if request.form else (request.get_json(silent=True) or {})
    publication_text = str(data.get("publication", "")).strip()
    if not publication_text:
        return jsonify({"status": "error", "message": "Publication text is required"}), 400

    publications = faculty.get("publications")
    if not isinstance(publications, list):
        publications = []
    publications.append(publication_text)
    faculty["publications"] = publications

    rows = load_faculty_data(FACULTY_STORE)
    username = str(session.get("username", "")).strip().lower()
    for i, row in enumerate(rows):
        if str(row.get("username", "")).strip().lower() == username:
            rows[i] = faculty
            break
    save_data(FACULTY_STORE, rows)
    log_event("faculty", session.get("username"), "add_publication", "faculty", faculty.get("faculty_id"))
    push_notification("admin", "*", "Faculty Publication Added", f"{faculty.get('name')} added a publication.")

    return jsonify({
        "status": "success",
        "message": "Publication added",
        "publications": faculty["publications"]
    })


@app.route("/faculty-upload-personal-doc", methods=["POST"])
def faculty_upload_personal_doc():
    denied = _faculty_auth_guard()
    if denied:
        return denied

    faculty = _get_current_faculty_by_session_username()
    if not faculty:
        return jsonify({"status": "error", "message": "Faculty not found"}), 404

    file = request.files.get("file")
    doc_type = str(request.form.get("doc_type", "")).strip()
    if not file or not file.filename:
        return jsonify({"status": "error", "message": "File is required"}), 400
    if doc_type not in ALLOWED_PERSONAL_DOC_TYPES:
        return jsonify({"status": "error", "message": "Invalid personal doc type"}), 400

    try:
        rel_path = save_file(file, "personal", faculty.get("faculty_id"), tag=doc_type)
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 400

    docs = faculty.setdefault("personal_documents", {})
    if doc_type == "others":
        docs.setdefault("others", []).append(rel_path)
    else:
        old = docs.get(doc_type)
        if old:
            delete_file(old)
        docs[doc_type] = rel_path

    rows = load_faculty_data(FACULTY_STORE)
    username = str(session.get("username", "")).strip().lower()
    for i, row in enumerate(rows):
        if str(row.get("username", "")).strip().lower() == username:
            rows[i] = faculty
            break
    save_data(FACULTY_STORE, rows)
    log_event("faculty", session.get("username"), "upload_personal_doc", "faculty", faculty.get("faculty_id"), {"doc_type": doc_type})
    push_notification("admin", "*", "Personal Document Uploaded", f"{faculty.get('name')} uploaded {doc_type}.")
    return jsonify({"status": "success", "message": "Uploaded", "personal_documents": docs})


@app.route("/faculty-upload-qualification-doc", methods=["POST"])
def faculty_upload_qualification_doc():
    denied = _faculty_auth_guard()
    if denied:
        return denied

    faculty = _get_current_faculty_by_session_username()
    if not faculty:
        return jsonify({"status": "error", "message": "Faculty not found"}), 404

    file = request.files.get("file")
    doc_type = str(request.form.get("doc_type", "")).strip()
    if not file or not file.filename:
        return jsonify({"status": "error", "message": "File is required"}), 400
    if doc_type not in ALLOWED_QUAL_DOC_TYPES:
        return jsonify({"status": "error", "message": "Invalid qualification doc type"}), 400

    try:
        rel_path = save_file(file, "qualifications", faculty.get("faculty_id"), tag=doc_type)
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 400

    docs = faculty.setdefault("qualification_documents", {})
    if doc_type == "others":
        docs.setdefault("others", []).append(rel_path)
    else:
        old = docs.get(doc_type)
        if old:
            delete_file(old)
        docs[doc_type] = rel_path

    rows = load_faculty_data(FACULTY_STORE)
    username = str(session.get("username", "")).strip().lower()
    for i, row in enumerate(rows):
        if str(row.get("username", "")).strip().lower() == username:
            rows[i] = faculty
            break
    save_data(FACULTY_STORE, rows)
    log_event("faculty", session.get("username"), "upload_qualification_doc", "faculty", faculty.get("faculty_id"), {"doc_type": doc_type})
    push_notification("admin", "*", "Qualification Document Uploaded", f"{faculty.get('name')} uploaded {doc_type}.")
    return jsonify({"status": "success", "message": "Uploaded", "qualification_documents": docs})


@app.route("/faculty-delete-doc", methods=["DELETE"])
def faculty_delete_doc():
    denied = _faculty_auth_guard()
    if denied:
        return denied

    faculty = _get_current_faculty_by_session_username()
    if not faculty:
        return jsonify({"status": "error", "message": "Faculty not found"}), 404

    data = request.get_json(silent=True) or {}
    category = str(data.get("category", "")).strip().lower()
    doc_type = str(data.get("doc_type", "")).strip()
    target_path = str(data.get("path", "")).strip()

    if category not in ("personal", "qualification"):
        return jsonify({"status": "error", "message": "Invalid category"}), 400

    if category == "personal":
        allowed = ALLOWED_PERSONAL_DOC_TYPES
        docs = faculty.setdefault("personal_documents", {})
    else:
        allowed = ALLOWED_QUAL_DOC_TYPES
        docs = faculty.setdefault("qualification_documents", {})

    if doc_type not in allowed:
        return jsonify({"status": "error", "message": "Invalid doc type"}), 400

    if doc_type == "others":
        items = docs.setdefault("others", [])
        if not target_path or target_path not in items:
            return jsonify({"status": "error", "message": "Document not found"}), 404
        delete_file(target_path)
        items.remove(target_path)
    else:
        old = docs.get(doc_type)
        if not old:
            return jsonify({"status": "error", "message": "Document not found"}), 404
        delete_file(old)
        docs[doc_type] = ""

    rows = load_faculty_data(FACULTY_STORE)
    username = str(session.get("username", "")).strip().lower()
    for i, row in enumerate(rows):
        if str(row.get("username", "")).strip().lower() == username:
            rows[i] = faculty
            break
    save_data(FACULTY_STORE, rows)

    action = "delete_personal_doc" if category == "personal" else "delete_qualification_doc"
    log_event("faculty", session.get("username"), action, "faculty", faculty.get("faculty_id"), {"doc_type": doc_type})
    push_notification("admin", "*", "Faculty Document Deleted", f"{faculty.get('name')} deleted {doc_type} ({category}).")
    return jsonify({
        "status": "success",
        "message": "Document deleted",
        "personal_documents": faculty.get("personal_documents", {}),
        "qualification_documents": faculty.get("qualification_documents", {}),
    })


@app.route("/faculty-notifications", methods=["GET"])
def faculty_notifications():
    denied = _faculty_auth_guard()
    if denied:
        return denied
    unread_only = request.args.get("unread") == "1"
    limit = request.args.get("limit", 50, type=int)
    notes = list_notifications("faculty", session.get("username"), unread_only=unread_only, limit=limit)
    return jsonify({"status": "success", "notifications": notes})


@app.route("/faculty-notifications/<notification_id>/read", methods=["PUT"])
def faculty_mark_notification_read(notification_id):
    denied = _faculty_auth_guard()
    if denied:
        return denied
    ok = mark_as_read("faculty", session.get("username"), notification_id)
    if not ok:
        return jsonify({"status": "error", "message": "Notification not found"}), 404
    return jsonify({"status": "success", "message": "Notification marked as read"})


# ======================================================
# SECURE FILE SERVING
# ======================================================
@app.route('/uploads/<path:filename>')
def secure_serve_file(filename):
    # 1. Check if user is logged in
    if 'role' not in session:
        return abort(401) # Unauthorized

    user_role = session['role']
    user_id = session.get('user') # This is faculty_id for faculty members

    normalized_name = str(filename).replace("\\", "/").lstrip("/")
    rel_key = f"uploads/{normalized_name}"
    guessed_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"

    # 2. Admins can access any file
    if user_role == 'admin':
        if using_s3():
            data = read_upload_rel_path(f"/{rel_key}")
            if data is None:
                return abort(404)
            return send_file(BytesIO(data), mimetype=guessed_type, as_attachment=True, download_name=os.path.basename(filename))
        return send_from_directory(UPLOAD_DIR, filename, as_attachment=True)

    # 3. Faculty can only access their own files
    if user_role == 'faculty':
        # The filename is expected to be like 'FAC1001__aadhaar__17098822.pdf'
        # We check if the user's ID is at the start of the filename.
        if user_id and os.path.basename(filename).startswith(user_id):
            if using_s3():
                data = read_upload_rel_path(f"/{rel_key}")
                if data is None:
                    return abort(404)
                return send_file(BytesIO(data), mimetype=guessed_type, as_attachment=True, download_name=os.path.basename(filename))
            return send_from_directory(UPLOAD_DIR, filename, as_attachment=True)
        else:
            # Log this attempt for security auditing
            app.logger.warning(f"SECURITY: Faculty '{user_id}' attempted to access forbidden file '{filename}'")
            return abort(403) # Forbidden

    # 4. Deny all other roles
    return abort(403)


@app.route('/uploads/docs/<path:filename>')
def secure_docs_download(filename):
    if 'role' not in session:
        return abort(401)

    docs_dir = os.path.join(UPLOAD_DIR, "docs")
    requested_path = os.path.normpath(filename).replace("\\", "/").lstrip("/")
    abs_path = os.path.abspath(os.path.join(docs_dir, requested_path))
    if not abs_path.startswith(os.path.abspath(docs_dir)):
        return abort(403)
    safe_name = os.path.basename(requested_path)
    subdir = os.path.dirname(requested_path)
    send_dir = os.path.join(docs_dir, subdir) if subdir else docs_dir

    guessed_type = mimetypes.guess_type(safe_name)[0] or "application/octet-stream"
    rel_key = "/uploads/docs/" + requested_path.replace("\\", "/")

    if session.get("role") == "admin":
        if using_s3():
            data = read_upload_rel_path(rel_key)
            if data is None:
                return abort(404)
            return send_file(BytesIO(data), mimetype=guessed_type, as_attachment=True, download_name=safe_name)
        return send_from_directory(send_dir, safe_name, as_attachment=True)

    if session.get("role") == "faculty":
        faculty_id = session.get("faculty_id")
        if faculty_id and safe_name.startswith(faculty_id):
            if using_s3():
                data = read_upload_rel_path(rel_key)
                if data is None:
                    return abort(404)
                return send_file(BytesIO(data), mimetype=guessed_type, as_attachment=True, download_name=safe_name)
            return send_from_directory(send_dir, safe_name, as_attachment=True)
        return abort(403)

    return abort(403)


# ======================================================
# FORGOT PASSWORD
# ======================================================
@app.route("/auth/forgot-password", methods=["POST"])
def forgot_password():
    data = request.get_json(silent=True) or {}
    username = str(data.get("username") or "").strip()
    role = str(data.get("role") or "").strip().lower()
    dob = str(data.get("dob") or "").strip()
    new_password = str(data.get("new_password") or "").strip()

    if not username or not new_password:
        return jsonify({"error": "username and new_password are required"}), 400

    ok, reason = validate_password_strength(new_password)
    if not ok:
        return jsonify({"error": reason}), 400

    def _norm_date(value):
        txt = str(value or "").strip()
        if not txt:
            return ""
        for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d", "%m-%d-%Y", "%m/%d/%Y"):
            try:
                return datetime.strptime(txt, fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue
        return txt.replace("/", "-")

    if role != "admin":
        if not dob:
            return jsonify({"error": "dob is required for faculty password reset"}), 400

        faculty_list = load_data(FACULTY_STORE)
        if isinstance(faculty_list, list):
            requested_dob = _norm_date(dob)
            for fac in faculty_list:
                fac_username = str(fac.get("username") or "").strip().lower()
                fac_id = str(fac.get("faculty_id") or "").strip().lower()
                if username.lower() not in (fac_username, fac_id):
                    continue

                stored_dob = _norm_date(fac.get("dob") or fac.get("date_of_birth"))
                if not stored_dob or stored_dob != requested_dob:
                    return jsonify({"error": "DOB verification failed"}), 403

                fac["password"] = hash_password(new_password)
                save_data(FACULTY_STORE, faculty_list)
                log_event("faculty", username, "forgot_password_reset", "faculty", fac.get("faculty_id"))
                push_notification("admin", "*", "Faculty Password Reset", f"{fac.get('name')} reset password through forgot password.")
                return jsonify({"message": "Password updated successfully"})

        if role == "faculty":
            return jsonify({"error": "User not found"}), 404

    users_data = load_data(USERS_STORE)
    if isinstance(users_data, dict) and "users" in users_data:
        for user in users_data.get("users", []):
            if str(user.get("user_id") or "").strip().lower() == username.lower():
                user["password_hash"] = hash_password(new_password)
                save_data(USERS_STORE, users_data)
                log_event("admin", username, "forgot_password_reset", "admin", user.get("user_id"))
                return jsonify({"message": "Password updated successfully"})

    return jsonify({"error": "User not found"}), 404

# ======================================================
# HEALTH CHECK (VERY USEFUL — NEW)
# ======================================================
@app.route("/health")
def health():
    return {"status": "ok"}


def init_upload_dirs_on_startup():
    from utils.file_handler import init_upload_dirs
    init_upload_dirs()


def ensure_faculty_schema_on_startup():
    rows = load_faculty_data(FACULTY_STORE)
    save_data(FACULTY_STORE, rows)


def ensure_users_dataset_on_startup():
    users_data = load_data(USERS_STORE)
    changed = False

    if not isinstance(users_data, dict):
        users_data = {"meta": {"version": 1}, "users": []}
        changed = True

    users_list = users_data.get("users")
    if not isinstance(users_list, list):
        users_data["users"] = []
        users_list = users_data["users"]
        changed = True

    has_admin = any(str(user.get("user_id", "")).strip().upper() == "ADMIN001" for user in users_list if isinstance(user, dict))
    if not has_admin:
        users_list.append({
            "user_id": "ADMIN001",
            "role": "admin",
            "password_hash": hash_password("admin123"),
            "faculty_id": None,
        })
        changed = True

    if changed:
        save_data(USERS_STORE, users_data)


def run_startup_bootstrap():
    """
    Ensure required directories/data schema exist when the app is loaded by WSGI servers
    like gunicorn (Render uses gunicorn, so __main__ block won't run).
    """
    init_upload_dirs_on_startup()
    ensure_users_dataset_on_startup()
    ensure_faculty_schema_on_startup()


# Run bootstrap during module import so deployment startup is consistent on Render.
run_startup_bootstrap()

# ======================================================
# RUN
# ======================================================
if __name__ == "__main__":
    print("Starting College Admin Server...")
    if app.config.get("SECRET_KEY") == "super-secret-key-change-later":
        print("WARNING: Using default SECRET_KEY. Set SECRET_KEY environment variable for security.")
    init_upload_dirs_on_startup()
    ensure_faculty_schema_on_startup()
    debug_mode = str(os.getenv("FLASK_DEBUG", "false")).strip().lower() in {"1", "true", "yes", "on"}
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "5000"))
    app.run(host=host, port=port, debug=debug_mode)


