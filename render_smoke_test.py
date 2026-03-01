import io
import json
import traceback

from app import app


def _ok(cond, message):
    if not cond:
        raise AssertionError(message)


def _json(resp):
    try:
        return resp.get_json(silent=True) or {}
    except Exception:
        return {}


def run():
    results = []
    with app.test_client() as client:
        # Health + static assets
        resp = client.get("/health")
        _ok(resp.status_code == 200, f"/health failed: {resp.status_code}")
        results.append("health: ok")

        logo = client.get("/static/RCE%20Logo.png")
        _ok(logo.status_code == 200, f"logo missing: {logo.status_code}")
        results.append("logo: ok")

        placeholder = client.get("/static/default-user.png")
        _ok(placeholder.status_code == 200, f"default-user missing: {placeholder.status_code}")
        results.append("default-user: ok")

        # Public pages
        _ok(client.get("/").status_code == 200, "home page failed")
        _ok(client.get("/login").status_code == 200, "login page failed")
        results.append("public pages: ok")

        # Admin login
        login = client.post(
            "/auth/login",
            json={"username": "ADMIN001", "password": "admin123"},
        )
        _ok(login.status_code == 200, f"admin login failed: {login.status_code} {_json(login)}")
        _ok(_json(login).get("role") == "admin", f"admin login role mismatch: {_json(login)}")
        results.append("admin login: ok")

        # Admin pages/apis
        _ok(client.get("/admin-dashboard").status_code == 200, "admin dashboard page failed")

        dep = client.get("/admin/departments")
        _ok(dep.status_code == 200, f"/admin/departments failed: {dep.status_code}")
        dep_json = _json(dep)
        _ok("departments" in dep_json, "departments payload missing")
        results.append("admin departments: ok")

        fac_list_resp = client.get("/admin/faculty-list")
        _ok(fac_list_resp.status_code == 200, f"/admin/faculty-list failed: {fac_list_resp.status_code}")
        fac_list = _json(fac_list_resp).get("faculty", [])
        _ok(isinstance(fac_list, list), "faculty list payload invalid")
        results.append(f"faculty list: ok ({len(fac_list)} rows)")

        # Notifications endpoint should at least respond
        ntf = client.get("/admin/notifications")
        _ok(ntf.status_code == 200, f"/admin/notifications failed: {ntf.status_code}")
        results.append("admin notifications: ok")

        # Faculty workflow tests (if at least one faculty exists)
        if fac_list:
            faculty_id = fac_list[0].get("faculty_id")
            username = fac_list[0].get("username")
            _ok(faculty_id, "faculty_id missing in first row")

            # Upload + download + delete personal doc as admin
            fake_pdf = io.BytesIO(b"%PDF-1.4\n% smoke test\n")
            upload = client.post(
                f"/admin/upload-personal-doc/{faculty_id}",
                data={"doc_type": "aadhaar", "file": (fake_pdf, "smoke.pdf")},
                content_type="multipart/form-data",
            )
            _ok(upload.status_code == 200, f"doc upload failed: {upload.status_code} {_json(upload)}")
            uploaded_docs = _json(upload).get("personal_documents", {})
            uploaded_path = uploaded_docs.get("aadhaar")
            _ok(uploaded_path, "uploaded doc path missing")
            results.append("doc upload: ok")

            dl = client.get(uploaded_path)
            _ok(dl.status_code == 200, f"doc download failed: {dl.status_code}")
            results.append("doc download: ok")

            delete = client.delete(f"/admin/delete-personal-doc/{faculty_id}/aadhaar")
            _ok(delete.status_code == 200, f"doc delete failed: {delete.status_code} {_json(delete)}")
            results.append("doc delete: ok")

            # Try faculty login with default excel import password
            if username:
                client.post("/auth/logout")
                faculty_login = client.post(
                    "/auth/login",
                    json={"username": username, "password": "welcome123"},
                )
                if faculty_login.status_code == 200 and _json(faculty_login).get("role") == "faculty":
                    _ok(client.get("/faculty-dashboard").status_code == 200, "faculty dashboard page failed")
                    _ok(client.get("/faculty-notifications").status_code == 200, "faculty notifications failed")
                    results.append("faculty login/dashboard: ok")
                else:
                    results.append(
                        "faculty login skipped: default password may have been changed for this user"
                    )

    print("Smoke Test Results")
    for item in results:
        print(f"- {item}")
    print("\nPASS")


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:
        print("FAIL")
        print(str(exc))
        print(traceback.format_exc())
        raise
