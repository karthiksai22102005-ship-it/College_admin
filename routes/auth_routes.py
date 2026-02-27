from flask import Blueprint, request, jsonify, session
from utils.data_store import load_data, save_data
from utils.security import check_password, hash_password, is_password_hash
from utils.audit_service import log_event
from utils.rbac import normalize_role_from_designation, default_permissions_json_for_role
import os
import time

auth_bp = Blueprint("auth_bp", __name__)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
USERS_STORE = os.path.join(BASE_DIR, "data", "users.store")
FACULTY_STORE = os.path.join(BASE_DIR, "data", "faculty.store")
FAILED_LOGIN = {}
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_SECONDS = 300


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.json
    username = data.get("username")
    password = data.get("password")
    remote = request.remote_addr or "unknown"
    lock_key = f"{remote}:{username}"
    lock = FAILED_LOGIN.get(lock_key, {"count": 0, "until": 0})
    now = time.time()
    if lock.get("until", 0) > now:
        wait_sec = int(lock["until"] - now)
        return jsonify({"error": f"Too many attempts. Try again in {wait_sec}s"}), 429

    # ===== ADMIN =====
    users_data = load_data(USERS_STORE)
    if isinstance(users_data, dict):
        for user in users_data.get("users", []):
            if user.get("user_id") != username:
                continue
            if bool(user.get("account_locked")):
                return jsonify({"error": "Account is locked. Contact admin."}), 423

            stored_hash = user.get("password_hash") or ""
            stored_legacy = user.get("password") or ""
            valid = False

            if stored_hash:
                if is_password_hash(stored_hash):
                    valid = check_password(password, stored_hash)
                else:
                    # One-time migration for wrongly stored plaintext in password_hash.
                    valid = (password == stored_hash)
                    if valid:
                        user["password_hash"] = hash_password(password)
                        user.pop("password", None)
                        try:
                            save_data(USERS_STORE, users_data)
                        except Exception:
                            pass
            elif stored_legacy:
                if is_password_hash(stored_legacy):
                    valid = check_password(password, stored_legacy)
                    if valid:
                        user["password_hash"] = stored_legacy
                        user.pop("password", None)
                        try:
                            save_data(USERS_STORE, users_data)
                        except Exception:
                            pass
                else:
                    # One-time migration for legacy plaintext admin password.
                    valid = (password == stored_legacy)
                    if valid:
                        user["password_hash"] = hash_password(password)
                        user.pop("password", None)
                        try:
                            save_data(USERS_STORE, users_data)
                        except Exception:
                            pass

            if valid:
                FAILED_LOGIN.pop(lock_key, None)
                session["role"] = "admin"
                session["normalized_role"] = "ADMIN"
                session["user"] = user.get("user_id")
                session["username"] = user.get("user_id")
                session["permissions_json"] = user.get("permissions_json") or ""
                session.permanent = True
                log_event("admin", session.get("username"), "login_success", "session", session.get("username"), {"ip": remote})
                return jsonify({"role": "admin"})

    allow_legacy_admin = str(os.getenv("ALLOW_LEGACY_ADMIN_LOGIN", "false")).strip().lower() == "true"
    if allow_legacy_admin and username == "ADMIN001" and password == "admin123":
        FAILED_LOGIN.pop(lock_key, None)
        session["role"] = "admin"
        session["normalized_role"] = "ADMIN"
        session["user"] = "ADMIN001"
        session["username"] = "ADMIN001"
        session["permissions_json"] = ""
        session.permanent = True
        log_event("admin", session.get("username"), "login_success", "session", session.get("username"), {"ip": remote})
        return jsonify({"role": "admin"})

    # ===== FACULTY =====
    faculty_list = load_data(FACULTY_STORE)

    for fac in faculty_list:
        if fac.get("username") != username:
            continue
        if bool(fac.get("account_locked")):
            return jsonify({"error": "Account is locked. Contact admin."}), 423
        stored_password = fac.get("password") or ""
        valid = False
        if is_password_hash(stored_password):
            valid = check_password(password, stored_password)
        else:
            # One-time legacy plaintext migration.
            valid = stored_password == password
            if valid:
                fac["password"] = hash_password(password)
                try:
                    save_data(FACULTY_STORE, faculty_list)
                except Exception:
                    pass
        if valid:
            FAILED_LOGIN.pop(lock_key, None)
            session["role"] = "faculty"
            normalized_role = str(fac.get("normalized_role") or normalize_role_from_designation(fac.get("designation", ""))).strip().upper()
            session["normalized_role"] = normalized_role
            session["user"] = fac["faculty_id"]
            session["faculty_id"] = fac["faculty_id"]
            session["username"] = fac.get("username")
            session["permissions_json"] = fac.get("permissions_json") or default_permissions_json_for_role(normalized_role)
            session.permanent = True
            log_event("faculty", session.get("username"), "login_success", "session", fac.get("faculty_id"), {"ip": remote})
            return jsonify({"role": "faculty"})

    attempts = FAILED_LOGIN.get(lock_key, {"count": 0, "until": 0})
    attempts["count"] = int(attempts.get("count", 0)) + 1
    if attempts["count"] >= MAX_LOGIN_ATTEMPTS:
        attempts["until"] = now + LOCKOUT_SECONDS
        attempts["count"] = 0
    FAILED_LOGIN[lock_key] = attempts
    log_event("unknown", username, "login_failed", "session", username, {"ip": remote})
    return jsonify({"error": "Invalid credentials"}), 401


@auth_bp.route("/logout", methods=["POST"])
def logout():
    log_event(session.get("role"), session.get("username") or session.get("user"), "logout", "session", session.get("user"))
    session.clear()
    return jsonify({"message": "Logged out successfully"}), 200


@auth_bp.route("/check-session", methods=["GET"])
def check_session():
    if "role" in session:
        return jsonify({
            "authenticated": True,
            "role": session.get("role"),
            "normalized_role": session.get("normalized_role"),
            "user": session.get("user")
        }), 200
    return jsonify({"authenticated": False}), 401
