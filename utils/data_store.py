import base64
import json
import os
import pickle
import sqlite3
import zlib
import pandas as pd
from copy import deepcopy
from io import BytesIO
from utils.storage_backend import path_to_storage_key, read_bytes
from utils.rbac import normalize_role_from_designation, default_permissions_json_for_role, compute_experience_years
from services.department_service import canonicalize_department_code, infer_staff_type_from_designation


DEFAULT_PERSONAL_DOCUMENTS = {
    "aadhaar": "",
    "pan": "",
    "bank_passbook": "",
    "service_register": "",
    "joining_letter": "",
    "others": [],
}

DEFAULT_QUALIFICATION_DOCUMENTS = {
    "ssc_memo": "",
    "inter_memo": "",
    "btech_memo": "",
    "mtech_memo": "",
    "phd_memo": "",
    "others": [],
}

DEFAULT_FACULTY_SHAPE = {
    "faculty_id": "",
    "name": "",
    "full_name": "",
    "gender": "",
    "date_of_birth": "",
    "username": "",
    "password": "",
    "password_hash": "",
    "department": "",
    "employment_type": "",
    "joining_date": "",
    "experience_years": 0,
    "status": "Active",
    "designation": "",
    "normalized_role": "STAFF",
    "role": "STAFF",
    "permissions_json": "",
    "account_locked": False,
    "email": "",
    "official_email": "",
    "phone": "",
    "phone_number": "",
    "address": "",
    "emergency_contact_name": "",
    "emergency_contact_phone": "",
    "photo": "",
    "qualifications": [],
    "qualifications_list": [],
    "highest_qualification": "",
    "research_area": "",
    "subject_expertise": [],
    "assigned_subjects": [],
    "assigned_sections": [],
    "semester": "",
    "academic_year": "",
    "timetable_id": "",
    "weekly_workload_hours": 0,
    "lecture_hours": 0,
    "lab_hours": 0,
    "publications": [],
    "publications_list": [],
    "certifications": [],
    "phd_status": "",
    "appraisal_score": 0,
    "student_feedback_rating": 0,
    "workload": {
        "subjects": [],
        "hours_per_week": 0,
    },
    "last_login": "",
    "office_room": "",
    "extension": "",
    "admin_notes": "",
    "personal_documents": DEFAULT_PERSONAL_DOCUMENTS,
    "qualification_documents": DEFAULT_QUALIFICATION_DOCUMENTS,
}


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.getenv("APP_DB_PATH", os.path.join(BASE_DIR, "data", "college_admin.db"))
DB_BACKEND = str(os.getenv("DB_BACKEND", "sqlite")).strip().lower()
DATABASE_URL = str(os.getenv("DATABASE_URL", "")).strip()
COMPRESS_THRESHOLD_BYTES = int(os.getenv("DB_COMPRESS_THRESHOLD_BYTES", "4096"))


def _use_postgres():
    return DB_BACKEND in {"postgres", "postgresql", "pg"}


def _db_connect():
    if _use_postgres():
        raise RuntimeError("Use _pg_connect() for postgres backend")
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.execute("PRAGMA busy_timeout=30000;")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS app_store (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    return conn


def _pg_connect():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is required when DB_BACKEND=postgres")
    try:
        import psycopg
    except Exception as exc:
        raise RuntimeError("DB_BACKEND=postgres requires psycopg package") from exc

    conn = psycopg.connect(DATABASE_URL)
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS app_store (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        conn.commit()
    return conn


def _db_get(key):
    if _use_postgres():
        with _pg_connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT value FROM app_store WHERE key = %s", (key,))
                row = cur.fetchone()
        return row[0] if row else None
    with _db_connect() as conn:
        row = conn.execute("SELECT value FROM app_store WHERE key = ?", (key,)).fetchone()
    return row[0] if row else None


def _db_set(key, value):
    if _use_postgres():
        with _pg_connect() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO app_store(key, value, updated_at)
                    VALUES (%s, %s, NOW())
                    ON CONFLICT(key) DO UPDATE SET
                        value = EXCLUDED.value,
                        updated_at = NOW()
                """, (key, value))
                conn.commit()
        return
    with _db_connect() as conn:
        conn.execute("""
            INSERT INTO app_store(key, value, updated_at)
            VALUES (?, ?, datetime('now'))
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = datetime('now')
        """, (key, value))
        conn.commit()


def _encode_store_value(data):
    payload_json = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    payload_bytes = payload_json.encode("utf-8")
    if len(payload_bytes) >= COMPRESS_THRESHOLD_BYTES:
        packed = zlib.compress(payload_bytes, level=9)
        return json.dumps({
            "v": 2,
            "enc": "zlib+base64",
            "payload": base64.b64encode(packed).decode("ascii"),
        }, ensure_ascii=False)

    return json.dumps({
        "v": 2,
        "enc": "utf-8",
        "payload": payload_json,
    }, ensure_ascii=False)


def _decode_store_value(raw):
    try:
        obj = json.loads(raw)
    except Exception:
        return []

    # Backward compatibility: old rows had raw JSON data directly.
    if not isinstance(obj, dict) or "enc" not in obj or "payload" not in obj:
        return obj

    enc = str(obj.get("enc") or "").strip().lower()
    payload = obj.get("payload")

    try:
        if enc == "utf-8":
            return json.loads(str(payload or "[]"))
        if enc == "zlib+base64":
            compressed = base64.b64decode(str(payload or "").encode("ascii"))
            restored = zlib.decompress(compressed).decode("utf-8")
            return json.loads(restored)
    except Exception:
        return []

    return []


def _candidate_keys(path):
    key = path_to_storage_key(path)
    keys = [key]
    if key.endswith(".store"):
        keys.append(key[:-6] + ".pkl")
        keys.append(key[:-6] + ".json")
    elif key.endswith(".pkl"):
        keys.append(key[:-4] + ".store")
        keys.append(key[:-4] + ".json")
    elif key.endswith(".json"):
        keys.append(key[:-5] + ".store")
        keys.append(key[:-5] + ".pkl")
    return list(dict.fromkeys(keys))


def _load_legacy_from_files(path):
    # One-time importer for existing file-based datasets.
    # Order preference: .json first, then .pkl.
    key = path_to_storage_key(path)
    if key.endswith(".store"):
        base = key[:-6]
        candidates = [f"{base}.json", f"{base}.pkl"]
    elif key.endswith(".pkl"):
        base = key[:-4]
        candidates = [f"{base}.json", f"{base}.pkl"]
    elif key.endswith(".json"):
        base = key[:-5]
        candidates = [f"{base}.json", f"{base}.pkl"]
    else:
        candidates = [f"{key}.json", f"{key}.pkl"]

    for candidate in candidates:
        raw = read_bytes(candidate)
        if raw is None:
            continue
        if candidate.endswith(".json"):
            try:
                return json.loads(raw.decode("utf-8"))
            except Exception:
                continue
        if candidate.endswith(".pkl"):
            try:
                return pickle.load(BytesIO(raw))
            except Exception:
                continue
    return None


def load_data(path):
    keys = _candidate_keys(path)
    target_key = keys[0] if keys else path_to_storage_key(path)
    for key in keys:
        raw = _db_get(key)
        if raw is not None:
            data = _decode_store_value(raw)
            # Normalize storage key to the requested/new key.
            if key != target_key:
                _db_set(target_key, _encode_store_value(data))
            return data

    legacy = _load_legacy_from_files(path)
    if legacy is not None:
        _db_set(target_key, _encode_store_value(legacy))
        return legacy

    return []


def save_data(path, data):
    key = path_to_storage_key(path)
    payload = _encode_store_value(data)
    _db_set(key, payload)


def _normalize_subject_expertise(value):
    if not isinstance(value, list):
        return []

    normalized = []
    for item in value:
        if isinstance(item, dict):
            normalized.append({
                "subject": str(item.get("subject", "")).strip(),
                "cert_ids": list(item.get("cert_ids", []) or []),
            })
        elif isinstance(item, str):
            normalized.append({"subject": item.strip(), "cert_ids": []})
    return [x for x in normalized if x.get("subject")]


def ensure_faculty_schema_record(record):
    if not isinstance(record, dict):
        record = {}

    normalized = deepcopy(DEFAULT_FACULTY_SHAPE)
    normalized.update(record)

    normalized["qualifications"] = list(normalized.get("qualifications") or [])
    normalized["qualifications_list"] = list(normalized.get("qualifications_list") or [])
    normalized["publications"] = list(normalized.get("publications") or [])
    normalized["publications_list"] = list(normalized.get("publications_list") or [])
    normalized["certifications"] = list(normalized.get("certifications") or [])
    normalized["subject_expertise"] = _normalize_subject_expertise(normalized.get("subject_expertise"))
    normalized["assigned_subjects"] = list(normalized.get("assigned_subjects") or [])
    normalized["assigned_sections"] = list(normalized.get("assigned_sections") or [])

    if not normalized.get("full_name"):
        normalized["full_name"] = normalized.get("name", "")
    if not normalized.get("name"):
        normalized["name"] = normalized.get("full_name", "")
    if not normalized.get("official_email"):
        normalized["official_email"] = normalized.get("email", "")
    if not normalized.get("email"):
        normalized["email"] = normalized.get("official_email", "")
    if not normalized.get("phone_number"):
        normalized["phone_number"] = normalized.get("phone", "")
    if not normalized.get("phone"):
        normalized["phone"] = normalized.get("phone_number", "")

    role = normalize_role_from_designation(normalized.get("designation"))
    normalized["normalized_role"] = str(normalized.get("normalized_role") or role)
    normalized["role"] = str(normalized.get("role") or normalized["normalized_role"])
    if not normalized.get("permissions_json"):
        normalized["permissions_json"] = default_permissions_json_for_role(normalized["normalized_role"])
    normalized["experience_years"] = compute_experience_years(normalized.get("joining_date"))
    if not normalized.get("department_code"):
        normalized["department_code"] = canonicalize_department_code(normalized.get("department"))
    if not normalized.get("staff_type"):
        normalized["staff_type"] = infer_staff_type_from_designation(normalized.get("designation"))

    workload = normalized.get("workload")
    if not isinstance(workload, dict):
        workload = {}
    normalized["workload"] = {
        "subjects": list(workload.get("subjects") or []),
        "hours_per_week": workload.get("hours_per_week") or 0,
    }

    docs = deepcopy(DEFAULT_PERSONAL_DOCUMENTS)
    incoming_docs = normalized.get("personal_documents")
    if isinstance(incoming_docs, dict):
        docs.update(incoming_docs)
    docs["others"] = list(docs.get("others") or [])
    normalized["personal_documents"] = docs

    qual_docs = deepcopy(DEFAULT_QUALIFICATION_DOCUMENTS)
    incoming_qual_docs = normalized.get("qualification_documents")
    if isinstance(incoming_qual_docs, dict):
        qual_docs.update(incoming_qual_docs)
    qual_docs["others"] = list(qual_docs.get("others") or [])
    normalized["qualification_documents"] = qual_docs

    return normalized


def load_faculty_data(path):
    rows = load_data(path)
    if not isinstance(rows, list):
        return []
    return [ensure_faculty_schema_record(row) for row in rows]


# ================= Excel Export =================
def export_faculty_to_excel(store_key_path, excel_path):
    data = load_data(store_key_path)

    if not data:
        return False

    rows = []
    for f in data:
        rows.append({
            "Faculty ID": f.get("faculty_id"),
            "Name": f.get("name"),
            "Department": f.get("department"),
            "Designation": f.get("designation"),
            "Email": f.get("email"),
            "Phone": f.get("phone"),
            "Username": f.get("username"),
            "Password Set": "Yes" if f.get("password") else "No",
            "Qualifications": "; ".join([f"{q.get('type')} ({q.get('year', 'N/A')})" for q in f.get("qualifications", [])]),
            "Expertise": "; ".join(
                [e.get("subject", "") if isinstance(e, dict) else str(e) for e in f.get("subject_expertise", [])]
            ),
            "Publications": "; ".join([f"{p.get('type')}: {p.get('details')}" for p in f.get("publications", [])]),
            "Books": "; ".join([f"{b.get('title')} - {b.get('author')}" for b in f.get("books", [])]),
            "Research Papers": "; ".join([f"{p.get('title')} - {p.get('year')}" for p in f.get("research_papers", [])])
        })

    df = pd.DataFrame(rows)
    os.makedirs(os.path.dirname(excel_path), exist_ok=True)
    df.to_excel(excel_path, index=False)

    return True
