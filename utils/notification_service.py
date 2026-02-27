import os
import uuid
from datetime import datetime
from utils.data_store import load_data, save_data


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NOTIFICATIONS_STORE = os.path.join(BASE_DIR, "data", "notifications.store")


def _load_rows():
    rows = load_data(NOTIFICATIONS_STORE)
    if not isinstance(rows, list):
        return []
    return rows


def _save_rows(rows):
    save_data(NOTIFICATIONS_STORE, rows if isinstance(rows, list) else [])


def push_notification(user_role, user_id, title, message, payload=None):
    rows = _load_rows()
    rows.append({
        "notification_id": "ntf-" + uuid.uuid4().hex[:16],
        "user_role": user_role or "",
        "user_id": user_id or "",
        "title": title or "",
        "message": message or "",
        "payload": payload or {},
        "is_read": False,
        "created_at": datetime.utcnow().isoformat(),
    })
    _save_rows(rows)


def list_notifications(user_role, user_id, unread_only=False, limit=100):
    rows = _load_rows()
    out = []
    for row in reversed(rows):
        if row.get("user_role") != user_role:
            continue
        if user_id and row.get("user_id") not in ("*", user_id):
            continue
        if unread_only and row.get("is_read"):
            continue
        out.append(row)
        if len(out) >= max(1, int(limit or 100)):
            break
    return out


def mark_as_read(user_role, user_id, notification_id):
    rows = _load_rows()
    changed = False
    for row in rows:
        if row.get("notification_id") != notification_id:
            continue
        if row.get("user_role") != user_role:
            continue
        if user_id and row.get("user_id") not in ("*", user_id):
            continue
        row["is_read"] = True
        changed = True
        break
    if changed:
        _save_rows(rows)
    return changed
