from flask import session, jsonify
from functools import wraps
from utils.rbac import can_permission


# ======================================================
# LOGIN REQUIRED DECORATOR
# ======================================================
def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user" not in session:
            return jsonify({"error": "Login required"}), 401
        return f(*args, **kwargs)
    return wrapper


# ======================================================
# ROLE REQUIRED DECORATOR
# ======================================================
def role_required(role):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if session.get("role") != role:
                return jsonify({"error": f"{role} only"}), 403
            return f(*args, **kwargs)
        return wrapper
    return decorator


def any_role_required(*roles):
    allowed = {str(r).strip().lower() for r in roles if r}
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            current = str(session.get("role") or "").strip().lower()
            if current not in allowed:
                return jsonify({"error": "Forbidden"}), 403
            return f(*args, **kwargs)
        return wrapper
    return decorator


def permission_required(permission):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            role = session.get("normalized_role") or session.get("role")
            perms = session.get("permissions_json")
            if not can_permission(permission, role, perms):
                return jsonify({"error": "Permission denied"}), 403
            return f(*args, **kwargs)
        return wrapper
    return decorator


def faculty_self_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if session.get("role") != "faculty" or not session.get("faculty_id"):
            return jsonify({"error": "faculty only"}), 403
        return f(*args, **kwargs)
    return wrapper
