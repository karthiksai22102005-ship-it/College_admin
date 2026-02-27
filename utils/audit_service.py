import os
from datetime import datetime
from utils.data_store import load_data, save_data


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUDIT_STORE = os.path.join(BASE_DIR, "data", "audit_logs.store")


def log_event(actor_role, actor_id, action, target_type="", target_id="", meta=None):
    rows = load_data(AUDIT_STORE)
    if not isinstance(rows, list):
        rows = []

    rows.append({
        "timestamp": datetime.utcnow().isoformat(),
        "actor_role": actor_role or "",
        "actor_id": actor_id or "",
        "action": action or "",
        "target_type": target_type or "",
        "target_id": target_id or "",
        "meta": meta or {},
    })
    save_data(AUDIT_STORE, rows)


def get_logs(limit=200):
    rows = load_data(AUDIT_STORE)
    if not isinstance(rows, list):
        return []
    return list(reversed(rows))[: max(1, int(limit or 200))]
