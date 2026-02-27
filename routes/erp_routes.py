from flask import Blueprint, jsonify, request, session

from utils.guards import faculty_self_required, role_required, permission_required
from utils.audit_service import log_event
from utils.notification_service import push_notification
from utils.file_handler import save_file
from utils.erp_repository import (
    init_erp_tables,
    list_assignments,
    upsert_assignment,
    create_leave_request,
    list_leave_requests_by_faculty,
    list_pending_leave_requests,
    decide_leave,
    create_material,
    list_materials,
    create_attendance,
    create_internal_mark,
    create_task,
    list_tasks,
)
from utils.data_store import load_faculty_data
from utils.rbac import can_permission
from config import Config


erp_bp = Blueprint("erp_bp", __name__)
ERP_SCHEMA_READY = False


@erp_bp.before_app_request
def _ensure_erp_schema():
    global ERP_SCHEMA_READY
    if ERP_SCHEMA_READY:
        return
    init_erp_tables()
    ERP_SCHEMA_READY = True


def _faculty_rows():
    return load_faculty_data(Config.FACULTY_STORE)


def _get_faculty_by_id(faculty_id):
    rows = _faculty_rows()
    return next((f for f in rows if f.get("faculty_id") == faculty_id), None)


def _get_department_member_ids(department_name):
    dept = str(department_name or "").strip().lower()
    if not dept:
        return []
    rows = _faculty_rows()
    return [f.get("faculty_id") for f in rows if str(f.get("department") or "").strip().lower() == dept and f.get("faculty_id")]


@erp_bp.route("/me/overview", methods=["GET"])
@faculty_self_required
def erp_my_overview():
    faculty_id = session.get("faculty_id")
    fac = _get_faculty_by_id(faculty_id)
    if not fac:
        return jsonify({"error": "Faculty not found"}), 404
    assignments = list_assignments(faculty_id)
    tasks = list_tasks(faculty_id)
    leaves = list_leave_requests_by_faculty(faculty_id)
    materials = list_materials(faculty_id)

    pending_approval = []
    if str(fac.get("normalized_role") or "").upper() == "HOD":
        ids = _get_department_member_ids(fac.get("department"))
        pending_approval = [r for r in list_pending_leave_requests(ids) if r.get("faculty_id") != faculty_id]

    return jsonify({
        "normalized_role": fac.get("normalized_role"),
        "assignments": assignments,
        "tasks": tasks,
        "leave_requests": leaves,
        "pending_leave_approvals": pending_approval,
        "materials": materials,
    })


@erp_bp.route("/leave/apply", methods=["POST"])
@faculty_self_required
@permission_required("apply_leave")
def apply_leave():
    data = request.json or {}
    from_date = str(data.get("from_date") or "").strip()
    to_date = str(data.get("to_date") or "").strip()
    reason = str(data.get("reason") or "").strip()
    if not from_date or not to_date or not reason:
        return jsonify({"error": "from_date, to_date, and reason are required"}), 400

    faculty_id = session.get("faculty_id")
    leave_id = create_leave_request(faculty_id, from_date, to_date, reason)
    log_event("faculty", session.get("username"), "apply_leave", "leave_request", leave_id)
    push_notification("admin", "*", "Leave Request Submitted", f"{session.get('username')} submitted leave request.")
    return jsonify({"message": "Leave request submitted", "leave_id": leave_id}), 201


@erp_bp.route("/leave/my", methods=["GET"])
@faculty_self_required
def my_leave_requests():
    faculty_id = session.get("faculty_id")
    return jsonify({"leave_requests": list_leave_requests_by_faculty(faculty_id)})


@erp_bp.route("/leave/pending-department", methods=["GET"])
@faculty_self_required
@permission_required("approve_leave")
def pending_department_leaves():
    faculty_id = session.get("faculty_id")
    fac = _get_faculty_by_id(faculty_id)
    if not fac:
        return jsonify({"error": "Faculty not found"}), 404
    ids = _get_department_member_ids(fac.get("department"))
    rows = [r for r in list_pending_leave_requests(ids) if r.get("faculty_id") != faculty_id]
    return jsonify({"pending": rows})


@erp_bp.route("/leave/<leave_id>/decision", methods=["PUT"])
@faculty_self_required
@permission_required("approve_leave")
def leave_decision(leave_id):
    data = request.json or {}
    decision = str(data.get("decision") or "").strip().upper()
    if decision not in {"APPROVED", "REJECTED"}:
        return jsonify({"error": "decision must be APPROVED or REJECTED"}), 400
    try:
        decide_leave(leave_id, session.get("faculty_id"), decision)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    log_event("faculty", session.get("username"), "decide_leave", "leave_request", leave_id, {"decision": decision})
    return jsonify({"message": f"Leave request {decision.lower()}"}), 200


@erp_bp.route("/attendance/mark", methods=["POST"])
@faculty_self_required
@permission_required("mark_attendance")
def mark_attendance():
    data = request.json or {}
    subject = str(data.get("subject") or "").strip()
    section_name = str(data.get("section_name") or "").strip()
    entry_date = str(data.get("entry_date") or "").strip()
    period_name = str(data.get("period_name") or "").strip()
    status = str(data.get("status") or "PRESENT").strip().upper()
    if not all([subject, section_name, entry_date, period_name]):
        return jsonify({"error": "subject, section_name, entry_date, period_name are required"}), 400
    attendance_id = create_attendance(session.get("faculty_id"), subject, section_name, entry_date, period_name, status)
    log_event("faculty", session.get("username"), "mark_attendance", "attendance", attendance_id)
    return jsonify({"message": "Attendance marked", "attendance_id": attendance_id}), 201


@erp_bp.route("/marks/enter", methods=["POST"])
@faculty_self_required
@permission_required("enter_internal_marks")
def enter_marks():
    data = request.json or {}
    student_roll_no = str(data.get("student_roll_no") or "").strip()
    subject = str(data.get("subject") or "").strip()
    exam_type = str(data.get("exam_type") or "").strip()
    marks_obtained = data.get("marks_obtained")
    max_marks = data.get("max_marks")
    if not all([student_roll_no, subject, exam_type]) or marks_obtained is None or max_marks is None:
        return jsonify({"error": "student_roll_no, subject, exam_type, marks_obtained, max_marks are required"}), 400
    mark_id = create_internal_mark(
        session.get("faculty_id"),
        student_roll_no,
        subject,
        exam_type,
        marks_obtained,
        max_marks,
    )
    log_event("faculty", session.get("username"), "enter_internal_marks", "marks", mark_id)
    return jsonify({"message": "Marks saved", "mark_id": mark_id}), 201


@erp_bp.route("/materials/upload", methods=["POST"])
@faculty_self_required
def upload_material():
    role = session.get("normalized_role") or session.get("role")
    perms = session.get("permissions_json")
    if not (can_permission("upload_study_materials", role, perms) or can_permission("upload_documents", role, perms)):
        return jsonify({"error": "Permission denied"}), 403

    file = request.files.get("file")
    title = str(request.form.get("title") or "").strip()
    description = str(request.form.get("description") or "").strip()
    subject = str(request.form.get("subject") or "").strip()
    section_name = str(request.form.get("section_name") or "").strip()
    academic_year = str(request.form.get("academic_year") or "").strip()
    if not title:
        return jsonify({"error": "title is required"}), 400

    file_path = ""
    if file and file.filename:
        try:
            file_path = save_file(file, "rd", session.get("faculty_id"), tag=f"material_{title}")
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
    material_id = create_material(
        session.get("faculty_id"),
        title,
        description,
        subject,
        section_name,
        academic_year,
        file_path,
    )
    log_event("faculty", session.get("username"), "upload_study_material", "material", material_id)
    return jsonify({"message": "Material uploaded", "material_id": material_id}), 201


@erp_bp.route("/materials/my", methods=["GET"])
@faculty_self_required
def my_materials():
    return jsonify({"materials": list_materials(session.get("faculty_id"))})


@erp_bp.route("/tasks/my", methods=["GET"])
@faculty_self_required
def my_tasks():
    return jsonify({"tasks": list_tasks(session.get("faculty_id"))})


@erp_bp.route("/admin/assignments/upsert", methods=["POST"])
@role_required("admin")
def admin_upsert_assignment():
    data = request.json or {}
    faculty_id = str(data.get("faculty_id") or "").strip()
    subject = str(data.get("subject") or "").strip()
    section_name = str(data.get("section_name") or "").strip()
    if not all([faculty_id, subject, section_name]):
        return jsonify({"error": "faculty_id, subject, section_name are required"}), 400
    assignment_id = upsert_assignment(
        faculty_id=faculty_id,
        subject=subject,
        section_name=section_name,
        semester=str(data.get("semester") or "").strip(),
        academic_year=str(data.get("academic_year") or "").strip(),
        timetable_id=str(data.get("timetable_id") or "").strip(),
        weekly_workload_hours=int(data.get("weekly_workload_hours") or 0),
        lecture_hours=int(data.get("lecture_hours") or 0),
        lab_hours=int(data.get("lab_hours") or 0),
    )
    log_event("admin", session.get("username"), "assign_subject_workload", "faculty", faculty_id, {"assignment_id": assignment_id})
    fac = _get_faculty_by_id(faculty_id)
    push_notification("faculty", fac.get("username") if fac else None, "New Assignment", f"New assignment created for {faculty_id}.")
    return jsonify({"message": "Assignment saved", "assignment_id": assignment_id}), 201


@erp_bp.route("/admin/assignments/<faculty_id>", methods=["GET"])
@role_required("admin")
def admin_list_assignments(faculty_id):
    return jsonify({"assignments": list_assignments(faculty_id)})


@erp_bp.route("/admin/tasks/assign", methods=["POST"])
@role_required("admin")
def admin_assign_task():
    data = request.json or {}
    faculty_id = str(data.get("faculty_id") or "").strip()
    title = str(data.get("title") or "").strip()
    details = str(data.get("details") or "").strip()
    due_date = str(data.get("due_date") or "").strip()
    if not faculty_id or not title:
        return jsonify({"error": "faculty_id and title are required"}), 400
    task_id = create_task(faculty_id, title, details, due_date, session.get("username"))
    log_event("admin", session.get("username"), "assign_task", "faculty", faculty_id, {"task_id": task_id})
    fac = _get_faculty_by_id(faculty_id)
    push_notification("faculty", fac.get("username") if fac else None, "New Task Assigned", f"Task '{title}' assigned.")
    return jsonify({"message": "Task assigned", "task_id": task_id}), 201
