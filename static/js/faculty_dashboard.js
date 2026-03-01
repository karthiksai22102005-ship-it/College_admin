
let FACULTY_DATA = window.FACULTY_BOOTSTRAP || {};
let PLANNER_SESSION_STARTED_AT = Date.now();

const REQUIRED_PROFILE_FIELDS = ["name", "department", "username", "email", "phone", "designation"];
const PERSONAL_DOC_KEYS = ["aadhaar", "pan", "bank_passbook", "service_register", "joining_letter"];
const QUAL_DOC_KEYS = ["ssc_memo", "inter_memo", "btech_memo", "mtech_memo", "phd_memo"];

const MAX_PROFILE_PHOTO_BYTES = 3 * 1024 * 1024; // 3MB
const ALLOWED_PROFILE_PHOTO_EXT = new Set(["png", "jpg", "jpeg", "gif"]);
const ROLE_WORKSPACE = {
    HOD: {
        title: "Department-level authority enabled",
        actions: [
            "View all faculty in department",
            "Approve/reject leave requests",
            "Assign subjects and workload",
            "Modify department timetable",
            "Export department reports"
        ]
    },
    ASSOC_PROF: {
        title: "Associate Professor workspace",
        actions: [
            "Mark attendance",
            "Enter internal marks",
            "Upload study materials",
            "View own timetable",
            "Apply leave"
        ]
    },
    ASST_PROF: {
        title: "Assistant Professor workspace",
        actions: [
            "Mark attendance",
            "Enter marks",
            "Upload materials",
            "View timetable",
            "Apply leave"
        ]
    },
    STAFF: {
        title: "Non-teaching workspace",
        actions: [
            "View profile",
            "Apply leave",
            "View assigned tasks",
            "Upload documents"
        ]
    }
};
const ROLE_SIDEBAR = {
    HOD: ["Department Overview", "Faculty Management", "Subject Allocation", "Timetable Control", "Attendance Monitor", "Marks Oversight", "Leave Approvals", "Department Analytics", "Reports Export"],
    ASSOC_PROF: ["My Timetable", "Mark Attendance", "Internal Marks", "Study Materials", "Assigned Students", "My Workload", "Apply Leave", "Profile"],
    ASST_PROF: ["My Timetable", "Mark Attendance", "Enter Marks", "Upload Materials", "Apply Leave", "Profile"],
    STAFF: ["My Tasks", "Apply Leave", "Documents", "Profile"]
};
const SIDEBAR_NAV_TARGETS = {
    "Department Overview": "workloadCard",
    "Faculty Management": "roleWorkspaceCard",
    "Subject Allocation": "workloadCard",
    "Timetable Control": "workloadCard",
    "Attendance Monitor": "academicOpsCard",
    "Marks Oversight": "academicOpsCard",
    "Leave Approvals": "leaveCard",
    "Department Analytics": "notificationsCard",
    "Reports Export": "notificationsCard",
    "My Timetable": "workloadCard",
    "Mark Attendance": "academicOpsCard",
    "Internal Marks": "academicOpsCard",
    "Enter Marks": "academicOpsCard",
    "Study Materials": "materialsCard",
    "Upload Materials": "materialsCard",
    "Assigned Students": "workloadCard",
    "My Workload": "workloadCard",
    "Apply Leave": "leaveCard",
    "Profile": "roleWorkspaceCard",
    "My Tasks": "tasksCard",
    "Documents": "materialsCard"
};
let ERP_OVERVIEW = null;
const ROLE_FEATURES = {
    HOD: [
        { title: "Leave Approvals", desc: "Approve/reject department leave requests", target: "leaveCard", countKey: "pending_leave_approvals" },
        { title: "Subject Allocation", desc: "Track faculty subject assignments", target: "workloadCard", countKey: "assignments" },
        { title: "Attendance Monitor", desc: "Oversee attendance and marks flow", target: "academicOpsCard", countKey: "assignments" },
        { title: "Department Materials", desc: "Review uploaded study materials", target: "materialsCard", countKey: "materials" },
        { title: "Task Oversight", desc: "Follow assigned staff tasks", target: "tasksCard", countKey: "tasks" },
        { title: "Notifications", desc: "Watch critical department updates", target: "notificationsCard", countKey: "notifications" },
    ],
    ASSOC_PROF: [
        { title: "My Timetable", desc: "See your allocated subjects and sections", target: "workloadCard", countKey: "assignments" },
        { title: "Mark Attendance", desc: "Record class attendance", target: "academicOpsCard", countKey: "assignments" },
        { title: "Internal Marks", desc: "Submit evaluation marks", target: "academicOpsCard", countKey: "assignments" },
        { title: "Upload Materials", desc: "Share notes and references", target: "materialsCard", countKey: "materials" },
        { title: "Apply Leave", desc: "Create and track leave requests", target: "leaveCard", countKey: "leave_requests" },
        { title: "Notifications", desc: "Stay updated with alerts", target: "notificationsCard", countKey: "notifications" },
    ],
    ASST_PROF: [
        { title: "My Timetable", desc: "See your schedule", target: "workloadCard", countKey: "assignments" },
        { title: "Attendance", desc: "Mark attendance for classes", target: "academicOpsCard", countKey: "assignments" },
        { title: "Marks Entry", desc: "Enter marks for students", target: "academicOpsCard", countKey: "assignments" },
        { title: "Materials", desc: "Upload teaching materials", target: "materialsCard", countKey: "materials" },
        { title: "Leave", desc: "Apply leave", target: "leaveCard", countKey: "leave_requests" },
        { title: "Notifications", desc: "Track reminders and updates", target: "notificationsCard", countKey: "notifications" },
    ],
    STAFF: [
        { title: "Assigned Tasks", desc: "Track assigned tasks", target: "tasksCard", countKey: "tasks" },
        { title: "Leave", desc: "Apply leave and check status", target: "leaveCard", countKey: "leave_requests" },
        { title: "Documents", desc: "Upload required documents", target: "materialsCard", countKey: "materials" },
        { title: "Notifications", desc: "View latest updates", target: "notificationsCard", countKey: "notifications" },
    ],
};

function resolveRole() {
    const designation = String(FACULTY_DATA.designation || "").toUpperCase();
    if (designation.includes("HOD")) return "HOD";
    if (designation.includes("ASSOC")) return "ASSOC_PROF";
    if (designation.includes("ASST")) return "ASST_PROF";
    const explicit = String(FACULTY_DATA.normalized_role || FACULTY_DATA.role || "").toUpperCase().trim();
    if (explicit) return explicit;
    return "STAFF";
}

async function parseApiResponse(res) {
    const contentType = (res.headers.get("content-type") || "").toLowerCase();
    if (contentType.includes("application/json")) {
        return await res.json();
    }
    const text = await res.text();
    const normalized = (text || "").replace(/\s+/g, " ").trim();
    return { error: `${res.status} ${res.url || ""} ${normalized.slice(0, 180)}`.trim() };
}

function parsePermissions() {
    const raw = FACULTY_DATA.permissions_json;
    if (!raw) return [];
    if (typeof raw === "object") return raw.permissions || [];
    try {
        const obj = JSON.parse(raw);
        return obj.permissions || [];
    } catch (e) {
        return [];
    }
}

function hasPermission(permission) {
    const perms = parsePermissions();
    return perms.includes(permission);
}

function bindEnterAdvance(fieldIds, onLast) {
    const ids = Array.isArray(fieldIds) ? fieldIds : [];
    ids.forEach((id, idx) => {
        const el = document.getElementById(id);
        if (!el) return;
        el.addEventListener("keydown", (e) => {
            if (e.key !== "Enter" || e.shiftKey) return;
            if (el.tagName === "TEXTAREA") return;
            e.preventDefault();
            for (let i = idx + 1; i < ids.length; i += 1) {
                const next = document.getElementById(ids[i]);
                if (!next) continue;
                if (next.disabled || next.readOnly) continue;
                if (next.offsetParent === null) continue;
                next.focus();
                if (typeof next.select === "function") next.select();
                return;
            }
            if (idx === ids.length - 1 && typeof onLast === "function") onLast();
        });
    });
}

function _getFileExt(filename) {
    const name = (filename || "").toString();
    const idx = name.lastIndexOf(".");
    if (idx === -1) return "";
    return name.slice(idx + 1).toLowerCase();
}

function validateProfilePhotoFile(file) {
    if (!file) return { ok: false, message: "Please choose a photo file first" };
    const ext = _getFileExt(file.name);
    if (!ALLOWED_PROFILE_PHOTO_EXT.has(ext)) {
        return { ok: false, message: "Only PNG, JPG, JPEG, or GIF images are allowed" };
    }
    if (file.type && !file.type.toLowerCase().startsWith("image/")) {
        return { ok: false, message: "Selected file is not an image" };
    }
    if (file.size > MAX_PROFILE_PHOTO_BYTES) {
        return { ok: false, message: "Photo must be 3MB or smaller" };
    }
    return { ok: true, message: "" };
}

function showToast(message, isError = false) {
    const box = document.getElementById("toastContainer");
    if (!box) return;
    const item = document.createElement("div");
    item.className = `fd-toast${isError ? " error" : ""}`;
    item.textContent = message;
    box.appendChild(item);
    setTimeout(() => item.remove(), 3200);
}

function getPublicationText(pub) {
    if (typeof pub === "string") return pub;
    if (pub && typeof pub === "object") return pub.title || pub.details || pub.type || "-";
    return "-";
}

function renderPublications(publications, query = "") {
    const list = document.getElementById("publicationsList");
    if (!list) return;
    const normalizedQuery = query.trim().toLowerCase();
    const rows = Array.isArray(publications) ? publications : [];
    const filtered = normalizedQuery
        ? rows.filter((p) => getPublicationText(p).toLowerCase().includes(normalizedQuery))
        : rows;

    if (filtered.length === 0) {
        list.innerHTML = '<li class="fd-empty">No publications found</li>';
        return;
    }
    list.innerHTML = filtered.map((p) => `<li>${getPublicationText(p)}</li>`).join("");
}

function calculateProfileCompletion() {
    let total = REQUIRED_PROFILE_FIELDS.length;
    let done = 0;
    for (const key of REQUIRED_PROFILE_FIELDS) {
        if (String(FACULTY_DATA[key] || "").trim()) done += 1;
    }
    return Math.round((done / total) * 100);
}

function countUploadedDocs() {
    const personal = FACULTY_DATA.personal_documents || {};
    const qual = FACULTY_DATA.qualification_documents || {};
    const p = PERSONAL_DOC_KEYS.filter((k) => personal[k]).length;
    const q = QUAL_DOC_KEYS.filter((k) => qual[k]).length;
    return { uploaded: p + q, total: PERSONAL_DOC_KEYS.length + QUAL_DOC_KEYS.length };
}

function renderRoleWorkspace() {
    const badge = document.getElementById("facultyRoleBadge");
    const desc = document.getElementById("roleWorkspaceDescription");
    const list = document.getElementById("roleQuickActions");
    const role = resolveRole();
    const cfg = ROLE_WORKSPACE[role] || ROLE_WORKSPACE.STAFF;
    if (badge) badge.textContent = role;
    const headerRole = document.getElementById("facultyHeaderRole");
    if (headerRole) headerRole.textContent = role;
    if (desc) desc.textContent = cfg.title;
    if (list) {
        list.innerHTML = cfg.actions.map((a) => `<li>${a}</li>`).join("");
    }
    const body = document.body;
    if (body) body.classList.toggle("role-hod", role === "HOD");
}

function renderRoleSidebar() {
    const el = document.getElementById("roleSidebarMenu");
    if (!el) return;
    const role = resolveRole();
    const modules = ROLE_SIDEBAR[role] || ROLE_SIDEBAR.STAFF;
    el.innerHTML = modules.map((m) => {
        const card = SIDEBAR_NAV_TARGETS[m] || "roleWorkspaceCard";
        return `<li><button type="button" class="fd-link-btn" onclick="scrollToCard('${card}')">${m}</button></li>`;
    }).join("");
}

function scrollToCard(cardId) {
    const el = document.getElementById(cardId);
    if (!el) {
        showToast("Section not found", true);
        return;
    }
    // If hidden by previous permission state, reveal it so the Open action is visible.
    const style = window.getComputedStyle(el);
    if (style.display === "none") {
        el.style.display = "";
    }
    el.scrollIntoView({ behavior: "smooth", block: "start" });
    el.classList.add("fd-card-focus");
    setTimeout(() => el.classList.remove("fd-card-focus"), 900);
}

function renderQuickButtons() {
    const wrap = document.getElementById("roleQuickButtons");
    if (!wrap) return;
    const role = resolveRole();
    const btns = [];
    if (role === "HOD") {
        btns.push({ label: "Pending Approvals", card: "leaveCard" });
        btns.push({ label: "Workload", card: "workloadCard" });
        btns.push({ label: "Notifications", card: "notificationsCard" });
    } else if (role === "ASSOC_PROF" || role === "ASST_PROF") {
        btns.push({ label: "Attendance", card: "academicOpsCard" });
        btns.push({ label: "Marks", card: "academicOpsCard" });
        btns.push({ label: "Materials", card: "materialsCard" });
    } else {
        btns.push({ label: "Tasks", card: "tasksCard" });
        btns.push({ label: "Leave", card: "leaveCard" });
    }
    wrap.innerHTML = btns.map((b) => `<button class="fd-btn fd-btn-soft" type="button" onclick="scrollToCard('${b.card}')">${b.label}</button>`).join("");
}

function renderPriorityAlerts() {
    const el = document.getElementById("priorityAlertsList");
    if (!el) return;
    const role = resolveRole();
    const alerts = [];
    if (ERP_OVERVIEW) {
        const assignments = ERP_OVERVIEW.assignments || [];
        const pendingLeaves = ERP_OVERVIEW.pending_leave_approvals || [];
        const tasks = ERP_OVERVIEW.tasks || [];
        const materials = ERP_OVERVIEW.materials || [];
        if (role === "HOD" && pendingLeaves.length > 0) alerts.push(`${pendingLeaves.length} leave approvals pending`);
        if ((role === "ASSOC_PROF" || role === "ASST_PROF") && assignments.length === 0) alerts.push("No assignments mapped yet");
        if (role === "STAFF" && tasks.length === 0) alerts.push("No active tasks assigned");
        if (hasPermission("upload_study_materials") && materials.length === 0) alerts.push("No study materials uploaded yet");
    }
    if (!alerts.length) alerts.push("All priority items are up to date");
    el.innerHTML = alerts.map((a) => `<li>${a}</li>`).join("");
}

function getFeatureCount(countKey) {
    if (countKey === "notifications") {
        const list = document.querySelectorAll("#facultyNotificationsList .fd-notice-card, #facultyNotificationsList .fd-note");
        return list ? list.length : 0;
    }
    if (!ERP_OVERVIEW) return 0;
    const rows = ERP_OVERVIEW[countKey] || [];
    return Array.isArray(rows) ? rows.length : 0;
}

function renderRoleFeatureCards() {
    const wrap = document.getElementById("roleFeatureCards");
    if (!wrap) return;
    const role = resolveRole();
    const features = ROLE_FEATURES[role] || ROLE_FEATURES.STAFF;
    wrap.innerHTML = features.map((f) => `
        <article class="fd-feature-card">
            <div class="fd-feature-head">
                <div class="fd-feature-title">${f.title}</div>
                <span class="fd-feature-count">${getFeatureCount(f.countKey)}</span>
            </div>
            <div class="fd-feature-desc">${f.desc}</div>
            <button class="fd-btn fd-btn-soft" type="button" onclick="scrollToCard('${f.target}')">Open</button>
        </article>
    `).join("");
}

function renderRoleModuleVisibility() {
    const leaveCard = document.getElementById("leaveCard");
    const academicOps = document.getElementById("academicOpsCard");
    const materialsCard = document.getElementById("materialsCard");
    const tasksCard = document.getElementById("tasksCard");
    const hodWrap = document.getElementById("hodLeaveApprovalWrap");
    const publicationCard = document.getElementById("publicationCard");
    const hodControlsCard = document.getElementById("hodControlsCard");
    const role = resolveRole();

    // Keep core role modules visible so dashboard cards/open buttons always work.
    if (leaveCard) leaveCard.style.display = "";
    if (academicOps) academicOps.style.display = role === "STAFF" ? "none" : "";
    if (materialsCard) materialsCard.style.display = "";
    if (tasksCard) tasksCard.style.display = "";
    if (hodWrap) hodWrap.style.display = role === "HOD" ? "" : "none";
    if (publicationCard) publicationCard.style.display = "";
    if (hodControlsCard) hodControlsCard.style.display = role === "HOD" ? "" : "none";
}

function renderHodControls() {
    const role = resolveRole();
    if (role !== "HOD") return;
    const pending = (ERP_OVERVIEW?.pending_leave_approvals || []).length;
    const assignments = (ERP_OVERVIEW?.assignments || []).length;
    const materials = (ERP_OVERVIEW?.materials || []).length;
    const p = document.getElementById("hodPendingCount");
    const a = document.getElementById("hodAssignCount");
    const m = document.getElementById("hodMaterialCount");
    if (p) p.textContent = String(pending);
    if (a) a.textContent = String(assignments);
    if (m) m.textContent = String(materials);
}

function notifyHodFeature(featureName) {
    showToast(`${featureName} can be enabled by admin workflow settings.`);
}

function renderAssignmentList(assignments) {
    const el = document.getElementById("assignmentList");
    if (!el) return;
    const rows = Array.isArray(assignments) ? assignments : [];
    if (!rows.length) {
        el.innerHTML = '<li class="fd-empty">No assignments yet</li>';
        return;
    }
    el.innerHTML = rows.map((a) => `<li><strong>${a.subject}</strong> - ${a.section_name} (${a.academic_year || "-"})</li>`).join("");
}

function renderMyLeaves(leaves) {
    const el = document.getElementById("myLeaveList");
    if (!el) return;
    const rows = Array.isArray(leaves) ? leaves : [];
    if (!rows.length) {
        el.innerHTML = '<li class="fd-empty">No leave records</li>';
        return;
    }
    el.innerHTML = rows.map((l) => `<li>${l.from_date} to ${l.to_date} - <strong>${l.status}</strong></li>`).join("");
}

function renderPendingApprovals(rows) {
    const el = document.getElementById("hodPendingLeaveList");
    if (!el) return;
    const list = Array.isArray(rows) ? rows : [];
    if (!list.length) {
        el.innerHTML = '<li class="fd-empty">No pending approvals</li>';
        return;
    }
    el.innerHTML = list.map((l) => `
        <li>
            <div><strong>${l.faculty_id}</strong>: ${l.from_date} to ${l.to_date}</div>
            <div>${l.reason || ""}</div>
            <div class="fd-actions">
                <button class="fd-btn fd-btn-soft" type="button" onclick="decideLeave('${l.leave_id}', 'APPROVED')">Approve</button>
                <button class="fd-btn fd-btn-danger" type="button" onclick="decideLeave('${l.leave_id}', 'REJECTED')">Reject</button>
            </div>
        </li>
    `).join("");
}

function renderMaterials(rows) {
    const el = document.getElementById("materialList");
    if (!el) return;
    const list = Array.isArray(rows) ? rows : [];
    if (!list.length) {
        el.innerHTML = '<li class="fd-empty">No materials uploaded</li>';
        return;
    }
    el.innerHTML = list.map((m) => {
        const file = m.file_path ? `<a href="${m.file_path}" target="_blank" rel="noopener">Open file</a>` : "No file";
        return `<li><strong>${m.title}</strong> (${m.subject || "-"}) - ${file}</li>`;
    }).join("");
}

function renderTasks(rows) {
    const el = document.getElementById("taskList");
    if (!el) return;
    const list = Array.isArray(rows) ? rows : [];
    if (!list.length) {
        el.innerHTML = '<li class="fd-empty">No assigned tasks</li>';
        return;
    }
    el.innerHTML = list.map((t) => `<li><strong>${t.title}</strong> - ${t.status}${t.due_date ? ` (Due: ${t.due_date})` : ""}</li>`).join("");
}

async function loadErpOverview() {
    try {
        const res = await fetch("/api/erp/me/overview", { credentials: "include" });
        const data = await parseApiResponse(res);
        if (!res.ok) throw new Error(data.error || "ERP overview failed");
        ERP_OVERVIEW = data || {};
        renderAssignmentList(data.assignments || []);
        renderMyLeaves(data.leave_requests || []);
        renderPendingApprovals(data.pending_leave_approvals || []);
        renderMaterials(data.materials || []);
        renderTasks(data.tasks || []);
        renderPriorityAlerts();
        renderHodControls();
        renderRoleFeatureCards();
    } catch (e) {
        showToast(e.message, true);
    }
}

async function submitLeaveApply(event) {
    event.preventDefault();
    const payload = {
        from_date: document.getElementById("leaveFromDate")?.value || "",
        to_date: document.getElementById("leaveToDate")?.value || "",
        reason: (document.getElementById("leaveReason")?.value || "").trim(),
    };
    try {
        const res = await fetch("/api/erp/leave/apply", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            credentials: "include",
            body: JSON.stringify(payload),
        });
        const data = await parseApiResponse(res);
        if (!res.ok) throw new Error(data.error || "Leave apply failed");
        showToast("Leave request submitted");
        loadErpOverview();
    } catch (e) {
        showToast(e.message, true);
    }
}

async function decideLeave(leaveId, decision) {
    try {
        const res = await fetch(`/api/erp/leave/${encodeURIComponent(leaveId)}/decision`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            credentials: "include",
            body: JSON.stringify({ decision }),
        });
        const data = await parseApiResponse(res);
        if (!res.ok) throw new Error(data.error || "Decision failed");
        showToast(data.message || "Updated");
        loadErpOverview();
    } catch (e) {
        showToast(e.message, true);
    }
}

async function submitAttendance(event) {
    event.preventDefault();
    const payload = {
        subject: (document.getElementById("attSubject")?.value || "").trim(),
        section_name: (document.getElementById("attSection")?.value || "").trim(),
        entry_date: document.getElementById("attDate")?.value || "",
        period_name: (document.getElementById("attPeriod")?.value || "").trim(),
        status: "PRESENT",
    };
    try {
        const res = await fetch("/api/erp/attendance/mark", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            credentials: "include",
            body: JSON.stringify(payload),
        });
        const data = await parseApiResponse(res);
        if (!res.ok) throw new Error(data.error || "Attendance failed");
        showToast("Attendance marked");
    } catch (e) {
        showToast(e.message, true);
    }
}

async function submitMarks(event) {
    event.preventDefault();
    const payload = {
        student_roll_no: (document.getElementById("markRollNo")?.value || "").trim(),
        subject: (document.getElementById("markSubject")?.value || "").trim(),
        exam_type: (document.getElementById("markExamType")?.value || "").trim(),
        marks_obtained: Number(document.getElementById("markObtained")?.value || 0),
        max_marks: Number(document.getElementById("markMax")?.value || 0),
    };
    try {
        const res = await fetch("/api/erp/marks/enter", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            credentials: "include",
            body: JSON.stringify(payload),
        });
        const data = await parseApiResponse(res);
        if (!res.ok) throw new Error(data.error || "Marks save failed");
        showToast("Marks saved");
    } catch (e) {
        showToast(e.message, true);
    }
}

async function submitMaterialUpload(event) {
    event.preventDefault();
    const formData = new FormData();
    formData.append("title", (document.getElementById("materialTitle")?.value || "").trim());
    formData.append("description", (document.getElementById("materialDescription")?.value || "").trim());
    formData.append("subject", (document.getElementById("materialSubject")?.value || "").trim());
    formData.append("section_name", (document.getElementById("materialSection")?.value || "").trim());
    formData.append("academic_year", (document.getElementById("materialAcademicYear")?.value || "").trim());
    const file = document.getElementById("materialFile")?.files?.[0];
    if (file) formData.append("file", file);
    try {
        const res = await fetch("/api/erp/materials/upload", {
            method: "POST",
            body: formData,
            credentials: "include",
        });
        const data = await parseApiResponse(res);
        if (!res.ok) throw new Error(data.error || "Material upload failed");
        showToast("Material uploaded");
        loadErpOverview();
    } catch (e) {
        showToast(e.message, true);
    }
}

function renderKpis() {
    const completion = calculateProfileCompletion();
    const docs = countUploadedDocs();
    const pubs = Array.isArray(FACULTY_DATA.publications) ? FACULTY_DATA.publications.length : 0;

    const profileEl = document.getElementById("kpiProfileCompletion");
    const docsEl = document.getElementById("kpiDocumentsUploaded");
    const pubsEl = document.getElementById("kpiPublications");
    const loginEl = document.getElementById("kpiLastLogin");

    if (profileEl) profileEl.textContent = `${completion}%`;
    if (docsEl) docsEl.textContent = `${docs.uploaded} / ${docs.total}`;
    if (pubsEl) pubsEl.textContent = String(pubs);
    if (loginEl) loginEl.textContent = FACULTY_DATA.last_login || "-";
    renderRoleWorkspace();
    renderRoleSidebar();
    renderQuickButtons();
    renderRoleFeatureCards();
}

function renderDocumentStatus() {
    const grid = document.getElementById("documentStatusGrid");
    if (!grid) return;
    const personal = FACULTY_DATA.personal_documents || {};
    const qual = FACULTY_DATA.qualification_documents || {};
    const rows = [
        ...PERSONAL_DOC_KEYS.map((k) => ({ category: "personal", type: k, label: `Personal: ${k.replace("_", " ")}`, path: personal[k] })),
        ...QUAL_DOC_KEYS.map((k) => ({ category: "qualification", type: k, label: `Qualification: ${k.replace("_", " ")}`, path: qual[k] })),
        ...(personal.others || []).map((p, idx) => ({ category: "personal", type: "others", label: `Personal: others #${idx + 1}`, path: p })),
        ...(qual.others || []).map((p, idx) => ({ category: "qualification", type: "others", label: `Qualification: others #${idx + 1}`, path: p })),
    ];

    grid.innerHTML = rows.map((row) => {
        if (!row.path) {
            return `<article class="fd-doc-item"><h4>${row.label}</h4><span class="fd-empty">Not uploaded</span></article>`;
        }
        return `
            <article class="fd-doc-item">
                <h4>${row.label}</h4>
                <a class="fd-doc-link" href="${row.path}" target="_blank" rel="noopener">Open document</a>
            </article>
        `;
    }).join("");
}

async function loadFacultyNotifications() {
    const el = document.getElementById("facultyNotificationsList");
    const unreadOnly = document.getElementById("notificationsUnreadOnly")?.checked;
    if (!el) return;
    try {
        const suffix = unreadOnly ? "?unread=1" : "";
        const res = await fetch(`/faculty-notifications${suffix}`, { credentials: "include" });
        const data = await parseApiResponse(res);
        if (!res.ok) throw new Error(data.message || "Failed to load notifications");
        const list = data.notifications || [];
        if (!list.length) {
            el.innerHTML = '<li class="fd-empty">No notifications</li>';
            renderRoleFeatureCards();
            return;
        }
        el.innerHTML = list.map((n) => {
            const title = (n.title || "Notification").toString();
            const message = (n.message || "").toString();
            const created = (n.created_at || "").toString();
            const unread = !n.is_read;
            const id = (n.notification_id || "").toString();

            return `
                <li class="fd-notice-card ${unread ? "unread" : ""}">
                    <div class="fd-notice-meta">
                        <div class="fd-notice-title">${title} ${unread ? '<span class="fd-note-badge">Unread</span>' : ""}</div>
                        <time class="fd-notice-time" datetime="${created}">${created}</time>
                    </div>
                    ${message ? `<div class="fd-notice-msg">${message}</div>` : ""}
                    <div class="fd-note-actions">
                        ${unread && id ? `<button class="fd-btn fd-btn-soft fd-note-btn" type="button" onclick="markFacultyNotificationRead('${id.replace(/'/g, "\\'")}')">Mark read</button>` : ""}
                    </div>
                </li>
            `;
        }).join("");
        renderRoleFeatureCards();
    } catch (e) {
        el.innerHTML = `<li class="fd-empty">${e.message}</li>`;
        renderRoleFeatureCards();
    }
}

async function markFacultyNotificationRead(notificationId) {
    try {
        const res = await fetch(`/faculty-notifications/${encodeURIComponent(notificationId)}/read`, {
            method: "PUT",
            credentials: "include"
        });
        const data = await parseApiResponse(res);
        if (!res.ok) throw new Error(data.message || "Failed");
        loadFacultyNotifications();
    } catch (e) {
        showToast(e.message, true);
    }
}

async function logoutFaculty() {
    try {
        await fetch("/auth/logout", { method: "POST", credentials: "include" });
    } catch (e) {}
    window.location.href = "/login";
}

async function stopAdminImpersonation() {
    try {
        const res = await fetch("/admin/impersonation/stop", { method: "POST", credentials: "include" });
        if (!res.ok) throw new Error("Failed to stop impersonation");
    } catch (e) {}
    window.location.href = "/admin-dashboard";
}

async function refreshDashboardData() {
    try {
        const res = await fetch("/faculty-me", { credentials: "include" });
        const data = await parseApiResponse(res);
        if (!res.ok) throw new Error(data.error || "Failed to refresh");
        FACULTY_DATA = data;
        renderKpis();
        renderDocumentStatus();
        renderRoleWorkspace();
        renderRoleModuleVisibility();
        renderPublications(FACULTY_DATA.publications || [], document.getElementById("publicationSearch")?.value || "");
        loadErpOverview();
        showToast("Dashboard refreshed");
    } catch (e) {
        showToast(e.message, true);
    }
}

async function submitProfileUpdate(event) {
    event.preventDefault();

    const rawPhone = (document.getElementById("facultyPhone")?.value || "").trim();
    const normalizedPhone = rawPhone.replace(/[^\d]/g, "");
    if (rawPhone && (normalizedPhone.length < 10 || normalizedPhone.length > 15)) {
        showToast("Phone number must be 10 to 15 digits", true);
        return;
    }

    const payload = {
        email: (document.getElementById("facultyEmail")?.value || "").trim(),
        phone: normalizedPhone,
    };

    try {
        const fd = new FormData();
        fd.append("email", payload.email || "");
        fd.append("phone", payload.phone || "");
        fd.append("designation", FACULTY_DATA.designation || "");
        const res = await fetch("/update-faculty-profile", {
            method: "POST",
            body: fd,
            credentials: "include"
        });
        const data = await parseApiResponse(res);
        if (!res.ok) {
            showToast(data.message || data.error || "Profile update failed", true);
            return;
        }

        FACULTY_DATA = { ...FACULTY_DATA, ...(data.faculty || {}) };
        document.getElementById("facultyDesignationHeader").textContent = FACULTY_DATA.designation || "-";
        renderKpis();
        showToast("Profile updated successfully");
    } catch (err) {
        showToast(err.message || "Profile update failed", true);
    }
}

async function submitPasswordChange(event) {
    event.preventDefault();

    const currentPassword = (document.getElementById("currentPassword")?.value || "").trim();
    const newPassword = (document.getElementById("newPassword")?.value || "").trim();
    const passwordRegex = /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9]).{8,}$/;
    if (!passwordRegex.test(newPassword)) {
        showToast("New password must match the required format", true);
        return;
    }

    const formData = new FormData();
    formData.append("current_password", currentPassword);
    formData.append("new_password", newPassword);

    try {
        const res = await fetch("/faculty-change-password", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                current_password: currentPassword,
                new_password: newPassword
            }),
            credentials: "include"
        });
        const data = await parseApiResponse(res);
        if (!res.ok) {
            showToast(data.message || data.error || "Password change failed", true);
            return;
        }

        document.getElementById("currentPassword").value = "";
        document.getElementById("newPassword").value = "";
        showToast("Password updated successfully");
    } catch (err) {
        showToast(err.message || "Password change failed", true);
    }
}

async function uploadProfilePhoto() {
    const fileInput = document.getElementById("facultyPhotoInput");
    const file = fileInput?.files?.[0];
    const verdict = validateProfilePhotoFile(file);
    if (!verdict.ok) {
        showToast(verdict.message, true);
        return;
    }

    const formData = new FormData();
    formData.append("photo", file);

    try {
        const res = await fetch("/faculty-upload-photo", {
            method: "POST",
            body: formData,
            credentials: "include"
        });
        const data = await parseApiResponse(res);
        if (!res.ok) {
            showToast(data.message || data.error || "Photo upload failed", true);
            return;
        }

        if (data.photo) {
            FACULTY_DATA.photo = data.photo;
            document.getElementById("facultyPhotoPreview").src = data.photo;
        }
        fileInput.value = "";
        showToast("Photo uploaded successfully");
    } catch (err) {
        showToast(err.message || "Photo upload failed", true);
    }
}

async function removeProfilePhoto() {
    if (!confirm("Remove current profile photo?")) return;

    try {
        const res = await fetch("/faculty-remove-photo", {
            method: "DELETE",
            credentials: "include"
        });
        const data = await parseApiResponse(res);
        if (!res.ok) {
            showToast(data.message || data.error || "Photo remove failed", true);
            return;
        }

        FACULTY_DATA.photo = "";
        document.getElementById("facultyPhotoPreview").src = "/static/default-user.png";
        document.getElementById("facultyPhotoInput").value = "";
        showToast("Photo removed successfully");
    } catch (err) {
        showToast(err.message || "Photo remove failed", true);
    }
}

async function submitPublication(event) {
    event.preventDefault();

    const publicationInput = document.getElementById("publicationInput");
    const publicationText = (publicationInput?.value || "").trim();
    if (!publicationText) {
        showToast("Please enter publication text", true);
        return;
    }

    const formData = new FormData();
    formData.append("publication", publicationText);

    try {
        const res = await fetch("/faculty-publications", {
            method: "POST",
            body: formData,
            credentials: "include"
        });
        const data = await parseApiResponse(res);
        if (!res.ok) {
            showToast(data.message || data.error || "Could not add publication", true);
            return;
        }

        FACULTY_DATA.publications = data.publications || [];
        renderPublications(FACULTY_DATA.publications, document.getElementById("publicationSearch")?.value || "");
        renderKpis();
        publicationInput.value = "";
        localStorage.removeItem("faculty_pub_draft");
        showToast("Publication added");
    } catch (err) {
        showToast(err.message || "Could not add publication", true);
    }
}

function setupDraftAutosave() {
    const input = document.getElementById("publicationInput");
    if (!input) return;
    input.value = localStorage.getItem("faculty_pub_draft") || "";
    input.addEventListener("input", () => {
        localStorage.setItem("faculty_pub_draft", input.value);
    });
}

function setupPasswordVisibilityToggles() {
    const buttons = document.querySelectorAll(".fd-password-toggle");
    buttons.forEach((btn) => {
        btn.addEventListener("click", () => {
            const targetId = btn.getAttribute("data-target");
            const input = document.getElementById(targetId);
            if (!input) return;
            const hidden = input.type === "password";
            input.type = hidden ? "text" : "password";
            btn.setAttribute("aria-label", hidden ? "Hide password" : "Show password");
        });
    });
}

function openPhotoLightbox(src) {
    const box = document.getElementById("photoLightbox");
    const img = document.getElementById("photoLightboxImg");
    if (!box || !img) return;
    if (!src) return;
    img.src = src;
    box.classList.add("is-open");
    box.setAttribute("aria-hidden", "false");
    document.body.style.overflow = "hidden";
}

function closePhotoLightbox() {
    const box = document.getElementById("photoLightbox");
    const img = document.getElementById("photoLightboxImg");
    if (!box || !img) return;
    box.classList.remove("is-open");
    box.setAttribute("aria-hidden", "true");
    img.removeAttribute("src");
    document.body.style.overflow = "";
}

function initDailyPlanner() {
    const dateEl = document.getElementById("plannerTodayDate");
    const clockEl = document.getElementById("plannerSessionClock");
    const checklistWrap = document.getElementById("plannerChecklist");
    if (!checklistWrap) return;

    const now = new Date();
    const dateKey = now.toISOString().slice(0, 10);
    if (dateEl) {
        dateEl.textContent = now.toLocaleDateString(undefined, {
            weekday: "short",
            day: "2-digit",
            month: "short",
            year: "numeric",
        });
    }

    const plannerStorageKey = `faculty_planner_${FACULTY_DATA.username || "user"}_${dateKey}`;
    let saved = {};
    try {
        saved = JSON.parse(localStorage.getItem(plannerStorageKey) || "{}");
    } catch (e) {
        saved = {};
    }

    checklistWrap.querySelectorAll("input[type='checkbox'][data-item]").forEach((cb) => {
        const item = cb.getAttribute("data-item");
        cb.checked = !!saved[item];
        cb.addEventListener("change", () => {
            saved[item] = cb.checked;
            localStorage.setItem(plannerStorageKey, JSON.stringify(saved));
        });
    });

    const tick = () => {
        if (!clockEl) return;
        const secs = Math.max(0, Math.floor((Date.now() - PLANNER_SESSION_STARTED_AT) / 1000));
        const mm = String(Math.floor(secs / 60)).padStart(2, "0");
        const ss = String(secs % 60).padStart(2, "0");
        clockEl.textContent = `${mm}:${ss}`;
    };
    tick();
    setInterval(tick, 1000);
}

document.addEventListener("DOMContentLoaded", () => {
    renderKpis();
    renderDocumentStatus();
    renderPublications(FACULTY_DATA.publications || []);
    loadFacultyNotifications();
    setupDraftAutosave();
    setupPasswordVisibilityToggles();

    const profileForm = document.getElementById("facultyProfileForm");
    const passwordForm = document.getElementById("facultyPasswordForm");
    const publicationForm = document.getElementById("publicationForm");
    const photoButton = document.getElementById("uploadPhotoBtn");
    const removePhotoButton = document.getElementById("removePhotoBtn");
    const photoInput = document.getElementById("facultyPhotoInput");
    const photoPreview = document.getElementById("facultyPhotoPreview");
    const refreshBtn = document.getElementById("refreshDashboardBtn");
    const refreshNotificationsBtn = document.getElementById("refreshNotificationsBtn");
    const unreadOnly = document.getElementById("notificationsUnreadOnly");
    const publicationSearch = document.getElementById("publicationSearch");
    const leaveApplyForm = document.getElementById("leaveApplyForm");
    const attendanceForm = document.getElementById("attendanceForm");
    const marksForm = document.getElementById("marksForm");
    const materialUploadForm = document.getElementById("materialUploadForm");

    if (profileForm) profileForm.addEventListener("submit", submitProfileUpdate);
    if (passwordForm) passwordForm.addEventListener("submit", submitPasswordChange);
    if (publicationForm) publicationForm.addEventListener("submit", submitPublication);
    if (photoButton) photoButton.addEventListener("click", uploadProfilePhoto);
    if (removePhotoButton) removePhotoButton.addEventListener("click", removeProfilePhoto);
    if (photoInput) {
        photoInput.addEventListener("change", () => {
            const file = photoInput.files?.[0];
            if (!file) return;
            const verdict = validateProfilePhotoFile(file);
            if (!verdict.ok) {
                showToast(verdict.message, true);
                photoInput.value = "";
                return;
            }

            const img = document.getElementById("facultyPhotoPreview");
            if (!img) return;
            const url = URL.createObjectURL(file);
            img.src = url;
            img.onload = () => URL.revokeObjectURL(url);
        });
    }
    if (photoPreview) {
        photoPreview.addEventListener("click", () => {
            const src = photoPreview.getAttribute("src") || "";
            openPhotoLightbox(src);
        });
        photoPreview.setAttribute("title", "Click to enlarge");
    }

    const lb = document.getElementById("photoLightbox");
    if (lb) {
        lb.addEventListener("click", (e) => {
            const t = e.target;
            if (t && t.closest && t.closest("[data-close='1']")) closePhotoLightbox();
        });
    }
    document.addEventListener("keydown", (e) => {
        if (e.key === "Escape") closePhotoLightbox();
    });
    if (refreshBtn) refreshBtn.addEventListener("click", refreshDashboardData);
    if (refreshNotificationsBtn) refreshNotificationsBtn.addEventListener("click", loadFacultyNotifications);
    if (unreadOnly) unreadOnly.addEventListener("change", loadFacultyNotifications);
    if (publicationSearch) {
        publicationSearch.addEventListener("input", () => {
            renderPublications(FACULTY_DATA.publications || [], publicationSearch.value);
        });
    }
    if (leaveApplyForm) leaveApplyForm.addEventListener("submit", submitLeaveApply);
    if (attendanceForm) attendanceForm.addEventListener("submit", submitAttendance);
    if (marksForm) marksForm.addEventListener("submit", submitMarks);
    if (materialUploadForm) materialUploadForm.addEventListener("submit", submitMaterialUpload);

    renderRoleModuleVisibility();
    renderRoleSidebar();
    renderQuickButtons();
    renderPriorityAlerts();
    loadErpOverview();
    initDailyPlanner();

    bindEnterAdvance(
        ["facultyEmail", "facultyPhone"],
        () => profileForm?.requestSubmit()
    );
    bindEnterAdvance(
        ["currentPassword", "newPassword"],
        () => passwordForm?.requestSubmit()
    );
});
