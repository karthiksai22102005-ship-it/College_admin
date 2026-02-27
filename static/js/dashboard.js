// ======================================================
// GLOBAL STATE
// ======================================================
let CURRENT_DEPARTMENT = null;
let CURRENT_FACULTY_ID = null;
let CURRENT_ROLE = "admin";
let CURRENT_FACULTY_DATA = null;
let ALL_DEPARTMENTS = [];
let IS_PROFILE_EDIT_MODE = false;
let TEMP_QUALIFICATIONS = [];
let TEMP_PUBLICATIONS = [];
let TEMP_SUBJECT_EXPERTISE = [];
let ALL_FACULTY_LIST = []; // For shared faculty lists
let CURRENT_FACULTY_LIST = []; // For the department-specific view
let CURRENT_DEPARTMENT_VIEW = null;
let CURRENT_EXPERTISE_FACULTY = null;
let CURRENT_EXPERTISE_CERTS = [];
let CURRENT_EXPERTISE_SUBJECTS = [];
let CURRENT_CREATE_DEPARTMENT = "";
let CURRENT_CREATE_DEPARTMENT_LOCKED = false;
let PROFILE_RETURN_CONTEXT = null;
let IS_HISTORY_RESTORE = false;
let NAV_INDEX = 0;
let LAST_ADMIN_SYNC_TS = 0;

function hasValidFacultyId(facultyId) {
    const id = String(facultyId || "").trim();
    return id.length > 0;
}

async function parseApiResponse(res) {
    const contentType = (res.headers.get("content-type") || "").toLowerCase();
    if (contentType.includes("application/json")) {
        return await res.json();
    }
    const text = await res.text();
    const oneLine = (text || "").replace(/\s+/g, " ").trim();
    throw new Error(`${res.status} ${res.url || ""} ${oneLine.slice(0, 180)}`.trim());
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

// ======================================================
// SECTION CONTROL & NAVIGATION
// ======================================================
function showSection(id, show) {
    document.getElementById(id)?.classList.toggle("hidden", !show);
}

function withCacheBust(url) {
    const raw = (url || "").toString().trim();
    if (!raw || raw.startsWith("data:")) return raw;
    const sep = raw.includes("?") ? "&" : "?";
    return `${raw}${sep}v=${LAST_ADMIN_SYNC_TS || Date.now()}`;
}

function getActiveSectionId() {
    return document.querySelector(".page-section.active")?.id || "mainDashboard";
}

function getAppNavState() {
    const researchDetailOpen = !document.getElementById("researchDetailView")?.classList.contains("hidden");
    return {
        appNav: true,
        navIndex: NAV_INDEX,
        sectionId: getActiveSectionId(),
        deptSearch: document.getElementById("deptSearch")?.value || "",
        facultySearch: document.getElementById("facultySearch")?.value || "",
        personalSearch: document.getElementById("personalFacultySearch")?.value || "",
        researchSearch: document.getElementById("researchFacultySearch")?.value || "",
        expertiseSearch: document.getElementById("expertiseFacultySearch")?.value || "",
        departmentViewCode: CURRENT_DEPARTMENT_VIEW?.department_code || CURRENT_DEPARTMENT || "",
        profileFacultyId: CURRENT_FACULTY_ID || "",
        profileEdit: !!IS_PROFILE_EDIT_MODE,
        researchDetailOpen: !!researchDetailOpen,
    };
}

function pushAppNavState(replace = false) {
    if (IS_HISTORY_RESTORE) return;
    if (replace) {
        const state = getAppNavState();
        state.navIndex = NAV_INDEX;
        window.history.replaceState(state, "");
        return;
    }
    NAV_INDEX += 1;
    const state = getAppNavState();
    state.navIndex = NAV_INDEX;
    window.history.pushState(state, "");
}

async function restoreFromHistoryState(state) {
    if (!state || !state.appNav) return;
    IS_HISTORY_RESTORE = true;
    NAV_INDEX = Number.isFinite(state.navIndex) ? state.navIndex : 0;

    try {
        const sectionId = state.sectionId || "mainDashboard";
        if (sectionId === "mainDashboard") {
            goHome(false);
            return;
        }
        if (sectionId === "departmentsSection") {
            openDepartments(false);
            if (state.departmentViewCode) {
                await openFacultyForDept(state.departmentViewCode, false);
                const fInput = document.getElementById("facultySearch");
                if (fInput) fInput.value = state.facultySearch || "";
                if (CURRENT_DEPARTMENT_VIEW) renderDepartmentFaculty(CURRENT_DEPARTMENT_VIEW, state.facultySearch || "");
            } else {
                const dInput = document.getElementById("deptSearch");
                if (dInput) dInput.value = state.deptSearch || "";
                filterDepartments();
            }
            return;
        }
        if (sectionId === "personalSection") {
            await openPersonal(false);
            const pInput = document.getElementById("personalFacultySearch");
            if (pInput) pInput.value = state.personalSearch || "";
            filterPersonalFaculty();
            return;
        }
        if (sectionId === "researchSection") {
            openResearch(false);
            const rInput = document.getElementById("researchFacultySearch");
            if (rInput) rInput.value = state.researchSearch || "";
            filterResearchFaculty();
            if (state.researchDetailOpen && state.profileFacultyId) {
                const facName = ALL_FACULTY_LIST.find(f => f.faculty_id === state.profileFacultyId)?.name || "";
                await openResearchDetail(state.profileFacultyId, facName, false);
            }
            return;
        }
        if (sectionId === "expertiseSection") {
            await openExpertise(false);
            const eInput = document.getElementById("expertiseFacultySearch");
            if (eInput) eInput.value = state.expertiseSearch || "";
            filterExpertiseFaculty();
            return;
        }
        if (sectionId === "insightsSection") {
            await openInsights(false);
            return;
        }
        if (sectionId === "profileSection" && state.profileFacultyId) {
            await openFacultyProfile(state.profileFacultyId, !!state.profileEdit, null, false);
            return;
        }
        goHome(false);
    } finally {
        IS_HISTORY_RESTORE = false;
    }
}

function goHome(recordHistory = true){
    document.querySelectorAll(".page-section.active").forEach(sec => sec.classList.remove("active"));
    document.getElementById("mainDashboard")?.classList.add("active");
    PROFILE_RETURN_CONTEXT = null;
    if (recordHistory) pushAppNavState(false);
}

function navigateBack(fallbackFn) {
    if (NAV_INDEX > 0) {
        window.history.back();
        return;
    }
    if (typeof fallbackFn === "function") fallbackFn();
}

function captureProfileReturnContext(source = null) {
    const activeSection = source || document.querySelector(".page-section.active")?.id || "departmentsSection";
    PROFILE_RETURN_CONTEXT = {
        sectionId: activeSection,
        scrollY: window.scrollY || 0,
        deptSearch: document.getElementById("deptSearch")?.value || "",
        facultySearch: document.getElementById("facultySearch")?.value || "",
        personalSearch: document.getElementById("personalFacultySearch")?.value || "",
        researchSearch: document.getElementById("researchFacultySearch")?.value || "",
        expertiseSearch: document.getElementById("expertiseFacultySearch")?.value || "",
    };
}

async function restoreProfileReturnContext() {
    const ctx = PROFILE_RETURN_CONTEXT;
    PROFILE_RETURN_CONTEXT = null;
    if (!ctx || !ctx.sectionId) {
        document.querySelectorAll(".page-section.active").forEach(sec => sec.classList.remove("active"));
        document.getElementById("departmentsSection")?.classList.add("active");
        return;
    }

    if (ctx.sectionId === "personalSection") {
        await openPersonal();
        const input = document.getElementById("personalFacultySearch");
        if (input) input.value = ctx.personalSearch || "";
        filterPersonalFaculty();
    } else if (ctx.sectionId === "researchSection") {
        openResearch();
        setTimeout(() => {
            const input = document.getElementById("researchFacultySearch");
            if (input) input.value = ctx.researchSearch || "";
            filterResearchFaculty();
        }, 150);
    } else if (ctx.sectionId === "expertiseSection") {
        await openExpertise();
        const input = document.getElementById("expertiseFacultySearch");
        if (input) input.value = ctx.expertiseSearch || "";
        filterExpertiseFaculty();
    } else {
        document.querySelectorAll(".page-section.active").forEach(sec => sec.classList.remove("active"));
        document.getElementById("departmentsSection")?.classList.add("active");
        if (ctx.deptSearch && document.getElementById("deptSearch")) {
            document.getElementById("deptSearch").value = ctx.deptSearch;
            filterDepartments();
        } else if (CURRENT_DEPARTMENT_VIEW) {
            renderDepartmentFaculty(CURRENT_DEPARTMENT_VIEW, ctx.facultySearch || "");
            const fInput = document.getElementById("facultySearch");
            if (fInput) fInput.value = ctx.facultySearch || "";
        }
    }

    setTimeout(() => window.scrollTo({ top: ctx.scrollY || 0, behavior: "auto" }), 50);
}

// ======================================================
// MAIN MENU BUTTONS
// ======================================================
function openDepartments(recordHistory = true){
    document.querySelectorAll(".page-section.active").forEach(sec => sec.classList.remove("active"));
    document.getElementById("departmentsSection")?.classList.add("active");
    loadDepartments();
    if (recordHistory) pushAppNavState(false);
}

async function openPersonal(recordHistory = true){
    document.querySelectorAll(".page-section.active").forEach(sec => sec.classList.remove("active"));
    const personalSection = document.getElementById("personalSection");
    personalSection?.classList.add("active");
    
    const container = document.getElementById("personalFacultyListContainer");
    if(!container) return;
    
    container.innerHTML = `<div class="loading-state">Loading faculty list...</div>`;
    try {
        if (ALL_FACULTY_LIST.length === 0) {
            const res = await fetch("/admin/faculty-list");
            if (!res.ok) throw new Error('Failed to fetch faculty list');
            const data = await res.json();
            ALL_FACULTY_LIST = data.faculty || [];
        }
        renderPersonalFacultyList(ALL_FACULTY_LIST);
    } catch(e) {
        console.error(e);
        container.innerHTML = `<div class="error-state">Error loading list. Please try again.</div>`;
    }
    if (recordHistory) pushAppNavState(false);
}

function openResearch(recordHistory = true){
    document.querySelectorAll(".page-section.active").forEach(sec => sec.classList.remove("active"));
    const researchSection = document.getElementById("researchSection");
    researchSection?.classList.add("active");

    showSection('researchListView', true);
    showSection('researchDetailView', false);
    
    const container = document.getElementById("researchFacultyListContainer");
    container.innerHTML = `<div class="loading-state">Loading faculty list...</div>`;

    try {
        if (ALL_FACULTY_LIST.length === 0) {
             fetch("/admin/faculty-list")
                .then(res => res.json())
                .then(data => {
                    ALL_FACULTY_LIST = data.faculty || [];
                    renderResearchFacultyList(ALL_FACULTY_LIST);
                })
                .catch(e => {
                    console.error(e);
                    container.innerHTML = `<div class="error-state">Error loading list.</div>`;
                });
        } else {
            renderResearchFacultyList(ALL_FACULTY_LIST);
        }
    } catch (e) {
        console.error(e);
        container.innerHTML = `<div class="error-state">Error loading list.</div>`;
    }
    if (recordHistory) pushAppNavState(false);
}

async function openExpertise(recordHistory = true){
    document.querySelectorAll(".page-section.active").forEach(sec => sec.classList.remove("active"));
    document.getElementById("expertiseSection")?.classList.add("active");

    const container = document.getElementById("expertiseFacultyListContainer");
    if(!container) return;
    container.innerHTML = `<div class="loading-state">Loading faculty list...</div>`;

    try {
        if (ALL_FACULTY_LIST.length === 0) {
            const res = await fetch("/admin/faculty-list");
            if (!res.ok) throw new Error("Failed to fetch faculty list");
            const data = await res.json();
            ALL_FACULTY_LIST = data.faculty || [];
        }
        renderExpertiseFacultyList(ALL_FACULTY_LIST);
    } catch (e) {
        console.error(e);
        container.innerHTML = `<div class="error-state">Failed to load faculty list.</div>`;
    }
    if (recordHistory) pushAppNavState(false);
}


// ======================================================
// DEPARTMENTS MODULE
// ======================================================

async function loadDepartments() {
    const grid = document.getElementById("departmentsGrid");
    if (!grid) return;

    grid.innerHTML = `<div class="loading-state">Loading departments...</div>`;
    CURRENT_DEPARTMENT_VIEW = null;

    try {
        const res = await fetch("/admin/departments");
        if (!res.ok) throw new Error('Failed to fetch departments');

        const data = await res.json();
        ALL_DEPARTMENTS = data.departments || [];

        renderDepartments(ALL_DEPARTMENTS);
    } catch (e) {
        console.error(e);
        grid.innerHTML = `<div class="error-state">Could not load departments.</div>`;
    }
}

function renderDepartments(list) {
    const grid = document.getElementById("departmentsGrid");
    if (!grid) return;
    if (list.length === 0) {
        grid.innerHTML = `<div class="empty-state">No departments found for your search.</div>`;
        return;
    }

    grid.innerHTML = list.map(dept => `
        <div class="main-card" onclick="openFacultyForDept('${dept.department_code}')">
            <div class="main-icon">&#127979;</div>
            <h2>${dept.department_name}</h2>
            <p>Teaching ${dept.teaching_count} | Non-Teaching ${dept.non_teaching_count} | Total ${dept.total_count}</p>
        </div>
    `).join('');
}

function filterDepartments() {
    const query = document.getElementById("deptSearch").value.toLowerCase().trim();
    const filtered = ALL_DEPARTMENTS.filter(dept =>
        (dept.department_name || "").toLowerCase().includes(query) ||
        (dept.department_code || "").toLowerCase().includes(query)
    );
    renderDepartments(filtered);
}

function backToDepartments() {
    navigateBack(() => {
        document.querySelectorAll(".page-section.active").forEach(sec => sec.classList.remove("active"));
        document.getElementById("departmentsSection")?.classList.add("active");
    });
}

function createFacultyCard(faculty) {
    const photoUrl = faculty.photo ? withCacheBust(faculty.photo) : `https://ui-avatars.com/api/?name=${encodeURIComponent(faculty.name)}&background=random&color=fff&size=96`;
    const validId = hasValidFacultyId(faculty.faculty_id);
    const disabledAttr = validId ? "" : "disabled title='Missing faculty id'";
    const id = String(faculty.faculty_id || "").trim();

    return `
    <div class="main-card" style="text-align: left; padding: 1rem; cursor: pointer; display: flex; flex-direction: column; justify-content: space-between;" onclick="openFacultyProfile('${id}')">
        <div>
            <div style="display: flex; align-items: center; margin-bottom: 1rem;">
                <img src="${photoUrl}" alt="Photo of ${faculty.name}" style="width: 60px; height: 60px; border-radius: 50%; margin-right: 1rem; object-fit: cover;">
                <div>
                    <h4 class="faculty-name" style="margin: 0 0 0.25rem 0;">${faculty.name}</h4>
                    <p style="margin: 0; font-size: 0.9em; color: #555;">${id || "N/A"}</p>
                </div>
            </div>
            <p style="margin: 0.5rem 0;"><strong>Designation:</strong><br>${faculty.designation || 'N/A'}</p>
            <p style="margin: 0.5rem 0;"><strong>Login:</strong><br>${faculty.username || 'N/A'}</p>
            <p style="margin: 0.5rem 0; word-break: break-all;"><strong>Email:</strong><br>${faculty.email || 'N/A'}</p>
            <p style="margin: 0.5rem 0; font-size: 0.85em; color: #4b5563;">
                <strong>Docs:</strong> Personal ${faculty.personal_docs_count || 0}/5 | Qualification ${faculty.qualification_docs_count || 0}/5
            </p>
        </div>
        <div style="margin-top: 1rem; text-align: right;">
            <button class="small-btn" type="button" ${disabledAttr} onclick="event.stopPropagation(); openFacultyProfile('${id}', true)">Edit Profile</button>
        </div>
    </div>
    `;
}

async function impersonateFacultyDashboard(facultyId) {
    if (!hasValidFacultyId(facultyId)) {
        alert("Invalid faculty ID for this row.");
        return;
    }
    try {
        const url = `/admin/impersonate/${encodeURIComponent(String(facultyId).trim())}`;
        const res = await fetch(url, { method: "POST" });
        const data = await parseApiResponse(res);
        if (!res.ok) throw new Error(data.error || "Failed to start impersonation");
        window.location.href = data.redirect || "/faculty-dashboard";
    } catch (e) {
        alert(`Error: ${e.message}`);
    }
}

async function adminToggleLockById(facultyId, currentLocked) {
    if (!hasValidFacultyId(facultyId)) {
        alert("Invalid faculty ID for this row.");
        return;
    }
    const targetLock = !Boolean(currentLocked);
    const confirmMsg = targetLock ? "Lock this faculty account?" : "Unlock this faculty account?";
    if (!confirm(confirmMsg)) return;
    try {
        const res = await fetch(`/admin/faculty/${encodeURIComponent(String(facultyId).trim())}/lock`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ locked: targetLock })
        });
        const data = await parseApiResponse(res);
        if (!res.ok) throw new Error(data.error || "Failed to update lock state");

        const apply = (f) => {
            if (f && f.faculty_id === facultyId) f.account_locked = !!data.account_locked;
        };
        ALL_FACULTY_LIST.forEach(apply);
        (CURRENT_DEPARTMENT_VIEW?.teaching || []).forEach(apply);
        (CURRENT_DEPARTMENT_VIEW?.non_teaching || []).forEach(apply);
        if (CURRENT_FACULTY_DATA && CURRENT_FACULTY_DATA.faculty_id === facultyId) {
            CURRENT_FACULTY_DATA.account_locked = !!data.account_locked;
            const lockState = document.getElementById('profileAccountLockState');
            if (lockState) lockState.value = data.account_locked ? "Locked" : "Active";
        }
        await syncAdminActiveView();
        alert(data.message || "Account state updated");
    } catch (e) {
        alert(`Error: ${e.message}`);
    }
}

async function adminResetPasswordById(facultyId) {
    if (!hasValidFacultyId(facultyId)) {
        alert("Invalid faculty ID for this row.");
        return;
    }
    const newPassword = prompt("Enter temporary password for this faculty:");
    if (!newPassword) return;
    try {
        const res = await fetch(`/admin/faculty/${encodeURIComponent(String(facultyId).trim())}/reset-password`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ new_password: newPassword })
        });
        const data = await parseApiResponse(res);
        if (!res.ok) throw new Error(data.error || "Failed to reset password");
        alert("Password reset successful.");
    } catch (e) {
        alert(`Error: ${e.message}`);
    }
}

function renderFacultySection(title, list) {
    const safeList = list || [];
    if (safeList.length === 0) {
        return `
            <h3 style="grid-column: 1 / -1; margin-top: 0.75rem;">${title} (0)</h3>
            <div class="empty-state" style="grid-column: 1 / -1;">No faculty found in this section.</div>
        `;
    }

    return `
        <h3 style="grid-column: 1 / -1; margin-top: 0.75rem;">${title} (${safeList.length})</h3>
        ${safeList.map(createFacultyCard).join("")}
    `;
}

function renderDepartmentFaculty(payload, query = "") {
    const grid = document.getElementById("departmentsGrid");
    if (!grid) return;

    const lowerQuery = (query || "").toLowerCase().trim();
    const teachingRaw = payload?.teaching || [];
    const nonTeachingRaw = payload?.non_teaching || [];
    const filterFn = (f) =>
        !lowerQuery ||
        (f.name || "").toLowerCase().includes(lowerQuery) ||
        (f.faculty_id || "").toLowerCase().includes(lowerQuery) ||
        (f.designation || "").toLowerCase().includes(lowerQuery);

    const teaching = teachingRaw.filter(filterFn);
    const nonTeaching = nonTeachingRaw.filter(filterFn);
    const emptyAll = teaching.length === 0 && nonTeaching.length === 0;

    const backBtn = `<div style="grid-column: 1 / -1; margin-bottom: 1rem; display:flex; gap:10px; align-items:center; flex-wrap:wrap;">
        <button class="small-btn" onclick="closeDepartmentFacultyView()">&larr; Back to Departments</button>
        <button class="small-btn" style="background:#16a34a; color:#fff;" onclick="openCreateFacultyForCurrentDepartment()">+ Add Faculty In ${payload.department_name}</button>
    </div>`;
    const header = `<h3 style="grid-column: 1 / -1;">Faculty in ${payload.department_name}</h3>`;

    let content = '';
    if (emptyAll) {
        content = `<div class="empty-state" style="grid-column: 1 / -1;">No faculty found in this department.</div>`;
    } else {
        content = `
            ${renderFacultySection("Teaching Faculty", teaching)}
            ${renderFacultySection("Non-Teaching Faculty", nonTeaching)}
        `;
    }

    grid.innerHTML = backBtn + header + content;
}

async function openFacultyForDept(departmentCode, recordHistory = true) {
    CURRENT_DEPARTMENT = departmentCode;
    const grid = document.getElementById("departmentsGrid");
    if (!grid) return;

    grid.innerHTML = `<div class="loading-state" style="grid-column: 1/-1;">Loading faculty for ${departmentCode}...</div>`;

    try {
        const res = await fetch(`/admin/departments/${encodeURIComponent(departmentCode)}/faculty`);
        if (!res.ok) throw new Error("Failed to fetch department faculty");
        CURRENT_DEPARTMENT_VIEW = await res.json();
        renderDepartmentFaculty(CURRENT_DEPARTMENT_VIEW, document.getElementById("facultySearch")?.value || "");
    } catch (e) {
        console.error(e);
        grid.innerHTML = `<div class="error-state" style="grid-column: 1/-1;">Could not load faculty.</div>`;
    }
    if (recordHistory) pushAppNavState(false);
}

function closeDepartmentFacultyView() {
    CURRENT_DEPARTMENT_VIEW = null;
    CURRENT_CREATE_DEPARTMENT = "";
    CURRENT_CREATE_DEPARTMENT_LOCKED = false;
    renderDepartments(ALL_DEPARTMENTS);
    pushAppNavState(false);
}

function openCreateFacultyForCurrentDepartment() {
    const deptName = CURRENT_DEPARTMENT_VIEW?.department_name || "";
    if (!deptName) {
        alert("Open a department first.");
        return;
    }
    openCreateFaculty(deptName, true);
}


// ======================================================
// FACULTY PROFILE MODULE (ADMIN)
// ======================================================

async function backToFaculty() {
    navigateBack(async () => {
        document.getElementById('profileSection').classList.remove('active');
        await restoreProfileReturnContext();
    });
}

async function openFacultyProfile(facultyId, isEditing = false, sourceSection = null, recordHistory = true) {
    CURRENT_FACULTY_ID = facultyId;
    CURRENT_CREATE_DEPARTMENT = "";
    CURRENT_CREATE_DEPARTMENT_LOCKED = false;
    if (recordHistory) {
        captureProfileReturnContext(sourceSection);
    }
    
    document.querySelectorAll(".page-section.active").forEach(sec => sec.classList.remove("active"));
    const profileSection = document.getElementById('profileSection');
    profileSection.classList.add('active');

    // Clear previous data and show loading state
    document.getElementById('profileName').value = 'Loading...';
    document.getElementById('profileFacultyId').value = '';
    document.getElementById('profileDept').value = '';
    document.getElementById('profileDesignation').value = '';
    const roleElInit = document.getElementById('profileNormalizedRole');
    if (roleElInit) roleElInit.value = '';
    const lockStateInit = document.getElementById('profileAccountLockState');
    if (lockStateInit) lockStateInit.value = '-';
    document.getElementById('profileEmail').value = '';
    document.getElementById('profilePhone').value = '';
    document.getElementById('profileUsername').value = '';
    document.getElementById('profilePassword').value = '';
    document.getElementById('qualificationList').innerHTML = '<div class="loading-state">Loading...</div>';
    document.getElementById('expertiseList').innerHTML = '<div class="loading-state">Loading...</div>';
    document.getElementById('publicationList').innerHTML = '<div class="loading-state">Loading...</div>';
    document.getElementById('documentList').innerHTML = '<div class="loading-state">Loading...</div>';
    
    try {
        // IMPORTANT: This requires a new backend endpoint: GET /admin/faculty/<faculty_id>
        const res = await fetch(`/admin/faculty/${facultyId}`); 
        if (!res.ok) throw new Error(`Failed to load faculty profile (status: ${res.status})`);
        
        CURRENT_FACULTY_DATA = await res.json();
        
        TEMP_QUALIFICATIONS = JSON.parse(JSON.stringify(CURRENT_FACULTY_DATA.qualifications || []));
        TEMP_PUBLICATIONS = JSON.parse(JSON.stringify(CURRENT_FACULTY_DATA.publications || []));
        TEMP_SUBJECT_EXPERTISE = normalizeSubjectExpertise(CURRENT_FACULTY_DATA.subject_expertise || []);

        populateProfileData(CURRENT_FACULTY_DATA);

        if (isEditing) {
            enableEdit();
        } else {
            disableEdit();
        }
        if (recordHistory) pushAppNavState(false);

    } catch (e) {
        console.error(e);
        const container = document.querySelector('#profileSection .profile-layout');
        if(container) container.innerHTML = `<div class="error-state" style="padding: 2rem;">Could not load profile. Please ensure the backend API endpoint '/admin/faculty/&lt;faculty_id&gt;' is available and working.</div>`;
    }
}

const PROFILE_PHOTO_FALLBACK =
    "data:image/svg+xml,%3Csvg%20xmlns%3D%27http%3A//www.w3.org/2000/svg%27%20viewBox%3D%270%200%20128%20128%27%3E%3Cdefs%3E%3CradialGradient%20id%3D%27g%27%20cx%3D%2735%25%27%20cy%3D%2730%25%27%20r%3D%2785%25%27%3E%3Cstop%20offset%3D%270%25%27%20stop-color%3D%27%23fff7ed%27/%3E%3Cstop%20offset%3D%27100%25%27%20stop-color%3D%27%23ffedd5%27/%3E%3C/radialGradient%3E%3C/defs%3E%3Crect%20width%3D%27128%27%20height%3D%27128%27%20rx%3D%2764%27%20fill%3D%27url(%23g)%27/%3E%3Cpath%20d%3D%27M64%2068c-14.4%200-26%2011.6-26%2026v6h52v-6c0-14.4-11.6-26-26-26z%27%20fill%3D%27%23fdba74%27/%3E%3Ccircle%20cx%3D%2764%27%20cy%3D%2746%27%20r%3D%2718%27%20fill%3D%27%23fb923c%27/%3E%3C/svg%3E";

function openAdminPhotoLightbox(src) {
    const box = document.getElementById("adminPhotoLightbox");
    const img = document.getElementById("adminPhotoLightboxImg");
    if (!box || !img) return;
    if (!src) return;
    img.src = src;
    box.classList.add("is-open");
    box.setAttribute("aria-hidden", "false");
    document.body.style.overflow = "hidden";
}

function closeAdminPhotoLightbox() {
    const box = document.getElementById("adminPhotoLightbox");
    const img = document.getElementById("adminPhotoLightboxImg");
    if (!box || !img) return;
    box.classList.remove("is-open");
    box.setAttribute("aria-hidden", "true");
    img.removeAttribute("src");
    document.body.style.overflow = "";
}

async function syncAdminActiveView() {
    const now = Date.now();
    if (now - LAST_ADMIN_SYNC_TS < 1500) return;
    LAST_ADMIN_SYNC_TS = now;
    try {
        const sectionId = getActiveSectionId();
        if (sectionId === "departmentsSection" && CURRENT_DEPARTMENT_VIEW?.department_code) {
            await openFacultyForDept(CURRENT_DEPARTMENT_VIEW.department_code, false);
            return;
        }
        if (sectionId === "profileSection" && CURRENT_FACULTY_ID && !IS_PROFILE_EDIT_MODE) {
            await openFacultyProfile(CURRENT_FACULTY_ID, false, null, false);
            return;
        }
        if (sectionId === "personalSection" || sectionId === "researchSection" || sectionId === "expertiseSection") {
            const res = await fetch("/admin/faculty-list");
            if (!res.ok) return;
            const data = await res.json();
            ALL_FACULTY_LIST = data.faculty || [];
            if (sectionId === "personalSection") filterPersonalFaculty();
            if (sectionId === "researchSection") filterResearchFaculty();
            if (sectionId === "expertiseSection") filterExpertiseFaculty();
        }
    } catch (e) {
        console.error("Admin sync failed", e);
    }
}

async function refreshCurrentFacultyData() {
    LAST_ADMIN_SYNC_TS = Date.now();
    try {
        await syncAdminActiveView();
        alert("Faculty data refreshed.");
    } catch (e) {
        console.error("Manual refresh failed", e);
        alert("Refresh failed. Please try again.");
    }
}

function populateProfileData(data) {
    if (!data) return;
    
    const photoEl = document.getElementById('profilePhoto');
    if (photoEl) photoEl.src = data.photo ? withCacheBust(data.photo) : PROFILE_PHOTO_FALLBACK;
    document.getElementById('profileName').value = data.name || '';
    document.getElementById('profileFacultyId').value = data.faculty_id || '';
    document.getElementById('profileDept').value = data.department || '';
    document.getElementById('profileDesignation').value = data.designation || '';
    const roleEl = document.getElementById('profileNormalizedRole');
    if (roleEl) roleEl.value = data.normalized_role || data.role || '';
    document.getElementById('profileEmail').value = data.email || '';
    document.getElementById('profilePhone').value = data.phone || '';
    document.getElementById('profileUsername').value = data.username || '';
    document.getElementById('profilePassword').value = '';
    const officeRoom = document.getElementById('profileOfficeRoom');
    if (officeRoom) officeRoom.value = data.office_room || '';
    const extension = document.getElementById('profileExtension');
    if (extension) extension.value = data.extension || '';
    const notes = document.getElementById('profileAdminNotes');
    if (notes) notes.value = data.admin_notes || '';
    const lockState = document.getElementById('profileAccountLockState');
    if (lockState) lockState.value = data.account_locked ? "Locked" : "Active";

    renderProfileQualifications(TEMP_QUALIFICATIONS);
    renderProfileExpertise(TEMP_SUBJECT_EXPERTISE);
    renderProfilePublications(TEMP_PUBLICATIONS);
    renderProfileDocuments(data);
}

function impersonateCurrentProfile() {
    if (!CURRENT_FACULTY_ID) return alert("Open a faculty profile first.");
    impersonateFacultyDashboard(CURRENT_FACULTY_ID);
}

async function toggleFacultyAccountLock() {
    if (!CURRENT_FACULTY_ID) return alert("Open a faculty profile first.");
    const currentlyLocked = !!(CURRENT_FACULTY_DATA && CURRENT_FACULTY_DATA.account_locked);
    await adminToggleLockById(CURRENT_FACULTY_ID, currentlyLocked);
}

async function resetFacultyPasswordByAdmin() {
    if (!CURRENT_FACULTY_ID) return alert("Open a faculty profile first.");
    await adminResetPasswordById(CURRENT_FACULTY_ID);
}

function normalizeSubjectExpertise(list) {
    if (!Array.isArray(list)) return [];
    return list
        .map(item => {
            if (!item) return null;
            if (typeof item === "string") {
                return { subject: item.trim(), cert_ids: [] };
            }
            if (typeof item === "object") {
                return {
                    subject: (item.subject || "").trim(),
                    cert_ids: Array.isArray(item.cert_ids) ? item.cert_ids : []
                };
            }
            return null;
        })
        .filter(item => item && item.subject);
}

async function openInsights(recordHistory = true) {
    document.querySelectorAll(".page-section.active").forEach(sec => sec.classList.remove("active"));
    document.getElementById("insightsSection")?.classList.add("active");
    await loadInsights();
    if (recordHistory) pushAppNavState(false);
}

function renderInsightsSummary(data) {
    const wrap = document.getElementById("insightsSummary");
    if (!wrap) return;
    const stats = [
        { label: "Total Faculty", value: data.total_faculty || 0 },
        { label: "Personal Docs Complete", value: data.personal_docs_complete || 0 },
        { label: "Qualification Docs Complete", value: data.qualification_docs_complete || 0 },
        { label: "Certifications Verified", value: data.certifications_verified || 0 },
        { label: "Certifications Pending", value: data.certifications_pending || 0 },
    ];
    wrap.innerHTML = stats.map(s => `
        <div class="insight-stat">
            <div class="label">${s.label}</div>
            <div class="value">${s.value}</div>
        </div>
    `).join("");
}

function renderInsightsNotifications(notifications) {
    const wrap = document.getElementById("insightsNotifications");
    if (!wrap) return;
    if (!notifications || notifications.length === 0) {
        wrap.innerHTML = `<div class="empty-state" style="min-height:120px;">No notifications.</div>`;
        return;
    }
    wrap.innerHTML = `
        <div class="insight-list">
            ${notifications.map(n => `
                <div class="insight-item">
                    <div><strong>${n.title || "Notification"}</strong></div>
                    <div>${n.message || ""}</div>
                    <div class="meta">${n.created_at || ""}</div>
                    ${n.is_read ? "" : `<button class="small-btn mark-read-btn" onclick="markAdminNotificationRead('${n.notification_id}')">Mark Read</button>`}
                </div>
            `).join("")}
        </div>
    `;
}

function renderInsightsAudit(logs) {
    const wrap = document.getElementById("insightsAudit");
    if (!wrap) return;
    if (!logs || logs.length === 0) {
        wrap.innerHTML = `<div class="empty-state" style="min-height:120px;">No audit logs yet.</div>`;
        return;
    }
    const top = logs.slice(0, 30);
    wrap.innerHTML = `
        <div style="overflow:auto;">
            <table class="audit-table">
                <thead>
                    <tr><th>Time</th><th>Actor</th><th>Action</th><th>Target</th></tr>
                </thead>
                <tbody>
                    ${top.map(l => `
                        <tr>
                            <td>${l.timestamp || ""}</td>
                            <td>${(l.actor_role || "")} / ${(l.actor_id || "")}</td>
                            <td>${l.action || ""}</td>
                            <td>${(l.target_type || "")} ${l.target_id ? "(" + l.target_id + ")" : ""}</td>
                        </tr>
                    `).join("")}
                </tbody>
            </table>
        </div>
    `;
}

async function markAdminNotificationRead(notificationId) {
    try {
        const res = await fetch(`/admin/notifications/${encodeURIComponent(notificationId)}/read`, { method: "PUT" });
        if (!res.ok) throw new Error((await res.json()).error || "Failed to mark read");
        await loadInsights();
    } catch (e) {
        alert(`Error: ${e.message}`);
    }
}

async function loadInsights() {
    const summary = document.getElementById("insightsSummary");
    const notifications = document.getElementById("insightsNotifications");
    const audit = document.getElementById("insightsAudit");
    if (summary) summary.innerHTML = `<div class="loading-state">Loading analytics...</div>`;
    if (notifications) notifications.innerHTML = `<div class="loading-state">Loading notifications...</div>`;
    if (audit) audit.innerHTML = `<div class="loading-state">Loading audit logs...</div>`;

    try {
        const [sumRes, notifRes, auditRes] = await Promise.all([
            fetch("/admin/analytics/overview"),
            fetch("/admin/notifications?limit=20"),
            fetch("/admin/audit-logs?limit=80")
        ]);
        if (!sumRes.ok) throw new Error("Failed to load analytics");
        if (!notifRes.ok) throw new Error("Failed to load notifications");
        if (!auditRes.ok) throw new Error("Failed to load audit logs");

        const sumData = await sumRes.json();
        const notifData = await notifRes.json();
        const auditData = await auditRes.json();

        renderInsightsSummary(sumData || {});
        renderInsightsNotifications(notifData.notifications || []);
        renderInsightsAudit(auditData.logs || []);
    } catch (e) {
        if (summary) summary.innerHTML = `<div class="error-state">Could not load analytics.</div>`;
        if (notifications) notifications.innerHTML = `<div class="error-state">${e.message}</div>`;
        if (audit) audit.innerHTML = `<div class="error-state">${e.message}</div>`;
    }
}

function triggerPhotoUpload() {
    if (!CURRENT_FACULTY_ID) {
        alert("Please create/save faculty profile first.");
        return;
    }
    document.getElementById("photoUpload")?.click();
}

async function handlePhotoUpload() {
    if (!CURRENT_FACULTY_ID) {
        alert("Please create/save faculty profile first.");
        return;
    }

    const input = document.getElementById("photoUpload");
    const file = input?.files?.[0];
    if (!file) return;

    const formData = new FormData();
    formData.append("photo", file);

    try {
        const res = await fetch(`/admin/faculty/${encodeURIComponent(CURRENT_FACULTY_ID)}/upload-photo`, {
            method: "POST",
            body: formData
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || "Photo upload failed");

        const photoPath = data.photo || PROFILE_PHOTO_FALLBACK;
        const img = document.getElementById("profilePhoto");
        if (img) img.src = photoPath;

        if (CURRENT_FACULTY_DATA) CURRENT_FACULTY_DATA.photo = photoPath;
        ALL_FACULTY_LIST.forEach(f => {
            if (f.faculty_id === CURRENT_FACULTY_ID) f.photo = photoPath;
        });
        (CURRENT_DEPARTMENT_VIEW?.teaching || []).forEach(f => {
            if (f.faculty_id === CURRENT_FACULTY_ID) f.photo = photoPath;
        });
        (CURRENT_DEPARTMENT_VIEW?.non_teaching || []).forEach(f => {
            if (f.faculty_id === CURRENT_FACULTY_ID) f.photo = photoPath;
        });

        input.value = "";
        alert("Photo uploaded successfully.");
    } catch (e) {
        alert(`Error: ${e.message}`);
    }
}

async function removeProfilePhoto() {
    if (!CURRENT_FACULTY_ID) {
        alert("Please create/save faculty profile first.");
        return;
    }
    if (!confirm("Remove this profile photo?")) return;

    try {
        const res = await fetch(`/admin/faculty/${encodeURIComponent(CURRENT_FACULTY_ID)}/remove-photo`, {
            method: "DELETE"
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || "Photo remove failed");

        const img = document.getElementById("profilePhoto");
        if (img) img.src = PROFILE_PHOTO_FALLBACK;

        if (CURRENT_FACULTY_DATA) CURRENT_FACULTY_DATA.photo = "";
        ALL_FACULTY_LIST.forEach(f => {
            if (f.faculty_id === CURRENT_FACULTY_ID) f.photo = "";
        });
        (CURRENT_DEPARTMENT_VIEW?.teaching || []).forEach(f => {
            if (f.faculty_id === CURRENT_FACULTY_ID) f.photo = "";
        });
        (CURRENT_DEPARTMENT_VIEW?.non_teaching || []).forEach(f => {
            if (f.faculty_id === CURRENT_FACULTY_ID) f.photo = "";
        });

        alert("Photo removed successfully.");
    } catch (e) {
        alert(`Error: ${e.message}`);
    }
}

function renderProfileQualifications(list) {
    const container = document.getElementById('qualificationList');
    let html = '';

    if (!list || list.length === 0) {
        html += '<p class="empty-text">No qualifications added.</p>';
        container.innerHTML = html;
        return;
    }

    html += list.map((q, i) => {
        const display = `${q.type || q} ${q.year ? `(${q.year})` : ''}`;
        const editControls = IS_PROFILE_EDIT_MODE ? `
            <div class="item-actions">
                <button class="small-btn" onclick="openQualificationModal(${i})">Edit</button>
                <button class="small-btn danger" onclick="deleteQualification(${i})">Del</button>
            </div>
        ` : '';
        return `<div class="list-item"><span>${display}</span>${editControls}</div>`;
    }).join('');
    
    container.innerHTML = html;
}

function renderProfileExpertise(list) {
    const container = document.getElementById('expertiseList');
    if (!list || list.length === 0) {
        container.innerHTML = '<p class="empty-text">No expertise added.</p>';
        return;
    }
    container.innerHTML = list.map((e, i) => `
        <div class="list-item">
            <span>${e.subject || e}</span>
            ${IS_PROFILE_EDIT_MODE ? `<div class="item-actions"><button class="small-btn danger" onclick="removeSubjectExpertiseAt(${i})">Del</button></div>` : ''}
        </div>
    `).join('');
}

function renderProfilePublications(list) {
    const container = document.getElementById('publicationList');
    let html = '';

    if (!list || list.length === 0) {
        html += '<p class="empty-text">No publications or books added.</p>';
        container.innerHTML = html;
        return;
    }
    html += list.map((p, i) => `
        <div class="list-item-multi-line">
            <div class="item-main-line">
                <strong>${p.title}</strong> (${p.year})
                ${IS_PROFILE_EDIT_MODE ? `
                    <div class="item-actions">
                        <button class="small-btn" onclick="openPublicationModal(${i})">Edit</button>
                        <button class="small-btn danger" onclick="deletePublication(${i})">Del</button>
                    </div>
                ` : ''}
            </div>
            <div class="item-sub-line">${p.journal || p.type}</div>
            ${p.doi ? `<div class="item-sub-line"><a href="https://doi.org/${p.doi}" target="_blank">DOI: ${p.doi}</a></div>` : ''}
        </div>`).join('');
    container.innerHTML = html;
}

function renderProfileDocuments(profileData) {
    const container = document.getElementById('documentList');
    const qualDocs = profileData?.qualification_documents || {};
    const personalDocs = profileData?.personal_documents || {};

    const qualDocTypes = [
        { key: 'ssc_memo', label: '10th Memo' },
        { key: 'inter_memo', label: 'Inter / Diploma' },
        { key: 'btech_memo', label: 'B.Tech / Degree' },
        { key: 'mtech_memo', label: 'M.Tech / PG' },
        { key: 'phd_memo', label: 'PhD' },
    ];
    const personalDocTypes = [
        { key: 'aadhaar', label: 'Aadhaar' },
        { key: 'pan', label: 'PAN' },
        { key: 'bank_passbook', label: 'Bank Passbook' },
        { key: 'service_register', label: 'Service Register' },
        { key: 'joining_letter', label: 'Joining Letter' },
    ];

    const qualUploaded = qualDocTypes.filter(d => !!qualDocs[d.key]).length;
    const personalUploaded = personalDocTypes.filter(d => !!personalDocs[d.key]).length;
    const qualTotal = qualDocTypes.length;
    const personalTotal = personalDocTypes.length;
    const pct = (uploaded, total) => total ? Math.round((uploaded / total) * 100) : 0;

    container.innerHTML = `
        <div class="doc-summary">
            <div class="doc-summary-row">
                <div class="doc-summary-left">
                    <div class="doc-summary-title">Qualification Documents</div>
                    <div class="doc-summary-meta">${qualUploaded} / ${qualTotal} uploaded</div>
                </div>
                <div class="doc-summary-right">
                    <button class="small-btn" type="button" onclick="openQualificationDocsModal(CURRENT_FACULTY_ID, CURRENT_FACULTY_DATA.name)">Upload</button>
                    <div class="doc-summary-pill">${pct(qualUploaded, qualTotal)}%</div>
                </div>
            </div>

            <div class="doc-summary-divider"></div>

            <div class="doc-summary-row">
                <div class="doc-summary-left">
                    <div class="doc-summary-title">Personal Documents</div>
                    <div class="doc-summary-meta">${personalUploaded} / ${personalTotal} uploaded</div>
                </div>
                <div class="doc-summary-right">
                    <button class="small-btn" type="button" onclick="openPersonalDocsModal(CURRENT_FACULTY_ID, CURRENT_FACULTY_DATA.name)">Upload</button>
                    <div class="doc-summary-pill">${pct(personalUploaded, personalTotal)}%</div>
                </div>
            </div>
        </div>
    `;
}


function enableEdit() {
    IS_PROFILE_EDIT_MODE = true;
    document.querySelectorAll('#profileSection .admin-edit').forEach(el => el.readOnly = false);
    if (!CURRENT_FACULTY_ID && !CURRENT_CREATE_DEPARTMENT_LOCKED) {
        document.getElementById('profileDept').readOnly = false;
    } else {
        document.getElementById('profileDept').readOnly = true;
    }
    document.querySelectorAll('#profileSection .admin-only').forEach(el => el.style.display = 'inline-block');
    document.querySelector('#profileSection button[onclick="enableEdit()"]').style.display = 'none';
    document.querySelector('#profileSection button[onclick="saveProfile()"]').style.display = 'inline-block';
    renderProfileQualifications(TEMP_QUALIFICATIONS);
    renderProfileExpertise(TEMP_SUBJECT_EXPERTISE);
    renderProfilePublications(TEMP_PUBLICATIONS);
}

function disableEdit() {
    IS_PROFILE_EDIT_MODE = false;
    document.querySelectorAll('#profileSection .admin-edit').forEach(el => el.readOnly = true);
    document.getElementById('profileDept').readOnly = true;
    document.querySelectorAll('#profileSection .admin-only').forEach(el => el.style.display = 'none');
    document.querySelector('#profileSection button[onclick="enableEdit()"]').style.display = 'inline-block';
    document.querySelector('#profileSection button[onclick="saveProfile()"]').style.display = 'none';
    renderProfileQualifications(TEMP_QUALIFICATIONS);
    renderProfileExpertise(TEMP_SUBJECT_EXPERTISE);
    renderProfilePublications(TEMP_PUBLICATIONS);
}

async function saveProfile() {
    const saveBtn = document.querySelector('#profileSection button[onclick="saveProfile()"]');
    saveBtn.disabled = true;
    saveBtn.textContent = 'Saving...';

    const isCreating = !CURRENT_FACULTY_ID;

    const payload = {
        name: document.getElementById('profileName').value,
        department: document.getElementById('profileDept').value,
        designation: document.getElementById('profileDesignation').value,
        normalized_role: document.getElementById('profileNormalizedRole')?.value || "",
        email: document.getElementById('profileEmail').value,
        phone: document.getElementById('profilePhone').value,
        username: document.getElementById('profileUsername').value,
        office_room: document.getElementById('profileOfficeRoom')?.value || "",
        extension: document.getElementById('profileExtension')?.value || "",
        admin_notes: document.getElementById('profileAdminNotes')?.value || "",
        qualifications: TEMP_QUALIFICATIONS,
        subject_expertise: TEMP_SUBJECT_EXPERTISE,
        publications: TEMP_PUBLICATIONS,
    };
    const password = document.getElementById('profilePassword').value;
    if (password) {
        payload.password = password;
    }

    if (!payload.name || !payload.department || !payload.email) {
        alert('Name, Department, and Email are required.');
        saveBtn.disabled = false;
        saveBtn.textContent = 'Save Changes';
        return;
    }

    const url = isCreating ? `/admin/faculty` : `/admin/faculty/${CURRENT_FACULTY_ID}`;
    const method = isCreating ? 'POST' : 'PUT';

    try {
        const res = await fetch(url, {
            method: method,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        if (!res.ok) throw new Error((await res.json()).error || 'Save failed');
        
        const savedData = await res.json();
        
        if (isCreating) {
            alert(`Faculty profile created successfully!\nUsername: ${savedData.username || '(auto)'}\nPassword: ${savedData.password || '(set later)'}`);
        } else {
            alert("Faculty profile saved successfully!");
        }

        if (isCreating) {
            ALL_FACULTY_LIST = []; 
            await openFacultyProfile(savedData.faculty_id);
        } else {
            CURRENT_FACULTY_DATA = savedData;
            populateProfileData(CURRENT_FACULTY_DATA);
            disableEdit();
        }

    } catch (e) {
        alert(`Error: ${e.message}`);
    } finally {
        saveBtn.disabled = false;
        saveBtn.textContent = 'Save Changes';
    }
}

function openCreateFaculty(prefillDepartment = "", lockDepartment = false, recordHistory = true) {
    CURRENT_FACULTY_ID = null;
    IS_PROFILE_EDIT_MODE = true;
    CURRENT_CREATE_DEPARTMENT = prefillDepartment || "";
    CURRENT_CREATE_DEPARTMENT_LOCKED = !!(lockDepartment && prefillDepartment);

    document.querySelectorAll(".page-section.active").forEach(sec => sec.classList.remove("active"));
    const profileSection = document.getElementById('profileSection');
    profileSection.classList.add("active");

    {
        const img = document.getElementById('profilePhoto');
        if (img) img.src = PROFILE_PHOTO_FALLBACK;
    }
    document.getElementById('profileName').value = '';
    document.getElementById('profileFacultyId').value = '(auto-generated)';
    document.getElementById('profileDept').value = CURRENT_CREATE_DEPARTMENT || '';
    document.getElementById('profileDesignation').value = '';
    {
        const el = document.getElementById('profileNormalizedRole');
        if (el) el.value = '';
    }
    document.getElementById('profileEmail').value = '';
    document.getElementById('profilePhone').value = '';
    document.getElementById('profileUsername').value = '';
    document.getElementById('profilePassword').value = '';
    {
        const el = document.getElementById('profileAccountLockState');
        if (el) el.value = 'Active';
    }
    {
        const el = document.getElementById('profileOfficeRoom');
        if (el) el.value = '';
    }
    {
        const el = document.getElementById('profileExtension');
        if (el) el.value = '';
    }
    {
        const el = document.getElementById('profileAdminNotes');
        if (el) el.value = '';
    }
    
    TEMP_QUALIFICATIONS = [];
    TEMP_PUBLICATIONS = [];
    TEMP_SUBJECT_EXPERTISE = [];

    renderProfileExpertise(TEMP_SUBJECT_EXPERTISE);
    document.getElementById('documentList').innerHTML = '<p class="empty-text">Manage documents after creation.</p>';

    enableEdit();
    if (recordHistory) pushAppNavState(false);
}

function addExpertise() {
    if (!IS_PROFILE_EDIT_MODE) return;
    const value = prompt("Enter subject expertise:");
    const subject = (value || "").trim();
    if (!subject) return;

    const exists = TEMP_SUBJECT_EXPERTISE.some(x => (x.subject || "").toLowerCase() === subject.toLowerCase());
    if (exists) {
        alert("Subject already added.");
        return;
    }
    TEMP_SUBJECT_EXPERTISE.push({ subject, cert_ids: [] });
    renderProfileExpertise(TEMP_SUBJECT_EXPERTISE);
}

function removeSubjectExpertiseAt(index) {
    if (!IS_PROFILE_EDIT_MODE) return;
    if (index < 0 || index >= TEMP_SUBJECT_EXPERTISE.length) return;
    if (!confirm("Remove this subject expertise?")) return;
    TEMP_SUBJECT_EXPERTISE.splice(index, 1);
    renderProfileExpertise(TEMP_SUBJECT_EXPERTISE);
}

function deleteQualification(index) {
    if (!confirm('Delete this qualification?')) return;
    TEMP_QUALIFICATIONS.splice(index, 1);
    renderProfileQualifications(TEMP_QUALIFICATIONS);
}

function deletePublication(index) {
    if (!confirm('Delete this publication?')) return;
    TEMP_PUBLICATIONS.splice(index, 1);
    renderProfilePublications(TEMP_PUBLICATIONS);
}

function openQualificationModal(index = null) {
    const isEditing = index !== null;
    const qual = isEditing ? TEMP_QUALIFICATIONS[index] : null;

    document.getElementById('qualModal')?.remove();

    const modalHTML = `
    <div class="modal-overlay" id="qualModal">
        <div class="modal-content">
            <div class="modal-header">
                <h3>${isEditing ? 'Edit' : 'Add'} Qualification</h3>
                <button class="modal-close" onclick="this.closest('.modal-overlay').remove()">&times;</button>
            </div>
            <div class="modal-body">
                <div class="input-group">
                    <label for="qualType">Type / Degree</label>
                    <input type="text" id="qualType" value="${qual?.type || ''}" placeholder="e.g., B.Tech, PhD">
                </div>
                <div class="input-group">
                    <label for="qualYear">Year of Completion</label>
                    <input type="text" id="qualYear" value="${qual?.year || ''}" placeholder="e.g., 2020">
                </div>
            </div>
            <div class="modal-footer">
                <button class="small-btn" onclick="this.closest('.modal-overlay').remove()">Cancel</button>
                <button class="small-btn primary" onclick="saveQualification(${index})">Save</button>
            </div>
        </div>
    </div>`;
    document.body.insertAdjacentHTML('beforeend', modalHTML);
    bindEnterAdvance(["qualType", "qualYear"], () => saveQualification(index));
}

function saveQualification(index = null) {
    const type = document.getElementById('qualType').value.trim();
    const year = document.getElementById('qualYear').value.trim();
    if (!type) return alert('Qualification type is required.');

    const newQual = { type, year };
    if (index !== null) {
        TEMP_QUALIFICATIONS[index] = newQual;
    } else {
        TEMP_QUALIFICATIONS.push(newQual);
    }
    document.getElementById('qualModal')?.remove();
    renderProfileQualifications(TEMP_QUALIFICATIONS);
}

function openPublicationModal(index = null) {
    const isEditing = index !== null;
    const pub = isEditing ? TEMP_PUBLICATIONS[index] : null;

    document.getElementById('pubModal')?.remove();

    const modalHTML = `
    <div class="modal-overlay" id="pubModal">
        <div class="modal-content">
            <div class="modal-header"><h3>${isEditing ? 'Edit' : 'Add'} Publication / Book</h3><button class="modal-close" onclick="this.closest('.modal-overlay').remove()">&times;</button></div>
            <div class="modal-body">
                <div class="input-group"><label for="pubTitle">Title</label><input type="text" id="pubTitle" value="${pub?.title || ''}"></div>
                <div class="input-group"><label for="pubJournal">Journal / Publisher</label><input type="text" id="pubJournal" value="${pub?.journal || ''}"></div>
                <div class="input-group"><label for="pubYear">Year</label><input type="text" id="pubYear" value="${pub?.year || ''}"></div>
                <div class="input-group"><label for="pubDoi">DOI / Link</label><input type="text" id="pubDoi" value="${pub?.doi || ''}"></div>
            </div>
            <div class="modal-footer"><button class="small-btn" onclick="this.closest('.modal-overlay').remove()">Cancel</button><button class="small-btn primary" onclick="savePublication(${index})">Save</button></div>
        </div>
    </div>`;
    document.body.insertAdjacentHTML('beforeend', modalHTML);
    bindEnterAdvance(["pubTitle", "pubJournal", "pubYear", "pubDoi"], () => savePublication(index));
}

function savePublication(index = null) {
    const title = document.getElementById('pubTitle').value.trim();
    const journal = document.getElementById('pubJournal').value.trim();
    const year = document.getElementById('pubYear').value.trim();
    const doi = document.getElementById('pubDoi').value.trim();
    if (!title || !journal || !year) return alert('Title, Journal, and Year are required.');

    const newPub = { title, journal, year, doi };
    if (index !== null) {
        TEMP_PUBLICATIONS[index] = newPub;
    } else {
        TEMP_PUBLICATIONS.push(newPub);
    }
    document.getElementById('pubModal')?.remove();
    renderProfilePublications(TEMP_PUBLICATIONS);
}

function filterFaculty() {
    if (!CURRENT_DEPARTMENT_VIEW) return;
    const query = document.getElementById("facultySearch")?.value || "";
    renderDepartmentFaculty(CURRENT_DEPARTMENT_VIEW, query);
}

// ======================================================
// PERSONAL MODULE
// ======================================================
function renderPersonalFacultyList(list) {
    const container = document.getElementById("personalFacultyListContainer");
    if (!container) return;
    container.innerHTML = (list.length === 0) ? `<div class="empty-state">No faculty found.</div>` : `
        <div class="table-wrapper">
            <table class="data-table">
                <thead><tr><th>ID</th><th>Name</th><th>Department</th><th>Documents</th><th>Actions</th></tr></thead>
                <tbody>
                    ${list.map(f => `
                        <tr>
                            <td>${f.faculty_id}</td>
                            <td class="faculty-name">
                                <button class="link-faculty-name" onclick="openFacultyProfileFromList('${f.faculty_id}')">${f.name}</button>
                            </td>
                            <td>${f.department}</td>
                            <td>Personal ${f.personal_docs_count || 0}/5 | Qualification ${f.qualification_docs_count || 0}/5</td>
                            <td>
                                <div class="action-btn-group">
                                    <button class="small-btn" type="button" onclick="openPersonalDocsModal('${f.faculty_id}', '${f.name}')">Manage Documents</button>
                                    <button class="small-btn danger-btn" type="button" onclick="removeFacultyFromManage('${f.faculty_id}', '${(f.name || '').replace(/'/g, "\\'")}', 'personal')">Remove</button>
                                </div>
                            </td>
                        </tr>`).join('')}
                </tbody>
            </table>
        </div>`;
}

function filterPersonalFaculty() {
    const query = document.getElementById("personalFacultySearch").value.toLowerCase().trim();
    const filtered = ALL_FACULTY_LIST.filter(f => (f.name || "").toLowerCase().includes(query) || (f.faculty_id || "").toLowerCase().includes(query));
    renderPersonalFacultyList(filtered);
}

async function openPersonalDocsModal(facultyId, facultyName) {
    CURRENT_FACULTY_ID = facultyId;
    const modal = document.getElementById("personalDocsModal");
    const title = document.getElementById("personalDocsTitle");
    const body = document.getElementById("personalDocsBody");
    if (!modal || !title || !body) return;

    title.textContent = `Personal Documents: ${facultyName}`;
    body.innerHTML = `<div class="loading-state">Loading documents...</div>`;
    modal.classList.add("active");

    try {
        const res = await fetch(`/api/personal/${facultyId}`);
        if (!res.ok) throw new Error('Failed to fetch document details.');
        const documents = await res.json();
        CURRENT_FACULTY_DATA = { ...CURRENT_FACULTY_DATA, personal_documents: documents };
        renderDocCards(documents);
    } catch (e) {
        body.innerHTML = `<div class="error-state">${e.message}</div>`;
    }
}

function closePersonalDocsModal() {
    document.getElementById("personalDocsModal")?.classList.remove("active");
}

async function openQualificationDocsModal(facultyId, facultyName) {
    const modal = document.getElementById("qualificationDocsModal");
    const title = document.getElementById("qualificationDocsTitle");
    const body = document.getElementById("qualificationDocsBody");
    if (!modal || !title || !body) return;

    title.textContent = `Qualification Documents: ${facultyName}`;
    body.innerHTML = `<div class="loading-state">Loading documents...</div>`;
    modal.classList.add("active");

    try {
        const res = await fetch(`/admin/faculty/${facultyId}`);
        if (!res.ok) throw new Error("Failed to fetch qualification documents");
        const faculty = await res.json();
        const docs = faculty.qualification_documents || {};
        renderQualificationDocCards(docs);
    } catch (e) {
        body.innerHTML = `<div class="error-state">${e.message}</div>`;
    }
}

function closeQualificationDocsModal() {
    document.getElementById("qualificationDocsModal")?.classList.remove("active");
}

function escapeHtml(value = "") {
    return String(value).replace(/[&<>"']/g, (char) => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;"
    }[char]));
}

function getFileNameFromPath(path = "") {
    return String(path).split("/").pop() || "";
}

function shortenFileName(fileName = "", maxLength = 34) {
    if (fileName.length <= maxLength) return fileName;
    const extIndex = fileName.lastIndexOf(".");
    if (extIndex <= 0 || extIndex >= fileName.length - 1) {
        return `${fileName.slice(0, maxLength - 3)}...`;
    }
    const ext = fileName.slice(extIndex);
    const base = fileName.slice(0, extIndex);
    const allowedBaseLength = Math.max(8, maxLength - ext.length - 3);
    return `${base.slice(0, allowedBaseLength)}...${ext}`;
}

function renderQualificationDocCards(documents = {}) {
    const body = document.getElementById("qualificationDocsBody");
    if (!body) return;

    const docTypes = [
        { key: "ssc_memo", label: "10th Memo (SSC)", required: true },
        { key: "inter_memo", label: "Intermediate / Diploma", required: true },
        { key: "btech_memo", label: "B.Tech / Degree", required: true },
        { key: "mtech_memo", label: "M.Tech / PG", required: false },
        { key: "phd_memo", label: "PhD", required: false }
    ];

    let cardsHtml = `<div class="doc-grid">${docTypes.map((doc) => createQualificationDocCard(doc.key, doc.label, documents[doc.key], doc.required)).join("")}</div>`;
    cardsHtml += `
        <div class="doc-extra-section">
            <div class="card-head"><h3>Other Qualification Documents</h3></div>
            <div id="otherQualificationDocsList" class="doc-list">
                ${(documents.others && documents.others.length > 0) ? documents.others.map(createOtherQualificationDocItem).join("") : '<p class="empty-text">No other documents uploaded.</p>'}
            </div>
            <div class="upload-area">
                <input type="file" id="file-input-qual-others" class="file-input" accept=".pdf,.png,.jpg,.jpeg" onchange="uploadQualificationDoc('others')">
                <button class="small-btn" type="button" onclick="document.getElementById('file-input-qual-others').click()">Add Document</button>
            </div>
        </div>`;
    body.innerHTML = cardsHtml;
}

function createQualificationDocCard(key, label, path, required = false) {
    const hasFile = !!(path && path.length > 0);
    const fileName = hasFile ? getFileNameFromPath(path) : "";
    const displayName = shortenFileName(fileName);
    const reqBadge = required ? '<span class="doc-required">(Required)</span>' : '<span class="doc-optional">(Optional)</span>';
    return `
        <div class="doc-card">
            <h4>${label}${reqBadge}</h4>
            <div class="doc-status ${hasFile ? "uploaded" : "not-uploaded"}">
                <span class="doc-status-pill">${hasFile ? "Uploaded" : "Missing"}</span>
                ${hasFile
                    ? `<a class="doc-file-link" href="${path}" target="_blank" rel="noopener noreferrer" title="${escapeHtml(fileName)}">${escapeHtml(displayName)}</a>`
                    : '<span class="doc-file-empty">No file uploaded yet.</span>'}
            </div>
            <div class="doc-actions">
                <input type="file" id="file-input-qual-${key}" class="file-input" accept=".pdf,.png,.jpg,.jpeg" onchange="uploadQualificationDoc('${key}')">
                <button class="small-btn" type="button" onclick="document.getElementById('file-input-qual-${key}').click()">${hasFile ? "Replace File" : "Upload File"}</button>
                <button class="small-btn danger-btn" type="button" ${hasFile ? `onclick="deleteQualificationDoc('${key}')"` : "disabled"}>Remove</button>
            </div>
        </div>`;
}

function createOtherQualificationDocItem(path) {
    const fileName = getFileNameFromPath(path);
    const displayName = shortenFileName(fileName, 44);
    return `<div class="doc-list-item" id="qual-other-doc-${fileName.replace(/[^a-zA-Z0-9]/g, "")}">
            <a class="doc-list-link" href="${path}" target="_blank" rel="noopener noreferrer" title="${escapeHtml(fileName)}">${escapeHtml(displayName)}</a>
            <button class="list-item-remove" type="button" onclick="deleteQualificationDoc('others', '${path}')">&times;</button>
        </div>`;
}

async function uploadQualificationDoc(docType) {
    if (!CURRENT_FACULTY_ID) return;
    const inputId = docType === "others" ? "file-input-qual-others" : `file-input-qual-${docType}`;
    const fileInput = document.getElementById(inputId);
    const file = fileInput?.files?.[0];
    if (!file) return;
    {
        const ext = (file.name.split(".").pop() || "").toLowerCase();
        if (!["pdf", "png", "jpg", "jpeg"].includes(ext)) {
            alert("Qualification documents must be PDF or an image (PNG/JPG).");
            fileInput.value = "";
            return;
        }
    }

    const formData = new FormData();
    formData.append("file", file);
    formData.append("doc_type", docType);

    const modalBody = document.getElementById("qualificationDocsBody");
    if (modalBody) modalBody.innerHTML = `<div class="loading-state">Uploading ${file.name}...</div>`;

    try {
        const res = await fetch(`/admin/upload-qualification-doc/${CURRENT_FACULTY_ID}`, {
            method: "POST",
            body: formData
        });
        const result = await res.json();
        if (!res.ok) throw new Error(result.error || "Upload failed");
        renderQualificationDocCards(result.qualification_documents || {});

        if (CURRENT_FACULTY_DATA) {
            CURRENT_FACULTY_DATA.qualification_documents = result.qualification_documents || {};
            renderProfileDocuments(CURRENT_FACULTY_DATA);
        }
        syncFacultyDocCounts(CURRENT_FACULTY_ID, "qualification", result.qualification_documents || {});
    } catch (e) {
        alert(`Error: ${e.message}`);
    }
}

async function deleteQualificationDoc(docType, path = null) {
    if (!CURRENT_FACULTY_ID) return;
    if (!confirm("Are you sure you want to delete this document?")) return;

    const modalBody = document.getElementById("qualificationDocsBody");
    if (modalBody) modalBody.innerHTML = `<div class="loading-state">Deleting...</div>`;

    try {
        let url = `/admin/delete-qualification-doc/${CURRENT_FACULTY_ID}/${docType}`;
        if (docType === "others" && path) {
            url += `?path=${encodeURIComponent(path)}`;
        }

        const res = await fetch(url, { method: "DELETE" });
        const result = await res.json();
        if (!res.ok) throw new Error(result.error || "Deletion failed");
        renderQualificationDocCards(result.qualification_documents || {});

        if (CURRENT_FACULTY_DATA) {
            CURRENT_FACULTY_DATA.qualification_documents = result.qualification_documents || {};
            renderProfileDocuments(CURRENT_FACULTY_DATA);
        }
        syncFacultyDocCounts(CURRENT_FACULTY_ID, "qualification", result.qualification_documents || {});
    } catch (e) {
        alert(`Error: ${e.message}`);
    }
}

function renderDocCards(documents = {}) {
    const body = document.getElementById("personalDocsBody");
    if (!body) return;

    const docTypes = [
        { key: "aadhaar", label: "Aadhaar", required: true },
        { key: "pan", label: "PAN", required: true },
        { key: "bank_passbook", label: "Bank Passbook", required: true },
        { key: "service_register", label: "Service Register", required: true },
        { key: "joining_letter", label: "Joining Letter", required: true }
    ];

    let cardsHtml = `<div class="doc-grid">${docTypes.map((doc) => createDocCard(doc.key, doc.label, documents[doc.key], doc.required)).join("")}</div>`;
    cardsHtml += `
        <div class="doc-extra-section">
            <div class="card-head"><h3>Other Documents</h3></div>
            <div id="otherDocsList" class="doc-list">
                ${(documents.others && documents.others.length > 0) ? documents.others.map(createOtherDocItem).join("") : '<p class="empty-text">No other documents uploaded.</p>'}
            </div>
            <div class="upload-area">
                <input type="file" id="file-input-others" class="file-input" accept=".pdf,.png,.jpg,.jpeg" onchange="uploadPersonalDoc('others')">
                <button class="small-btn" type="button" onclick="document.getElementById('file-input-others').click()">Add Document</button>
            </div>
        </div>`;
    body.innerHTML = cardsHtml;
}

function createDocCard(key, label, path, required = false) {
    const hasFile = !!(path && path.length > 0);
    const fileName = hasFile ? getFileNameFromPath(path) : "";
    const displayName = shortenFileName(fileName);
    const reqBadge = required ? '<span class="doc-required">(Required)</span>' : '<span class="doc-optional">(Optional)</span>';
    return `
        <div class="doc-card">
            <h4>${label}${reqBadge}</h4>
            <div class="doc-status ${hasFile ? "uploaded" : "not-uploaded"}">
                <span class="doc-status-pill">${hasFile ? "Uploaded" : "Missing"}</span>
                ${hasFile
                    ? `<a class="doc-file-link" href="${path}" target="_blank" rel="noopener noreferrer" title="${escapeHtml(fileName)}">${escapeHtml(displayName)}</a>`
                    : '<span class="doc-file-empty">No file uploaded yet.</span>'}
            </div>
            <div class="doc-actions">
                <input type="file" id="file-input-${key}" class="file-input" accept=".pdf,.png,.jpg,.jpeg" onchange="uploadPersonalDoc('${key}')">
                <button class="small-btn" type="button" onclick="document.getElementById('file-input-${key}').click()">${hasFile ? "Replace File" : "Upload File"}</button>
                <button class="small-btn danger-btn" type="button" ${hasFile ? `onclick="deletePersonalDoc('${key}')"` : "disabled"}>Remove</button>
            </div>
        </div>`;
}

function createOtherDocItem(path) {
    const fileName = getFileNameFromPath(path);
    const displayName = shortenFileName(fileName, 44);
    return `<div class="doc-list-item" id="other-doc-${fileName.replace(/[^a-zA-Z0-9]/g, "")}">
            <a class="doc-list-link" href="${path}" target="_blank" rel="noopener noreferrer" title="${escapeHtml(fileName)}">${escapeHtml(displayName)}</a>
            <button class="list-item-remove" type="button" onclick="deletePersonalDoc('others', '${path}')">&times;</button>
        </div>`;
}
function syncFacultyDocCounts(facultyId, docsType, docs) {
    if (!facultyId || !docs) return;
    const personalCount = (docMap => ["aadhaar", "pan", "bank_passbook", "service_register", "joining_letter"].filter(k => !!docMap?.[k]).length);
    const qualCount = (docMap => ["ssc_memo", "inter_memo", "btech_memo", "mtech_memo", "phd_memo"].filter(k => !!docMap?.[k]).length);

    const apply = (row) => {
        if (!row || row.faculty_id !== facultyId) return;
        if (docsType === "personal") {
            row.personal_docs_count = personalCount(docs);
        } else if (docsType === "qualification") {
            row.qualification_docs_count = qualCount(docs);
        }
    };

    ALL_FACULTY_LIST.forEach(apply);
    (CURRENT_DEPARTMENT_VIEW?.teaching || []).forEach(apply);
    (CURRENT_DEPARTMENT_VIEW?.non_teaching || []).forEach(apply);

    if (CURRENT_DEPARTMENT_VIEW) {
        const query = document.getElementById("facultySearch")?.value || "";
        renderDepartmentFaculty(CURRENT_DEPARTMENT_VIEW, query);
    }
}

async function uploadPersonalDoc(docType) {
    const fileInput = document.getElementById(`file-input-${docType}`);
    const file = fileInput.files[0];
    if (!file) return;
    {
        const ext = (file.name.split(".").pop() || "").toLowerCase();
        if (!["pdf", "png", "jpg", "jpeg"].includes(ext)) {
            alert("Personal documents must be PDF or an image (PNG/JPG).");
            fileInput.value = "";
            return;
        }
    }

    const formData = new FormData();
    formData.append("file", file);
    formData.append("doc_type", docType);
    
    const modalBody = document.getElementById('personalDocsBody');
    modalBody.innerHTML = `<div class="loading-state">Uploading ${file.name}...</div>`;

    try {
        const res = await fetch(`/api/personal/${CURRENT_FACULTY_ID}/upload`, { method: "POST", body: formData });
        const result = await res.json();
        if (!res.ok) throw new Error(result.error || 'Upload failed');
        renderDocCards(result.personal_documents);
        if (CURRENT_FACULTY_DATA && CURRENT_FACULTY_DATA.faculty_id === CURRENT_FACULTY_ID) {
            CURRENT_FACULTY_DATA.personal_documents = result.personal_documents || {};
            renderProfileDocuments(CURRENT_FACULTY_DATA);
        }
        syncFacultyDocCounts(CURRENT_FACULTY_ID, "personal", result.personal_documents || {});
    } catch (e) {
        alert(`Error: ${e.message}`);
        renderDocCards(CURRENT_FACULTY_DATA.personal_documents);
    }
}

async function deletePersonalDoc(docType, path = null) {
    if (!confirm('Are you sure you want to delete this document?')) return;
    
    const modalBody = document.getElementById('personalDocsBody');
    modalBody.innerHTML = `<div class="loading-state">Deleting...</div>`;

    try {
        const res = await fetch(`/api/personal/${CURRENT_FACULTY_ID}/delete`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ doc_type: docType, path: path })
        });
        const result = await res.json();
        if (!res.ok) throw new Error(result.error || 'Deletion failed');
        renderDocCards(result.personal_documents);
        if (CURRENT_FACULTY_DATA && CURRENT_FACULTY_DATA.faculty_id === CURRENT_FACULTY_ID) {
            CURRENT_FACULTY_DATA.personal_documents = result.personal_documents || {};
            renderProfileDocuments(CURRENT_FACULTY_DATA);
        }
        syncFacultyDocCounts(CURRENT_FACULTY_ID, "personal", result.personal_documents || {});
    } catch (e) {
        alert(`Error: ${e.message}`);
        renderDocCards(CURRENT_FACULTY_DATA.personal_documents);
    }
}

// ======================================================
// R&D MODULE
// ======================================================
function renderResearchFacultyList(list) {
    const container = document.getElementById("researchFacultyListContainer");
    if (!container) return;
    container.innerHTML = (list.length === 0) ? `<div class="empty-state">No faculty found.</div>` : `
        <div class="table-wrapper">
            <table class="data-table">
                <thead><tr><th>ID</th><th>Name</th><th>Department</th><th>Actions</th></tr></thead>
                <tbody>
                    ${list.map(f => `
                        <tr>
                            <td>${f.faculty_id}</td>
                            <td class="faculty-name">
                                <button class="link-faculty-name" onclick="openFacultyProfileFromList('${f.faculty_id}')">${f.name}</button>
                            </td>
                            <td>${f.department}</td>
                            <td>
                                <div class="action-btn-group">
                                    <button class="small-btn" type="button" onclick="openResearchDetail('${f.faculty_id}', '${f.name}', true)">Manage R&D</button>
                                    <button class="small-btn danger-btn" type="button" onclick="removeFacultyFromManage('${f.faculty_id}', '${(f.name || '').replace(/'/g, "\\'")}', 'research')">Remove</button>
                                </div>
                            </td>
                        </tr>`).join('')}
                </tbody>
            </table>
        </div>`;
}

async function removeFacultyFromManage(facultyId, facultyName, moduleName) {
    if (!facultyId) return;
    if (!confirm(`Remove faculty profile for ${facultyName || facultyId}? This cannot be undone.`)) return;

    try {
        const res = await fetch(`/faculty/delete/${encodeURIComponent(facultyId)}`, { method: "DELETE" });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || "Failed to remove faculty");

        ALL_FACULTY_LIST = (ALL_FACULTY_LIST || []).filter(f => f.faculty_id !== facultyId);
        if (CURRENT_DEPARTMENT_VIEW) {
            CURRENT_DEPARTMENT_VIEW.teaching = (CURRENT_DEPARTMENT_VIEW.teaching || []).filter(f => f.faculty_id !== facultyId);
            CURRENT_DEPARTMENT_VIEW.non_teaching = (CURRENT_DEPARTMENT_VIEW.non_teaching || []).filter(f => f.faculty_id !== facultyId);
        }

        if (moduleName === "personal") {
            filterPersonalFaculty();
        } else if (moduleName === "research") {
            filterResearchFaculty();
        } else {
            renderDepartments(ALL_DEPARTMENTS);
        }

        alert("Faculty removed successfully.");
    } catch (e) {
        alert(`Error: ${e.message}`);
    }
}

async function removeDocSubmissionsForFaculty(facultyId, facultyName, moduleName) {
    if (!facultyId) return;
    const text = moduleName === "personal"
        ? `Remove all Personal + Qualification document submissions for ${facultyName || facultyId}?`
        : `Remove all R&D submissions (certifications/books/papers) for ${facultyName || facultyId}?`;
    if (!confirm(text)) return;

    const url = moduleName === "personal"
        ? `/admin/faculty/${encodeURIComponent(facultyId)}/clear-doc-submissions`
        : `/admin/faculty/${encodeURIComponent(facultyId)}/clear-rd-submissions`;

    try {
        const res = await fetch(url, { method: "DELETE" });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || "Failed to clear submissions");

        if (moduleName === "personal") {
            ALL_FACULTY_LIST = (ALL_FACULTY_LIST || []).map(f => (
                f.faculty_id === facultyId
                    ? { ...f, personal_docs_count: 0, qualification_docs_count: 0 }
                    : f
            ));
            filterPersonalFaculty();
        } else if (moduleName === "research") {
            filterResearchFaculty();
            if (CURRENT_FACULTY_ID === facultyId) {
                openResearchDetail(facultyId, facultyName || "");
            }
        }

        if (CURRENT_FACULTY_DATA && CURRENT_FACULTY_DATA.faculty_id === facultyId && moduleName === "personal") {
            CURRENT_FACULTY_DATA.personal_documents = data.personal_documents || {};
            CURRENT_FACULTY_DATA.qualification_documents = data.qualification_documents || {};
            renderProfileDocuments(CURRENT_FACULTY_DATA);
        }

        alert("Submitted documents cleared successfully.");
    } catch (e) {
        alert(`Error: ${e.message}`);
    }
}

function filterResearchFaculty() {
    const query = document.getElementById("researchFacultySearch").value.toLowerCase().trim();
    const filtered = ALL_FACULTY_LIST.filter(f => (f.name || "").toLowerCase().includes(query) || (f.faculty_id || "").toLowerCase().includes(query));
    renderResearchFacultyList(filtered);
}

function backToResearchList() {
    navigateBack(() => {
        showSection('researchListView', true);
        showSection('researchDetailView', false);
        pushAppNavState(false);
    });
}

async function openResearchDetail(facultyId, facultyName, recordHistory = false) {
    CURRENT_FACULTY_ID = facultyId;
    showSection('researchListView', false);
    showSection('researchDetailView', true);
    
    const title = document.getElementById("researchDetailTitle");
    const body = document.getElementById("researchDetailBody");
    if (!title || !body) return;

    title.textContent = `R&D Assets for: ${facultyName}`;
    body.innerHTML = `<div class="loading-state">Loading assets...</div>`;

    try {
        const res = await fetch(`/api/research/faculty/${facultyId}`);
        if (!res.ok) throw new Error((await res.json()).error || 'Failed to fetch R&D assets');
        const assets = await res.json();
        CURRENT_FACULTY_DATA = { ...CURRENT_FACULTY_DATA, ...assets };
        body.innerHTML = renderCertifications(assets.certifications) + `
            ${renderBooks(assets.books || [])}
            ${renderResearchPapers(assets.research_papers || [])}`;
        if (recordHistory) pushAppNavState(false);
    } catch (e) {
        body.innerHTML = `<div class="error-state">${e.message}</div>`;
    }
}

function renderCertifications(certifications = []) {
    return `
        <div class="profile-card">
            <div class="card-head">
                <h3>Certifications</h3>
                <button class="small-btn" onclick="openCertificationModal()">+ Add New</button>
            </div>
            <div id="certificationsContainer">
                ${!certifications.length ? '<p class="empty-text">No certifications added.</p>' : `
                    <table class="data-table">
                        <thead><tr><th>Title</th><th>Issuer</th><th>Year</th><th>Status</th><th>Actions</th></tr></thead>
                        <tbody>
                            ${certifications.map(c => `
                                <tr>
                                    <td><a href="${c.file}" target="_blank">${c.title}</a></td>
                                    <td>${c.issuer}</td>
                                    <td>${c.year}</td>
                                    <td><span class="status-badge ${c.verified ? 'verified' : 'pending'}">${c.verified ? 'Verified' : 'Pending'}</span></td>
                                    <td class="action-buttons">
                                        <button class="small-btn" onclick='openCertificationModal(${JSON.stringify(c)})'>Edit</button>
                                        <button class="small-btn" onclick="toggleCertificationVerification('${c.cert_id}')">${c.verified ? 'Un-verify' : 'Verify'}</button>
                                        <button class="small-btn danger" onclick="deleteCertification('${c.cert_id}')">Delete</button>
                                    </td>
                                </tr>`).join('')}
                        </tbody>
                    </table>`}
            </div>
        </div>`;
}

function renderBooks(books = []) {
    return `
        <div class="profile-card">
            <div class="card-head">
                <h3>Books</h3>
                <button class="small-btn" onclick="openBookModal()">+ Add Book</button>
            </div>
            ${!books.length ? '<p class="empty-text">No books added.</p>' : `
                <table class="data-table">
                    <thead><tr><th>Title</th><th>Author</th><th>Year</th><th>Document</th><th>Actions</th></tr></thead>
                    <tbody>
                        ${books.map(b => `
                            <tr>
                                <td>${b.title || ''}</td>
                                <td>${b.author || ''}</td>
                                <td>${b.year || ''}</td>
                                <td>${b.file ? `<a href="${b.file}" target="_blank">View</a>` : '<span class="empty-text">No file</span>'}</td>
                                <td class="action-buttons">
                                    <button class="small-btn" onclick='openBookModal(${JSON.stringify(b)})'>Edit</button>
                                    <button class="small-btn danger" onclick="deleteBook('${b.book_id}')">Delete</button>
                                </td>
                            </tr>`).join('')}
                    </tbody>
                </table>`}
        </div>`;
}

function renderResearchPapers(papers = []) {
    return `
        <div class="profile-card">
            <div class="card-head">
                <h3>Research Papers</h3>
                <button class="small-btn" onclick="openPaperModal()">+ Add Paper</button>
            </div>
            ${!papers.length ? '<p class="empty-text">No research papers added.</p>' : `
                <table class="data-table">
                    <thead><tr><th>Title</th><th>Journal</th><th>Year</th><th>Document</th><th>Actions</th></tr></thead>
                    <tbody>
                        ${papers.map(p => `
                            <tr>
                                <td>${p.title || ''}</td>
                                <td>${p.journal || ''}</td>
                                <td>${p.year || ''}</td>
                                <td>${p.file ? `<a href="${p.file}" target="_blank">View</a>` : '<span class="empty-text">No file</span>'}</td>
                                <td class="action-buttons">
                                    <button class="small-btn" onclick='openPaperModal(${JSON.stringify(p)})'>Edit</button>
                                    <button class="small-btn danger" onclick="deletePaper('${p.paper_id}')">Delete</button>
                                </td>
                            </tr>`).join('')}
                    </tbody>
                </table>`}
        </div>`;
}

function openCertificationModal(cert = null) {
    const modal = document.getElementById("certificationModal");
    if (!modal) return;

    document.getElementById("certificationModalTitle").textContent = cert ? "Edit Certification" : "Add Certification";
    document.getElementById("certEditId").value = cert ? cert.cert_id : '';
    document.getElementById("certTitle").value = cert ? cert.title : '';
    document.getElementById("certIssuer").value = cert ? cert.issuer : '';
    document.getElementById("certYear").value = cert ? cert.year : '';
    
    const fileInput = document.getElementById("certFile");
    const fileStatus = document.getElementById("certFileStatus");
    fileInput.value = '';
    fileInput.required = !cert;
    fileStatus.innerHTML = cert ? `Current: <a href="${cert.file}" target="_blank">View File</a>. Re-upload to replace.` : '';
    
    modal.classList.add("active");
}

function closeCertificationModal() {
    document.getElementById("certificationModal")?.classList.remove("active");
}

async function saveCertification() {
    const certId = document.getElementById("certEditId").value;
    const isEditing = !!certId;

    const title = document.getElementById("certTitle").value;
    const issuer = document.getElementById("certIssuer").value;
    const year = document.getElementById("certYear").value;
    const file = document.getElementById("certFile").files[0];

    if (!title || !issuer || !year) return alert("Title, Issuer, and Year are required.");
    if (!isEditing && !file) return alert("Certificate file is required for new entries.");
    if (file) {
        const ext = (file.name.split(".").pop() || "").toLowerCase();
        if (!["pdf", "png", "jpg", "jpeg"].includes(ext)) {
            return alert("Certification file must be PDF or an image (PNG/JPG).");
        }
    }

    const formData = new FormData();
    formData.append("title", title);
    formData.append("issuer", issuer);
    formData.append("year", year);
    if (file) formData.append("file", file);

    const url = isEditing ? `/api/research/faculty/${CURRENT_FACULTY_ID}/certifications/${certId}` : `/api/research/faculty/${CURRENT_FACULTY_ID}/certifications`;
    const method = isEditing ? "PUT" : "POST";
    
    // Simplified: PUT with metadata, POST for creation with file.
    // Let's adjust the backend to handle file update on PUT.
    let body = formData;
    let headers = {};

    if(isEditing && !file) {
        body = JSON.stringify({ title, issuer, year });
        headers['Content-Type'] = 'application/json';
    }
    
    // For this implementation, we will require user to re-upload file on edit.
    if(isEditing) {
        // A real app might have a separate file-upload endpoint.
        // For simplicity, we'll just use POST for edits with files too.
        // This requires the backend to handle POST as an "upsert". Let's assume it doesn't.
        // The safest is to use PUT for metadata and POST for creation.
        // A file change during edit is complex. Let's disallow it for now.
        if (file) {
            alert("To change the file, please delete this certification and create a new one.");
            return;
        }
    }


    try {
        const res = await fetch(url, {
            method: isEditing ? 'PUT' : 'POST',
            body: isEditing ? JSON.stringify({title, issuer, year}) : formData,
            headers: isEditing ? {'Content-Type': 'application/json'} : {}
            });
        const result = await res.json();
        if (!res.ok) throw new Error(result.error || 'Save failed');
        
        alert("Certification saved!");
        closeCertificationModal();
        openResearchDetail(CURRENT_FACULTY_ID, ALL_FACULTY_LIST.find(f=>f.faculty_id === CURRENT_FACULTY_ID).name);
    } catch (e) {
        alert(`Error: ${e.message}`);
    }
}

async function deleteCertification(certId) {
    if (!confirm("Delete this certification?")) return;
    try {
        const res = await fetch(`/api/research/faculty/${CURRENT_FACULTY_ID}/certifications/${certId}`, { method: "DELETE" });
        if (!res.ok) throw new Error((await res.json()).error || 'Failed to delete');
        alert("Certification deleted.");
        openResearchDetail(CURRENT_FACULTY_ID, ALL_FACULTY_LIST.find(f=>f.faculty_id === CURRENT_FACULTY_ID).name);
    } catch (e) {
        alert(`Error: ${e.message}`);
    }
}

async function toggleCertificationVerification(certId) {
    try {
        const res = await fetch(`/api/research/faculty/${CURRENT_FACULTY_ID}/certifications/${certId}/verify`, { method: "POST" });
        const result = await res.json();
        if (!res.ok) throw new Error(result.error || 'Status update failed');
        alert(result.message);
        openResearchDetail(CURRENT_FACULTY_ID, ALL_FACULTY_LIST.find(f=>f.faculty_id === CURRENT_FACULTY_ID).name);
    } catch (e) {
        alert(`Error: ${e.message}`);
    }
}

function openBookModal(book = null) {
    const modal = document.getElementById("bookModal");
    if (!modal) return;
    document.getElementById("bookModalTitle").textContent = book ? "Edit Book" : "Add Book";
    document.getElementById("bookEditId").value = book ? book.book_id : "";
    document.getElementById("bookTitle").value = book ? (book.title || "") : "";
    document.getElementById("bookAuthor").value = book ? (book.author || "") : "";
    document.getElementById("bookPublisher").value = book ? (book.publisher || "") : "";
    document.getElementById("bookYear").value = book ? (book.year || "") : "";
    document.getElementById("bookFile").value = "";
    modal.classList.add("active");
}

function closeBookModal() {
    document.getElementById("bookModal")?.classList.remove("active");
}

async function saveBook() {
    const bookId = document.getElementById("bookEditId").value;
    const isEdit = !!bookId;
    const title = document.getElementById("bookTitle").value.trim();
    const author = document.getElementById("bookAuthor").value.trim();
    const publisher = document.getElementById("bookPublisher").value.trim();
    const year = document.getElementById("bookYear").value.trim();
    const file = document.getElementById("bookFile").files[0];

    if (!title) return alert("Book title is required.");
    if (file) {
        const ext = (file.name.split(".").pop() || "").toLowerCase();
        if (!["pdf", "doc", "docx"].includes(ext)) {
            return alert("Book document must be PDF, DOC, or DOCX (images are not allowed).");
        }
    }

    try {
        let res;
        if (isEdit && !file) {
            res = await fetch(`/api/research/faculty/${CURRENT_FACULTY_ID}/books/${bookId}`, {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ title, author, publisher, year })
            });
        } else {
            const fd = new FormData();
            fd.append("title", title);
            fd.append("author", author);
            fd.append("publisher", publisher);
            fd.append("year", year);
            if (file) fd.append("file", file);
            const url = isEdit
                ? `/api/research/faculty/${CURRENT_FACULTY_ID}/books/${bookId}`
                : `/api/research/faculty/${CURRENT_FACULTY_ID}/books`;
            const method = isEdit ? "PUT" : "POST";
            res = await fetch(url, { method, body: fd });
        }

        const data = await res.json();
        if (!res.ok) throw new Error(data.error || "Failed to save book");
        closeBookModal();
        openResearchDetail(CURRENT_FACULTY_ID, ALL_FACULTY_LIST.find(f => f.faculty_id === CURRENT_FACULTY_ID)?.name || "");
    } catch (e) {
        alert(`Error: ${e.message}`);
    }
}

async function deleteBook(bookId) {
    if (!confirm("Delete this book?")) return;
    try {
        const res = await fetch(`/api/research/faculty/${CURRENT_FACULTY_ID}/books/${bookId}`, { method: "DELETE" });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || "Failed to delete book");
        openResearchDetail(CURRENT_FACULTY_ID, ALL_FACULTY_LIST.find(f => f.faculty_id === CURRENT_FACULTY_ID)?.name || "");
    } catch (e) {
        alert(`Error: ${e.message}`);
    }
}

function openPaperModal(paper = null) {
    const modal = document.getElementById("paperModal");
    if (!modal) return;
    document.getElementById("paperModalTitle").textContent = paper ? "Edit Research Paper" : "Add Research Paper";
    document.getElementById("paperEditId").value = paper ? paper.paper_id : "";
    document.getElementById("paperTitle").value = paper ? (paper.title || "") : "";
    document.getElementById("paperJournal").value = paper ? (paper.journal || "") : "";
    document.getElementById("paperYear").value = paper ? (paper.year || "") : "";
    document.getElementById("paperDoi").value = paper ? (paper.doi || "") : "";
    document.getElementById("paperFile").value = "";
    modal.classList.add("active");
}

function closePaperModal() {
    document.getElementById("paperModal")?.classList.remove("active");
}

async function savePaper() {
    const paperId = document.getElementById("paperEditId").value;
    const isEdit = !!paperId;
    const title = document.getElementById("paperTitle").value.trim();
    const journal = document.getElementById("paperJournal").value.trim();
    const year = document.getElementById("paperYear").value.trim();
    const doi = document.getElementById("paperDoi").value.trim();
    const file = document.getElementById("paperFile").files[0];

    if (!title) return alert("Paper title is required.");
    if (file) {
        const ext = (file.name.split(".").pop() || "").toLowerCase();
        if (!["pdf", "doc", "docx"].includes(ext)) {
            return alert("Research paper document must be PDF, DOC, or DOCX (images are not allowed).");
        }
    }

    try {
        let res;
        if (isEdit && !file) {
            res = await fetch(`/api/research/faculty/${CURRENT_FACULTY_ID}/papers/${paperId}`, {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ title, journal, year, doi })
            });
        } else {
            const fd = new FormData();
            fd.append("title", title);
            fd.append("journal", journal);
            fd.append("year", year);
            fd.append("doi", doi);
            if (file) fd.append("file", file);
            const url = isEdit
                ? `/api/research/faculty/${CURRENT_FACULTY_ID}/papers/${paperId}`
                : `/api/research/faculty/${CURRENT_FACULTY_ID}/papers`;
            const method = isEdit ? "PUT" : "POST";
            res = await fetch(url, { method, body: fd });
        }

        const data = await res.json();
        if (!res.ok) throw new Error(data.error || "Failed to save paper");
        closePaperModal();
        openResearchDetail(CURRENT_FACULTY_ID, ALL_FACULTY_LIST.find(f => f.faculty_id === CURRENT_FACULTY_ID)?.name || "");
    } catch (e) {
        alert(`Error: ${e.message}`);
    }
}

async function deletePaper(paperId) {
    if (!confirm("Delete this research paper?")) return;
    try {
        const res = await fetch(`/api/research/faculty/${CURRENT_FACULTY_ID}/papers/${paperId}`, { method: "DELETE" });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || "Failed to delete paper");
        openResearchDetail(CURRENT_FACULTY_ID, ALL_FACULTY_LIST.find(f => f.faculty_id === CURRENT_FACULTY_ID)?.name || "");
    } catch (e) {
        alert(`Error: ${e.message}`);
    }
}

function renderExpertiseFacultyList(list) {
    const container = document.getElementById("expertiseFacultyListContainer");
    if (!container) return;
    if (!list || list.length === 0) {
        container.innerHTML = `<div class="empty-state">No faculty found.</div>`;
        return;
    }
    container.innerHTML = `
        <div class="table-wrapper">
            <table class="data-table">
                <thead><tr><th>ID</th><th>Name</th><th>Department</th><th>Actions</th></tr></thead>
                <tbody>
                    ${list.map(f => `
                        ${(() => {
                            const fid = String(f.faculty_id || "").trim();
                            const disabled = fid ? "" : "disabled title='Missing faculty id'";
                            const safeName = (f.name || '').replace(/'/g, "\\'");
                            return `
                        <tr>
                            <td>${fid || "N/A"}</td>
                            <td class="faculty-name">
                                <button class="link-faculty-name" type="button" ${disabled} onclick="openFacultyProfileFromList('${fid}')">${f.name}</button>
                            </td>
                            <td>${f.department || '-'}</td>
                            <td>
                                <div class="action-btn-group">
                                    <button class="small-btn" type="button" ${disabled} onclick="openExpertiseManager('${fid}', '${safeName}')">Manage Expertise</button>
                                </div>
                            </td>
                        </tr>`;
                        })()}
                    `).join('')}
                </tbody>
            </table>
        </div>`;
}

function openFacultyProfileFromList(facultyId) {
    if (!facultyId) return;
    const sectionId = document.querySelector(".page-section.active")?.id || null;
    openFacultyProfile(facultyId, false, sectionId);
}

function filterExpertiseFaculty() {
    const query = document.getElementById("expertiseFacultySearch")?.value.toLowerCase().trim() || "";
    const filtered = ALL_FACULTY_LIST.filter(f =>
        (f.name || "").toLowerCase().includes(query) ||
        (f.faculty_id || "").toLowerCase().includes(query)
    );
    renderExpertiseFacultyList(filtered);
}

async function openExpertiseManager(facultyId, facultyName) {
    if (!hasValidFacultyId(facultyId)) {
        alert("Invalid faculty ID for this row.");
        return;
    }
    CURRENT_EXPERTISE_FACULTY = { facultyId, facultyName };
    const modal = document.getElementById("expertiseManagerModal");
    const title = document.getElementById("expertiseManagerTitle");
    const body = document.getElementById("expertiseManagerBody");
    if (!modal || !title || !body) return;

    title.textContent = `Subject Expertise: ${facultyName}`;
    body.innerHTML = `<div class="loading-state">Loading expertise...</div>`;
    modal.classList.add("active");

    try {
        const [expRes, certRes] = await Promise.all([
            fetch(`/admin/faculty/${facultyId}/subject-expertise`),
            fetch(`/faculty/${facultyId}/certifications`)
        ]);
        const expData = await parseApiResponse(expRes);
        const certData = await parseApiResponse(certRes);
        if (!expRes.ok) throw new Error(expData.error || "Failed to load subject expertise");
        if (!certRes.ok) throw new Error(certData.error || "Failed to load certifications");
        CURRENT_EXPERTISE_SUBJECTS = expData.subject_expertise || [];
        CURRENT_EXPERTISE_CERTS = certData.certifications || [];
        renderExpertiseManager(CURRENT_EXPERTISE_SUBJECTS, CURRENT_EXPERTISE_CERTS);
    } catch (e) {
        body.innerHTML = `<div class="error-state">${e.message}</div>`;
    }
}

function closeExpertiseManagerModal() {
    document.getElementById("expertiseManagerModal")?.classList.remove("active");
}

function renderExpertiseManager(subjects, certs) {
    const body = document.getElementById("expertiseManagerBody");
    if (!body || !CURRENT_EXPERTISE_FACULTY) return;

    const certOptions = certs.map(c => `<option value="${c.cert_id}">${c.title} (${c.year})</option>`).join("");
    const linkedCertIds = new Set(subjects.flatMap(s => s.cert_ids || []));
    const unlinkedCerts = certs.filter(c => !linkedCertIds.has(c.cert_id));
    body.innerHTML = `
        <section class="expertise-panel">
            <div class="expertise-panel-head">
                <h3>Add Subject</h3>
            </div>
            <div class="expertise-add-row">
                <input type="text" id="newSubjectInput" class="profile-input" placeholder="e.g., Machine Learning">
                <button class="small-btn primary-btn-lite" type="button" onclick="addSubjectExpertise()">Add Subject</button>
            </div>
        </section>

        <section class="expertise-panel">
            <div class="expertise-panel-head">
                <h3>Quick Create From Certifications</h3>
            </div>
            ${unlinkedCerts.length === 0 ? '<p class="empty-text">All certifications are already linked.</p>' : `
                <div class="expertise-quick-list">
                    ${unlinkedCerts.map(c => `
                        <article class="expertise-quick-item">
                            <div class="expertise-quick-title">${c.title}</div>
                            <button class="small-btn" type="button" onclick="createSubjectFromCertification('${c.cert_id}')">Create + Link</button>
                        </article>
                    `).join('')}
                </div>
            `}
        </section>

        <section class="expertise-panel">
            <div class="expertise-panel-head expertise-panel-head-row">
                <h3>Subjects</h3>
                <input id="subjectSearchInput" class="profile-input expertise-search" placeholder="Search subject..." oninput="filterSubjectCards()">
            </div>
            <div id="subjectCardsWrap" class="expertise-cards-wrap">
            ${subjects.length === 0 ? '<p class="empty-text">No subjects added yet.</p>' : subjects.map(s => {
                const linked = (s.cert_ids || []).map(cid => certs.find(c => c.cert_id === cid)).filter(Boolean);
                const subjectEsc = (s.subject || '').replace(/'/g, "\\'");
                const selectId = `linkCert_${btoa(s.subject).replace(/=/g, '')}`;
                return `
                    <article class="subject-card" data-subject="${(s.subject || '').toLowerCase()}">
                        <header class="subject-card-head">
                            <strong>${s.subject}</strong>
                            <div class="subject-card-head-actions">
                                <span class="status-badge pending">${s.cert_count || 0} certs</span>
                                <button class="small-btn danger-btn" type="button" onclick="removeSubjectExpertise('${subjectEsc}')">Remove</button>
                            </div>
                        </header>
                        <div class="subject-link-row">
                            <select id="${selectId}" class="profile-input">
                                <option value="">Select certification to link</option>
                                ${certOptions}
                            </select>
                            <button class="small-btn" type="button" onclick="linkCertToSubject('${subjectEsc}', '${selectId}')">Link</button>
                        </div>
                        <div class="subject-linked-list">
                            ${linked.length === 0 ? '<span class="empty-text">No linked certifications</span>' : linked.map(c => `
                                <div class="subject-linked-item">
                                    <span>${c.title}</span>
                                    <button class="small-btn" type="button" onclick="unlinkCertFromSubject('${subjectEsc}', '${c.cert_id}')">Unlink</button>
                                </div>
                            `).join('')}
                        </div>
                    </article>
                `;
            }).join('')}
            </div>
        </section>
    `;
}

function filterSubjectCards() {
    const q = (document.getElementById("subjectSearchInput")?.value || "").toLowerCase().trim();
    document.querySelectorAll("#subjectCardsWrap .subject-card").forEach(card => {
        const subject = card.getAttribute("data-subject") || "";
        card.style.display = !q || subject.includes(q) ? "" : "none";
    });
}

async function addSubjectExpertise() {
    const subject = document.getElementById("newSubjectInput")?.value.trim();
    if (!subject || !CURRENT_EXPERTISE_FACULTY) return;
    const res = await fetch(`/admin/faculty/${CURRENT_EXPERTISE_FACULTY.facultyId}/subject-expertise`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ subject })
    });
    const data = await parseApiResponse(res);
    if (!res.ok) return alert(data.error || "Failed to add subject");
    openExpertiseManager(CURRENT_EXPERTISE_FACULTY.facultyId, CURRENT_EXPERTISE_FACULTY.facultyName);
}

async function createSubjectFromCertification(certId) {
    const cert = CURRENT_EXPERTISE_CERTS.find(c => c.cert_id === certId);
    if (!cert || !CURRENT_EXPERTISE_FACULTY) return;

    const proposed = (cert.title || "").trim();
    if (!proposed) return alert("Certification title is empty.");

    const addRes = await fetch(`/admin/faculty/${CURRENT_EXPERTISE_FACULTY.facultyId}/subject-expertise`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ subject: proposed })
    });
    const addData = await parseApiResponse(addRes);
    if (!addRes.ok && !String(addData.error || "").toLowerCase().includes("already exists")) {
        return alert(addData.error || "Failed to create subject");
    }

    const linkRes = await fetch(`/admin/faculty/${CURRENT_EXPERTISE_FACULTY.facultyId}/subject-expertise/${encodeURIComponent(proposed)}/link-cert/${encodeURIComponent(certId)}`, { method: "PUT" });
    const linkData = await parseApiResponse(linkRes);
    if (!linkRes.ok) return alert(linkData.error || "Failed to link certification");

    openExpertiseManager(CURRENT_EXPERTISE_FACULTY.facultyId, CURRENT_EXPERTISE_FACULTY.facultyName);
}

async function removeSubjectExpertise(subject) {
    if (!CURRENT_EXPERTISE_FACULTY) return;
    const res = await fetch(`/admin/faculty/${CURRENT_EXPERTISE_FACULTY.facultyId}/subject-expertise/${encodeURIComponent(subject)}`, { method: "DELETE" });
    const data = await parseApiResponse(res);
    if (!res.ok) return alert(data.error || "Failed to remove subject");
    openExpertiseManager(CURRENT_EXPERTISE_FACULTY.facultyId, CURRENT_EXPERTISE_FACULTY.facultyName);
}

async function linkCertToSubject(subject, selectId) {
    if (!CURRENT_EXPERTISE_FACULTY) return;
    const certId = document.getElementById(selectId)?.value;
    if (!certId) return;
    const res = await fetch(`/admin/faculty/${CURRENT_EXPERTISE_FACULTY.facultyId}/subject-expertise/${encodeURIComponent(subject)}/link-cert/${encodeURIComponent(certId)}`, { method: "PUT" });
    const data = await parseApiResponse(res);
    if (!res.ok) return alert(data.error || "Failed to link certification");
    openExpertiseManager(CURRENT_EXPERTISE_FACULTY.facultyId, CURRENT_EXPERTISE_FACULTY.facultyName);
}

async function unlinkCertFromSubject(subject, certId) {
    if (!CURRENT_EXPERTISE_FACULTY) return;
    const res = await fetch(`/admin/faculty/${CURRENT_EXPERTISE_FACULTY.facultyId}/subject-expertise/${encodeURIComponent(subject)}/unlink-cert/${encodeURIComponent(certId)}`, { method: "PUT" });
    const data = await parseApiResponse(res);
    if (!res.ok) return alert(data.error || "Failed to unlink certification");
    openExpertiseManager(CURRENT_EXPERTISE_FACULTY.facultyId, CURRENT_EXPERTISE_FACULTY.facultyName);
}

// ======================================================
// LOGOUT & SESSION
// ======================================================
async function logout(){
    try{ await fetch("/auth/logout", { method: "POST" }); } catch(e) {}
    window.location.href = "/login";
}

document.addEventListener("DOMContentLoaded", async ()=>{
    try{
        const res = await fetch("/auth/check-session");
        if(!res.ok) return window.location.href = "/login";
        const data = await res.json();
        CURRENT_ROLE = data.role || "admin";
        document.getElementById("roleBadge").textContent = CURRENT_ROLE.toUpperCase();
    }catch(e){ console.error("Session check failed:", e); }
    document.getElementById("photoUpload")?.addEventListener("change", handlePhotoUpload);

    // Admin profile photo: click to enlarge
    const profilePhoto = document.getElementById("profilePhoto");
    if (profilePhoto) {
        profilePhoto.addEventListener("click", () => {
            const src = profilePhoto.getAttribute("src") || "";
            openAdminPhotoLightbox(src);
        });
        profilePhoto.setAttribute("title", "Click to enlarge");
    }

    const lb = document.getElementById("adminPhotoLightbox");
    if (lb) {
        lb.addEventListener("click", (e) => {
            const t = e.target;
            if (t && t.closest && t.closest("[data-close='1']")) closeAdminPhotoLightbox();
        });
    }

    document.addEventListener("keydown", (e) => {
        if (e.key === "Escape") closeAdminPhotoLightbox();
    });
    window.addEventListener("focus", syncAdminActiveView);
    document.addEventListener("visibilitychange", () => {
        if (document.visibilityState === "visible") syncAdminActiveView();
    });
    setInterval(() => {
        if (document.visibilityState === "visible") syncAdminActiveView();
    }, 15000);

    bindEnterAdvance(
        [
            "profileName",
            "profileDept",
            "profileDesignation",
            "profileNormalizedRole",
            "profileEmail",
            "profilePhone",
            "profileUsername",
            "profilePassword",
            "profileOfficeRoom",
            "profileExtension"
        ],
        () => {
            if (IS_PROFILE_EDIT_MODE) saveProfile();
        }
    );

    goHome(false);
    NAV_INDEX = 0;
    pushAppNavState(true);
});

window.addEventListener("popstate", async (event) => {
    const state = event.state;
    if (!state || !state.appNav) return;
    await restoreFromHistoryState(state);
});


