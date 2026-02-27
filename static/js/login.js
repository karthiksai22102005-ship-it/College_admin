// Store the page user was trying to access
const urlParams = new URLSearchParams(window.location.search);
const nextPage = urlParams.get('next') || null;

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

// ===============================
// LOGIN HANDLER (FIXED)
// ===============================
async function login() {
    const userIdEl = document.getElementById("user_id");
    const passwordEl = document.getElementById("password");
    const errorEl = document.getElementById("error-msg");
    const button = document.querySelector(".login-btn");

    const username = userIdEl.value.trim();
    const password = passwordEl.value.trim();

    errorEl.textContent = "";

    if (!username || !password) {
        errorEl.textContent = "User ID and Password required";
        return;
    }

    button.disabled = true;
    const originalText = button.innerHTML;
    button.innerHTML = "Signing in...";

    try {
        const response = await fetch("/auth/login", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            credentials: "include",
            body: JSON.stringify({
                username: username,
                password: password
            })
        });

        const data = await response.json();

        if (!response.ok) {
            errorEl.textContent = data.error || "Invalid credentials";
            return;
        }

        // Redirect based on role or to next page
        if (nextPage) {
            window.location.href = nextPage;
        } else if (data.role === "faculty") {
            window.location.href = "/faculty-dashboard";
        } else if (data.role === "admin") {
            window.location.href = "/admin-dashboard";
        } else {
            window.location.href = "/admin-dashboard";
        }

    } catch (error) {
        console.error("Login error:", error);
        errorEl.textContent = "Server not reachable";
    } finally {
        button.disabled = false;
        button.innerHTML = originalText;
    }
}

// FIELD-SPECIFIC ENTER BEHAVIOR + PASSWORD VISIBILITY
document.addEventListener("DOMContentLoaded", () => {
    const userIdEl = document.getElementById("user_id");
    const passwordEl = document.getElementById("password");
    const toggleEl = document.getElementById("togglePassword");

    if (toggleEl && passwordEl) {
        toggleEl.addEventListener("click", () => {
            const isHidden = passwordEl.type === "password";
            passwordEl.type = isHidden ? "text" : "password";
            toggleEl.setAttribute("aria-label", isHidden ? "Hide password" : "Show password");
        });
    }

    if (userIdEl && passwordEl) {
        userIdEl.addEventListener("keydown", (e) => {
            if (e.key !== "Enter") return;
            e.preventDefault();
            if (userIdEl.value.trim()) {
                passwordEl.focus();
            }
        });

        passwordEl.addEventListener("keydown", (e) => {
            if (e.key !== "Enter") return;
            e.preventDefault();
            if (userIdEl.value.trim() && passwordEl.value.trim()) {
                login();
            }
        });
    }
});
// ===============================
// FORGOT PASSWORD UI
// ===============================
document.addEventListener("DOMContentLoaded", () => {
    const link = document.getElementById("forgotLink");
    const roleEl = document.getElementById("resetRole");
    const dobEl = document.getElementById("resetDob");
    const resetPwdEl = document.getElementById("newPassword");
    const resetToggleEl = document.getElementById("toggleResetPassword");
    if (link) {
        link.addEventListener("click", (e) => {
            e.preventDefault();
            document.getElementById("forgotModal").style.display = "flex";
        });
    }
    if (roleEl && dobEl) {
        roleEl.addEventListener("change", () => {
            dobEl.style.display = roleEl.value === "faculty" ? "block" : "none";
        });
    }
    if (resetToggleEl && resetPwdEl) {
        resetToggleEl.addEventListener("click", () => {
            const isHidden = resetPwdEl.type === "password";
            resetPwdEl.type = isHidden ? "text" : "password";
            resetToggleEl.setAttribute("aria-label", isHidden ? "Hide password" : "Show password");
        });
    }
    bindEnterAdvance(["resetUserId", "resetRole", "resetDob", "newPassword"], () => {
        const modal = document.getElementById("forgotModal");
        if (modal && modal.style.display !== "none") resetPassword();
    });
});

function closeForgotModal() {
    document.getElementById("forgotModal").style.display = "none";
}

// ===============================
// RESET PASSWORD
// ===============================
async function resetPassword() {
    const userId = document.getElementById("resetUserId").value.trim();
    const role = (document.getElementById("resetRole")?.value || "faculty").trim();
    const dob = (document.getElementById("resetDob")?.value || "").trim();
    const newPass = document.getElementById("newPassword").value.trim();
    const msg = document.getElementById("resetMsg");

    msg.textContent = "";

    if (!userId || !newPass) {
        msg.style.color = "red";
        msg.textContent = "User ID and new password required";
        return;
    }
    if (role === "faculty" && !dob) {
        msg.style.color = "red";
        msg.textContent = "DOB is required for faculty reset";
        return;
    }

    try {
        const res = await fetch("/auth/forgot-password", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                username: userId,
                role: role,
                dob: dob,
                new_password: newPass
            })
        });

        const data = await res.json();

        if (!res.ok) {
            msg.style.color = "red";
            msg.textContent = data.error || "Reset failed";
            return;
        }

        msg.style.color = "green";
        msg.textContent = "Password reset successful";

        setTimeout(closeForgotModal, 1200);

    } catch (err) {
        msg.style.color = "red";
        msg.textContent = "Server error";
    }
}

