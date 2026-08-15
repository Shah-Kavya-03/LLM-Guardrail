/* ==========================================
   AUDIT LOGS
========================================== */

const API_BASE = "http://localhost:8000";

let auditLogs = [];      // audit_logs entries -> the table + summary cards
let sidebarChats = [];   // real conversations -> the sidebar

const tableBody = document.getElementById("auditTableBody");
const emptyState = document.getElementById("emptyAudit");

const searchInput = document.getElementById("searchLogs");

const totalRequests = document.getElementById("totalRequests");
const safeRequests = document.getElementById("safeRequests");
const blockedRequests = document.getElementById("blockedRequests");
const modifiedResponses = document.getElementById("modifiedResponses");

/**
 * Same mapping used in script.js — keeps the audit table's status
 * badges consistent with the chat page's status vocabulary
 * (Protected / Blocked / Modified).
 */
function mapBackendStatus(status){

    if(status === "PII Detected") return "Modified";
    if(status === "Safe") return "Protected";
    return "Blocked";

}

/* ==========================================
   AUTH STATE
   Reads the SAME localStorage keys script.js
   writes on index.html, so signing in on one
   page is reflected on both.
========================================== */

let currentUser = null;

function loadAuthState(){

    const user = localStorage.getItem("guardrailUser");

    if(user){
        try{
            currentUser = JSON.parse(user);
        }catch{
            currentUser = null;
        }
    }

}

function updateProfileUI(){

    const usernameEl = document.getElementById("auditUsername");
    const subEl = document.getElementById("auditUserSub");
    const logoutBtn = document.getElementById("auditLogoutBtn");

    if(!usernameEl) return;

    if(currentUser){

        usernameEl.textContent = currentUser.name;
        subEl.textContent = currentUser.email;
        logoutBtn.style.display = "inline-flex";

    }else{

        usernameEl.textContent = "Log In";
        subEl.textContent = "Guest User";
        logoutBtn.style.display = "none";

    }

}

const profileArea = document.getElementById("profileArea");

if(profileArea){

    profileArea.addEventListener("click", (e) => {

        if(e.target.closest("#auditLogoutBtn")) return; // handled separately

        if(!currentUser){
            // audit.html has no login modal of its own — reuse
            // index.html's, opened automatically via ?auth=login
            window.location.href = "index.html?auth=login";
        }

    });

}

const auditLogoutBtn = document.getElementById("auditLogoutBtn");

if(auditLogoutBtn){

    auditLogoutBtn.addEventListener("click", async (e) => {

        e.stopPropagation();

        try{
            await fetch(`${API_BASE}/auth/logout`, { method: "POST" });
        }catch(err){
            console.warn("Logout request failed (clearing local session anyway):", err);
        }

        localStorage.removeItem("guardrailUser");
        localStorage.removeItem("guardrailToken");

        currentUser = null;
        updateProfileUI();

        await loadSidebarChats();

    });

}

/* ==========================================
   LOAD DATA (from backend, not localStorage)
========================================== */

async function loadLogs(){

    try{

        const res = await fetch(`${API_BASE}/logs`);
        const data = await res.json();

        auditLogs = (data.logs || []).map(log => ({
            id: log.session_id,
            title: log.title || "(untitled)",
            model: log.model_used || "—",
            status: mapBackendStatus(log.status)
        }));

    }catch(err){

        console.error("Failed to load audit logs:", err);
        auditLogs = [];

    }

}

async function loadDashboardStats(){

    try{

        const res = await fetch(`${API_BASE}/dashboard-stats`);
        const stats = await res.json();

        totalRequests.textContent = stats.total ?? 0;
        safeRequests.textContent = stats.safe ?? 0;
        blockedRequests.textContent = stats.blocked ?? 0;
        modifiedResponses.textContent = stats.pii_detected ?? 0;

    }catch(err){

        console.error("Failed to load dashboard stats:", err);

    }

}

/* ==========================================
   RECENT CHATS (real conversations, not
   audit log entries — matches index.html)
========================================== */

async function loadSidebarChats(){

    const recentChatsEl = document.getElementById("recentChats");

    if(!recentChatsEl) return;

    if(!currentUser?.user_id){

        // Guests don't have a backend-scoped chat list on this page
        // either (see script.js's note on shared "guest" user_id) —
        // point them at the chat page instead of showing nothing.
        recentChatsEl.innerHTML = `
            <div class="empty-recents">
                <a href="index.html" style="color:inherit;">
                    Sign in on the chat page to see your history here.
                </a>
            </div>
        `;
        sidebarChats = [];
        return;

    }

    try{

        const res = await fetch(`${API_BASE}/conversations?user_id=${encodeURIComponent(currentUser.user_id)}`);
        const data = await res.json();

        sidebarChats = data.conversations || [];

    }catch(err){

        console.error("Failed to load conversations:", err);
        sidebarChats = [];

    }

    renderRecentChats();

}

function renderRecentChats(){

    const recentChatsEl = document.getElementById("recentChats");

    if(!recentChatsEl) return;

    recentChatsEl.innerHTML = "";

    if(sidebarChats.length === 0){

        if(currentUser?.user_id){
            recentChatsEl.innerHTML = `
                <div class="empty-recents">
                    No recent chats yet.
                </div>
            `;
        }

        return;

    }

    sidebarChats.forEach(chat => {

        const div = document.createElement("div");

        div.className = "chat-item";

        div.innerHTML = `
            <span class="chat-title">
                ${escapeHTML(chat.title)}
            </span>
        `;

        // Opening a chat's full transcript happens on index.html —
        // this page only lists them.
        div.style.cursor = "pointer";
        div.onclick = () => {
            window.location.href = `index.html?open=${encodeURIComponent(chat.session_id)}`;
        };

        recentChatsEl.appendChild(div);

    });

}

function escapeHTML(str){

    const div = document.createElement("div");
    div.textContent = str ?? "";
    return div.innerHTML;

}

/* ==========================================
   TABLE
========================================== */

function renderAuditTable(data = auditLogs){

    tableBody.innerHTML = "";

    if(data.length === 0){

        emptyState.style.display = "flex";

        return;

    }

    emptyState.style.display = "none";

    data.forEach(chat=>{

        const row = document.createElement("tr");

        row.innerHTML = `

            <td>${chat.id}</td>

            <td>${chat.title}</td>

            <td>${chat.model || "Gemini 2.5 Flash"}</td>

            <td>

                <span class="status ${(
                    chat.status || "Protected"
                ).toLowerCase()}">

                    ${chat.status || "Protected"}

                </span>

            </td>

        `;

        tableBody.appendChild(row);

    });

}

/* ==========================================
   SEARCH
========================================== */

if(searchInput){

    searchInput.addEventListener("input",()=>{

        const value = searchInput.value.trim().toLowerCase();

        const filtered = auditLogs.filter(chat=>{

            return (

                String(chat.id).toLowerCase().includes(value)

                ||

                chat.title.toLowerCase().includes(value)

                ||

                (chat.model || "").toLowerCase().includes(value)

                ||

                (chat.status || "").toLowerCase().includes(value)

            );

        });

        renderAuditTable(filtered);

    });

}

/* ==========================================
   LOAD PAGE
========================================== */

async function loadAuditPage(){

    loadAuthState();
    updateProfileUI();

    await loadLogs();
    renderAuditTable();

    await loadDashboardStats();

    await loadSidebarChats();

}

window.addEventListener("load", loadAuditPage);

window.addEventListener("focus", loadAuditPage);

document.addEventListener("visibilitychange",()=>{

    if(!document.hidden){

        loadAuditPage();

    }

});