import os
import uuid
import sqlite3
from datetime import datetime

from utils.data_store import DB_BACKEND, DB_PATH, DATABASE_URL


def _is_pg():
    return str(DB_BACKEND or "").strip().lower() in {"postgres", "postgresql", "pg"}


def _connect_sqlite():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.execute("PRAGMA busy_timeout=30000;")
    return conn


def _connect_pg():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is required when DB_BACKEND=postgres")
    import psycopg
    return psycopg.connect(DATABASE_URL)


def init_erp_tables():
    if _is_pg():
        with _connect_pg() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS faculty_assignments (
                        assignment_id TEXT PRIMARY KEY,
                        faculty_id TEXT NOT NULL,
                        subject TEXT NOT NULL,
                        section_name TEXT NOT NULL,
                        semester TEXT,
                        academic_year TEXT,
                        timetable_id TEXT,
                        weekly_workload_hours INTEGER NOT NULL DEFAULT 0,
                        lecture_hours INTEGER NOT NULL DEFAULT 0,
                        lab_hours INTEGER NOT NULL DEFAULT 0,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS leave_requests (
                        leave_id TEXT PRIMARY KEY,
                        faculty_id TEXT NOT NULL,
                        from_date TEXT NOT NULL,
                        to_date TEXT NOT NULL,
                        reason TEXT NOT NULL,
                        status TEXT NOT NULL DEFAULT 'PENDING',
                        reviewed_by TEXT,
                        reviewed_at TEXT,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS study_materials (
                        material_id TEXT PRIMARY KEY,
                        faculty_id TEXT NOT NULL,
                        title TEXT NOT NULL,
                        description TEXT,
                        subject TEXT,
                        section_name TEXT,
                        academic_year TEXT,
                        file_path TEXT,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS attendance_entries (
                        attendance_id TEXT PRIMARY KEY,
                        faculty_id TEXT NOT NULL,
                        subject TEXT NOT NULL,
                        section_name TEXT NOT NULL,
                        entry_date TEXT NOT NULL,
                        period_name TEXT NOT NULL,
                        status TEXT NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS internal_marks (
                        mark_id TEXT PRIMARY KEY,
                        faculty_id TEXT NOT NULL,
                        student_roll_no TEXT NOT NULL,
                        subject TEXT NOT NULL,
                        exam_type TEXT NOT NULL,
                        marks_obtained REAL NOT NULL,
                        max_marks REAL NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS staff_tasks (
                        task_id TEXT PRIMARY KEY,
                        faculty_id TEXT NOT NULL,
                        title TEXT NOT NULL,
                        details TEXT,
                        status TEXT NOT NULL DEFAULT 'PENDING',
                        due_date TEXT,
                        assigned_by TEXT,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );
                    """
                )
            conn.commit()
        return

    with _connect_sqlite() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS faculty_assignments (
                assignment_id TEXT PRIMARY KEY,
                faculty_id TEXT NOT NULL,
                subject TEXT NOT NULL,
                section_name TEXT NOT NULL,
                semester TEXT,
                academic_year TEXT,
                timetable_id TEXT,
                weekly_workload_hours INTEGER NOT NULL DEFAULT 0,
                lecture_hours INTEGER NOT NULL DEFAULT 0,
                lab_hours INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS leave_requests (
                leave_id TEXT PRIMARY KEY,
                faculty_id TEXT NOT NULL,
                from_date TEXT NOT NULL,
                to_date TEXT NOT NULL,
                reason TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'PENDING',
                reviewed_by TEXT,
                reviewed_at TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS study_materials (
                material_id TEXT PRIMARY KEY,
                faculty_id TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                subject TEXT,
                section_name TEXT,
                academic_year TEXT,
                file_path TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS attendance_entries (
                attendance_id TEXT PRIMARY KEY,
                faculty_id TEXT NOT NULL,
                subject TEXT NOT NULL,
                section_name TEXT NOT NULL,
                entry_date TEXT NOT NULL,
                period_name TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS internal_marks (
                mark_id TEXT PRIMARY KEY,
                faculty_id TEXT NOT NULL,
                student_roll_no TEXT NOT NULL,
                subject TEXT NOT NULL,
                exam_type TEXT NOT NULL,
                marks_obtained REAL NOT NULL,
                max_marks REAL NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS staff_tasks (
                task_id TEXT PRIMARY KEY,
                faculty_id TEXT NOT NULL,
                title TEXT NOT NULL,
                details TEXT,
                status TEXT NOT NULL DEFAULT 'PENDING',
                due_date TEXT,
                assigned_by TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.commit()


def _rows_to_dicts(rows):
    out = []
    for row in rows or []:
        if isinstance(row, dict):
            out.append(dict(row))
        else:
            out.append(dict(row))
    return out


def _now():
    return datetime.utcnow().isoformat()


def list_assignments(faculty_id):
    if _is_pg():
        with _connect_pg() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT assignment_id, faculty_id, subject, section_name, semester, academic_year, timetable_id,
                           weekly_workload_hours, lecture_hours, lab_hours, created_at, updated_at
                    FROM faculty_assignments
                    WHERE faculty_id = %s
                    ORDER BY created_at DESC
                    """,
                    (faculty_id,),
                )
                rows = cur.fetchall()
                cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in rows]
    with _connect_sqlite() as conn:
        rows = conn.execute(
            """
            SELECT assignment_id, faculty_id, subject, section_name, semester, academic_year, timetable_id,
                   weekly_workload_hours, lecture_hours, lab_hours, created_at, updated_at
            FROM faculty_assignments
            WHERE faculty_id = ?
            ORDER BY created_at DESC
            """,
            (faculty_id,),
        ).fetchall()
    return _rows_to_dicts(rows)


def upsert_assignment(faculty_id, subject, section_name, semester="", academic_year="", timetable_id="", weekly_workload_hours=0, lecture_hours=0, lab_hours=0):
    now = _now()
    assignment_id = f"asg-{uuid.uuid4().hex[:16]}"
    if _is_pg():
        with _connect_pg() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO faculty_assignments(
                        assignment_id, faculty_id, subject, section_name, semester, academic_year, timetable_id,
                        weekly_workload_hours, lecture_hours, lab_hours, created_at, updated_at
                    )
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    """,
                    (
                        assignment_id,
                        faculty_id,
                        subject,
                        section_name,
                        semester,
                        academic_year,
                        timetable_id,
                        int(weekly_workload_hours or 0),
                        int(lecture_hours or 0),
                        int(lab_hours or 0),
                        now,
                        now,
                    ),
                )
            conn.commit()
    else:
        with _connect_sqlite() as conn:
            conn.execute(
                """
                INSERT INTO faculty_assignments(
                    assignment_id, faculty_id, subject, section_name, semester, academic_year, timetable_id,
                    weekly_workload_hours, lecture_hours, lab_hours, created_at, updated_at
                )
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    assignment_id,
                    faculty_id,
                    subject,
                    section_name,
                    semester,
                    academic_year,
                    timetable_id,
                    int(weekly_workload_hours or 0),
                    int(lecture_hours or 0),
                    int(lab_hours or 0),
                    now,
                    now,
                ),
            )
            conn.commit()
    return assignment_id


def create_leave_request(faculty_id, from_date, to_date, reason):
    leave_id = f"lv-{uuid.uuid4().hex[:16]}"
    now = _now()
    if _is_pg():
        with _connect_pg() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO leave_requests(leave_id, faculty_id, from_date, to_date, reason, status, created_at)
                    VALUES (%s,%s,%s,%s,%s,'PENDING',%s)
                    """,
                    (leave_id, faculty_id, from_date, to_date, reason, now),
                )
            conn.commit()
    else:
        with _connect_sqlite() as conn:
            conn.execute(
                """
                INSERT INTO leave_requests(leave_id, faculty_id, from_date, to_date, reason, status, created_at)
                VALUES (?,?,?,?,?,'PENDING',?)
                """,
                (leave_id, faculty_id, from_date, to_date, reason, now),
            )
            conn.commit()
    return leave_id


def list_leave_requests_by_faculty(faculty_id):
    if _is_pg():
        with _connect_pg() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT leave_id, faculty_id, from_date, to_date, reason, status, reviewed_by, reviewed_at, created_at
                    FROM leave_requests
                    WHERE faculty_id = %s
                    ORDER BY created_at DESC
                    """,
                    (faculty_id,),
                )
                rows = cur.fetchall()
                cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in rows]
    with _connect_sqlite() as conn:
        rows = conn.execute(
            """
            SELECT leave_id, faculty_id, from_date, to_date, reason, status, reviewed_by, reviewed_at, created_at
            FROM leave_requests
            WHERE faculty_id = ?
            ORDER BY created_at DESC
            """,
            (faculty_id,),
        ).fetchall()
    return _rows_to_dicts(rows)


def list_pending_leave_requests(faculty_ids):
    ids = [str(x) for x in (faculty_ids or []) if x]
    if not ids:
        return []
    if _is_pg():
        with _connect_pg() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT leave_id, faculty_id, from_date, to_date, reason, status, reviewed_by, reviewed_at, created_at
                    FROM leave_requests
                    WHERE status = 'PENDING' AND faculty_id = ANY(%s)
                    ORDER BY created_at ASC
                    """,
                    (ids,),
                )
                rows = cur.fetchall()
                cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in rows]

    marks = ",".join("?" for _ in ids)
    with _connect_sqlite() as conn:
        rows = conn.execute(
            f"""
            SELECT leave_id, faculty_id, from_date, to_date, reason, status, reviewed_by, reviewed_at, created_at
            FROM leave_requests
            WHERE status = 'PENDING' AND faculty_id IN ({marks})
            ORDER BY created_at ASC
            """,
            tuple(ids),
        ).fetchall()
    return _rows_to_dicts(rows)


def decide_leave(leave_id, reviewer_id, decision):
    status = str(decision or "").strip().upper()
    if status not in {"APPROVED", "REJECTED"}:
        raise ValueError("decision must be APPROVED or REJECTED")
    reviewed_at = _now()
    if _is_pg():
        with _connect_pg() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE leave_requests
                    SET status = %s, reviewed_by = %s, reviewed_at = %s
                    WHERE leave_id = %s
                    """,
                    (status, reviewer_id, reviewed_at, leave_id),
                )
            conn.commit()
    else:
        with _connect_sqlite() as conn:
            conn.execute(
                """
                UPDATE leave_requests
                SET status = ?, reviewed_by = ?, reviewed_at = ?
                WHERE leave_id = ?
                """,
                (status, reviewer_id, reviewed_at, leave_id),
            )
            conn.commit()


def create_material(faculty_id, title, description, subject, section_name, academic_year, file_path):
    material_id = f"mat-{uuid.uuid4().hex[:16]}"
    now = _now()
    if _is_pg():
        with _connect_pg() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO study_materials(material_id, faculty_id, title, description, subject, section_name, academic_year, file_path, created_at)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    """,
                    (material_id, faculty_id, title, description, subject, section_name, academic_year, file_path, now),
                )
            conn.commit()
    else:
        with _connect_sqlite() as conn:
            conn.execute(
                """
                INSERT INTO study_materials(material_id, faculty_id, title, description, subject, section_name, academic_year, file_path, created_at)
                VALUES (?,?,?,?,?,?,?,?,?)
                """,
                (material_id, faculty_id, title, description, subject, section_name, academic_year, file_path, now),
            )
            conn.commit()
    return material_id


def list_materials(faculty_id):
    if _is_pg():
        with _connect_pg() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT material_id, faculty_id, title, description, subject, section_name, academic_year, file_path, created_at
                    FROM study_materials
                    WHERE faculty_id = %s
                    ORDER BY created_at DESC
                    """,
                    (faculty_id,),
                )
                rows = cur.fetchall()
                cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in rows]
    with _connect_sqlite() as conn:
        rows = conn.execute(
            """
            SELECT material_id, faculty_id, title, description, subject, section_name, academic_year, file_path, created_at
            FROM study_materials
            WHERE faculty_id = ?
            ORDER BY created_at DESC
            """,
            (faculty_id,),
        ).fetchall()
    return _rows_to_dicts(rows)


def create_attendance(faculty_id, subject, section_name, entry_date, period_name, status):
    attendance_id = f"att-{uuid.uuid4().hex[:16]}"
    now = _now()
    if _is_pg():
        with _connect_pg() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO attendance_entries(attendance_id, faculty_id, subject, section_name, entry_date, period_name, status, created_at)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                    """,
                    (attendance_id, faculty_id, subject, section_name, entry_date, period_name, status, now),
                )
            conn.commit()
    else:
        with _connect_sqlite() as conn:
            conn.execute(
                """
                INSERT INTO attendance_entries(attendance_id, faculty_id, subject, section_name, entry_date, period_name, status, created_at)
                VALUES (?,?,?,?,?,?,?,?)
                """,
                (attendance_id, faculty_id, subject, section_name, entry_date, period_name, status, now),
            )
            conn.commit()
    return attendance_id


def create_internal_mark(faculty_id, student_roll_no, subject, exam_type, marks_obtained, max_marks):
    mark_id = f"mk-{uuid.uuid4().hex[:16]}"
    now = _now()
    if _is_pg():
        with _connect_pg() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO internal_marks(mark_id, faculty_id, student_roll_no, subject, exam_type, marks_obtained, max_marks, created_at)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                    """,
                    (mark_id, faculty_id, student_roll_no, subject, exam_type, float(marks_obtained), float(max_marks), now),
                )
            conn.commit()
    else:
        with _connect_sqlite() as conn:
            conn.execute(
                """
                INSERT INTO internal_marks(mark_id, faculty_id, student_roll_no, subject, exam_type, marks_obtained, max_marks, created_at)
                VALUES (?,?,?,?,?,?,?,?)
                """,
                (mark_id, faculty_id, student_roll_no, subject, exam_type, float(marks_obtained), float(max_marks), now),
            )
            conn.commit()
    return mark_id


def create_task(faculty_id, title, details, due_date, assigned_by):
    task_id = f"tsk-{uuid.uuid4().hex[:16]}"
    now = _now()
    if _is_pg():
        with _connect_pg() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO staff_tasks(task_id, faculty_id, title, details, status, due_date, assigned_by, created_at, updated_at)
                    VALUES (%s,%s,%s,%s,'PENDING',%s,%s,%s,%s)
                    """,
                    (task_id, faculty_id, title, details, due_date, assigned_by, now, now),
                )
            conn.commit()
    else:
        with _connect_sqlite() as conn:
            conn.execute(
                """
                INSERT INTO staff_tasks(task_id, faculty_id, title, details, status, due_date, assigned_by, created_at, updated_at)
                VALUES (?,?,?,?, 'PENDING', ?, ?, ?, ?)
                """,
                (task_id, faculty_id, title, details, due_date, assigned_by, now, now),
            )
            conn.commit()
    return task_id


def list_tasks(faculty_id):
    if _is_pg():
        with _connect_pg() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT task_id, faculty_id, title, details, status, due_date, assigned_by, created_at, updated_at
                    FROM staff_tasks
                    WHERE faculty_id = %s
                    ORDER BY created_at DESC
                    """,
                    (faculty_id,),
                )
                rows = cur.fetchall()
                cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in rows]
    with _connect_sqlite() as conn:
        rows = conn.execute(
            """
            SELECT task_id, faculty_id, title, details, status, due_date, assigned_by, created_at, updated_at
            FROM staff_tasks
            WHERE faculty_id = ?
            ORDER BY created_at DESC
            """,
            (faculty_id,),
        ).fetchall()
    return _rows_to_dicts(rows)
