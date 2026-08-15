
const API_BASE = "http://localhost:8000";

/**
 * Maps a backend threat_tier status to the frontend's existing
 * three-state display model: "Protected" (safe), "Blocked"
 * (injection/harmful/jailbreak), "Modified" (PII was masked).
 * This matches the status vocabulary already used throughout
 * script.js/audit.js/audit.css — no new states introduced.
 */
function mapBackendStatus(status){

    if(status === "PII Detected") return "Modified";
    if(status === "Safe") return "Protected";
    // Prompt Injection, Harmful, Jailbreak, Rate Limited all read as Blocked
    return "Blocked";

}

const sidebar = document.getElementById("sidebar");
const toggleSidebar = document.getElementById("toggleSidebar");

const signInButton = document.getElementById("signInButton");

const profileBtn = document.getElementById("profileBtn");

const profileDropdown = document.getElementById("profileDropdown");

const loginOverlay = document.getElementById("loginOverlay");

const signupOverlay = document.getElementById("signupOverlay");

const searchOverlay = document.getElementById("searchOverlay");

const overlay = document.getElementById("overlay");

const welcomeScreen = document.getElementById("welcomeScreen");

const chatContainer = document.getElementById("chatContainer");

const promptInput = document.getElementById("promptInput");

const sendBtn = document.getElementById("sendBtn");

const searchBtn = document.getElementById("searchBtn");

const recentChats = document.getElementById("recentChats");

const searchResults = document.getElementById("searchResults");

const welcomeHeading = document.getElementById("welcomeHeading");

const welcomeText = document.getElementById("welcomeText");

const profileName = document.getElementById("profileName");

const profileEmail = document.getElementById("profileEmail");

const usernameText = document.querySelector(".username");

const closeButtons = document.querySelectorAll(".closeModal");

const openSignup = document.getElementById("openSignup");

const backToLogin = document.getElementById("backToLogin");

const loginForm = document.getElementById("loginForm");

const signupForm = document.getElementById("signupForm");

const logoutButton = document.getElementById("logoutButton");

const chips = document.querySelectorAll(".chips button");

const logoutOverlay = document.getElementById("logoutOverlay");

let currentUser = null;

let authToken = null;

let conversations = [];

let currentConversation = null;

loadData();

toggleSidebar.addEventListener("click", () => {

    sidebar.classList.toggle("collapsed");

});

function openModal(modal){

    modal.classList.add("active");

}

function closeModal(modal){

    modal.classList.remove("active");

}

signInButton.addEventListener("click", () => {

    openModal(loginOverlay);

});

profileBtn.addEventListener("click", () => {

    if(currentUser){

        profileDropdown.classList.toggle("active");

    }else{

        openModal(loginOverlay);

    }

});

searchBtn.addEventListener("click",(e)=>{

    e.preventDefault();

    openModal(searchOverlay);

    renderSearch();

});

closeButtons.forEach(btn=>{

    btn.addEventListener("click", () => {

        const modal = btn.closest(".modal-overlay");

        if(modal){

            closeModal(modal);

        }

    });

});

window.addEventListener("click",(e)=>{

    if(e.target===loginOverlay){

        closeModal(loginOverlay);

    }

    if(e.target===signupOverlay){

        closeModal(signupOverlay);

    }

    if(e.target===searchOverlay){

        closeModal(searchOverlay);

    }

});

openSignup.addEventListener("click",(e)=>{

    e.preventDefault();

    closeModal(loginOverlay);

    openModal(signupOverlay);

});

backToLogin.addEventListener("click",(e)=>{

    e.preventDefault();

    closeModal(signupOverlay);

    openModal(loginOverlay);

});

loginForm.addEventListener("submit", async (e)=>{

    e.preventDefault();

    const email = loginForm.querySelector('input[type="email"]').value;
    const password = loginForm.querySelector('input[type="password"]').value;

    try{

        const res = await fetch(`${API_BASE}/auth/login`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email, password })
        });

        if(!res.ok){
            const err = await res.json().catch(() => ({}));
            toast(err.detail || "Login failed.", "error");
            return;
        }

        const data = await res.json();

        currentUser = {
            user_id: data.user_id,
            name: data.name,
            email: data.email
        };
        authToken = data.token;

        await refreshConversationsFromBackend();

        saveData();
        renderAuditLogs();

        updateUserUI();

        closeModal(loginOverlay);
        loginForm.reset();

        toast("Signed in successfully.","success");

    }catch(err){

        console.error("Login request failed:", err);
        toast("Could not reach the server. Is the backend running?", "error");

    }

});

signupForm.addEventListener("submit", async (e)=>{

    e.preventDefault();

    const name = signupForm.querySelector('input[type="text"]').value;
    const email = signupForm.querySelector('input[type="email"]').value;
    const passwordInputs = signupForm.querySelectorAll('input[type="password"]');
    const password = passwordInputs[0].value;
    const confirmPassword = passwordInputs[1].value;

    if(password !== confirmPassword){
        toast("Passwords do not match.", "error");
        return;
    }

    try{

        const res = await fetch(`${API_BASE}/auth/signup`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ name, email, password })
        });

        if(!res.ok){
            const err = await res.json().catch(() => ({}));
            toast(err.detail || "Signup failed.", "error");
            return;
        }

        const data = await res.json();

        currentUser = {
            user_id: data.user_id,
            name: data.name,
            email: data.email
        };
        authToken = data.token;

        conversations = [];

        saveData();
        renderAuditLogs();

        updateUserUI();

        closeModal(signupOverlay);
        signupForm.reset();

        toast("Account created.","success");

    }catch(err){

        console.error("Signup request failed:", err);
        toast("Could not reach the server. Is the backend running?", "error");

    }

});

logoutButton.addEventListener("click", async ()=>{

    await performLogout();

    toast("Logged out.","success");

});

async function performLogout(){

    try{
        await fetch(`${API_BASE}/auth/logout`, { method: "POST" });
    }catch(err){
        // Logout is stateless server-side (see auth.py) — a failed
        // network call here doesn't block clearing local state.
        console.warn("Logout request failed (clearing local session anyway):", err);
    }

    currentUser=null;
    authToken=null;
    conversations=[];
    currentConversation=null;

    chatContainer.innerHTML = "";
    chatContainer.classList.remove("active");
    welcomeScreen.style.display = "flex";

    saveData();
    renderAuditLogs();

    updateUserUI();
    renderRecentChats();

    profileDropdown.classList.remove("active");

}

function updateUserUI(){

    if(currentUser){

        usernameText.textContent=currentUser.name;

        profileName.textContent=currentUser.name;

        profileEmail.textContent=currentUser.email;

        welcomeHeading.textContent=`Hey, ${currentUser.name} 👋`;

        welcomeText.textContent="How can I help you securely today?";

        signInButton.style.display="none";

    }else{

        usernameText.textContent="Log In";

        profileName.textContent="Guest User";

        profileEmail.textContent="Not Signed In";

        welcomeHeading.textContent="Welcome to AI Guardrail";

        welcomeText.textContent="Your prompts are automatically protected against prompt injection, sensitive information leakage, and unsafe AI responses.";

        signInButton.style.display="block";

    }

}

function loadData(){

    const user=localStorage.getItem("guardrailUser");

    const token=localStorage.getItem("guardrailToken");

    const chats=localStorage.getItem("guardrailChats");

    if(user){

        currentUser=JSON.parse(user);

    }

    if(token){

        authToken=token;

    }

    if(chats){

        conversations=JSON.parse(chats);

    }

}

function saveData(){

    localStorage.setItem("guardrailUser",JSON.stringify(currentUser));

    localStorage.setItem("guardrailToken", authToken || "");

    localStorage.setItem("guardrailChats",JSON.stringify(conversations));

}

updateUserUI();


/* ==========================================
   SEND MESSAGE
========================================== */

sendBtn.addEventListener("click", sendMessage);

promptInput.addEventListener("keydown", (e) => {

    if (e.key === "Enter" && !e.shiftKey) {

        e.preventDefault();

        sendMessage();

    }

});

/* ==========================================
   AUTO RESIZE TEXTAREA
========================================== */

promptInput.addEventListener("input", () => {

    promptInput.style.height = "auto";

    promptInput.style.height = promptInput.scrollHeight + "px";

});

/* ==========================================
   SEND MESSAGE FUNCTION
========================================== */

function sendMessage() {

    const text = promptInput.value.trim();

    if (!text) return;

    if (welcomeScreen.style.display !== "none") {

        welcomeScreen.style.display = "none";

        chatContainer.classList.add("active");

    }

    if (!currentConversation) {

        currentConversation = {

            id: Date.now(),

            title: text.length > 35 ? text.substring(0, 35) + "..." : text,

            model: "Gemini 2.5 Flash",

            status: "Protected",

            messages: [],

            pinned: false

        };
        conversations.unshift(currentConversation);

        renderRecentChats();

    }

    currentConversation.messages.push({

        sender: "user",

        text: text

    });

    addMessage("user", text);

    promptInput.value = "";

    promptInput.style.height = "auto";

    saveData();
    renderAuditLogs();

    showTyping();

}

/* ==========================================
   ADD MESSAGE
========================================== */

function addMessage(sender, text) {

    const message = document.createElement("div");

    message.className = `message ${sender}-message`;

    const icon = sender === "user"

        ? "fa-user"

        : "fa-shield-halved";

    message.innerHTML = `

        <div class="message-avatar">

            <i class="fa-solid ${icon}"></i>

        </div>

        <div class="message-content">

            ${escapeHTML(text)}

        </div>

    `;

    chatContainer.appendChild(message);

    chatContainer.scrollTop = chatContainer.scrollHeight;

}

/* ==========================================
   TYPING INDICATOR
========================================== */

function showTyping() {

    const typing = document.createElement("div");

    typing.className = "message ai-message";

    typing.id = "typingIndicator";

    typing.innerHTML = `

        <div class="message-avatar">

            <i class="fa-solid fa-shield-halved"></i>

        </div>

        <div class="message-content">

            <div class="typing">

                <span></span>

                <span></span>

                <span></span>

            </div>

        </div>

    `;

    chatContainer.appendChild(typing);

    chatContainer.scrollTop = chatContainer.scrollHeight;

    sendToBackend(typing);

}

/* ==========================================
   REAL AI RESPONSE (backend call)
========================================== */

function sendToBackend(typingEl) {

    const lastUserMessage = currentConversation.messages
        .filter(m => m.sender === "user")
        .slice(-1)[0];

    fetch(`${API_BASE}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            prompt: lastUserMessage.text,
            session_id: String(currentConversation.id),
            user_id: currentUser?.user_id || "guest"
        })
    })
    .then(res => res.json())
    .then(data => {

        typingEl.remove();

        const displayStatus = mapBackendStatus(data.status);

        // Blocked/rate-limited requests: show the explanation instead
        // of a null response.
        const replyText = data.response
            ? data.response
            : (data.blocked_reason || data.lime_explanation || "Your message could not be processed.");

        currentConversation.messages.push({
            sender: "ai",
            text: replyText
        });

        addMessage("ai", replyText);

        currentConversation.status = displayStatus;
        currentConversation.model = data.model_used || currentConversation.model;
        currentConversation.lastLimeExplanation = data.lime_explanation;

        saveData();
        renderAuditLogs();

    })
    .catch(err => {

        typingEl.remove();

        const errorText = "Could not reach the guardrail backend. Is the server running?";

        currentConversation.messages.push({
            sender: "ai",
            text: errorText
        });

        addMessage("ai", errorText);

        console.error("Chat request failed:", err);

        saveData();
        renderAuditLogs();

    });

}

/* ==========================================
   RECENT CHATS
========================================== */

/* ==========================================
   SYNC CONVERSATIONS FROM BACKEND
   (only for logged-in users — guest chats stay
   local-only, since backend "guest" sessions
   aren't meaningfully scoped to one browser)
========================================== */

async function refreshConversationsFromBackend(){

    if(!currentUser?.user_id){
        return;
    }

    try{

        const res = await fetch(`${API_BASE}/conversations?user_id=${encodeURIComponent(currentUser.user_id)}`);
        const data = await res.json();

        conversations = (data.conversations || []).map(conv => ({
            id: conv.session_id,
            title: conv.title || "New Chat",
            model: conv.model_used || "Gemini 2.5 Flash",
            status: "Protected",
            messages: [],
            pinned: false,
            loaded: false   // full messages fetched lazily when opened
        }));

        renderRecentChats();

    }catch(err){

        console.error("Failed to load conversations:", err);

    }

}

/* ==========================================
   RECENT CHATS
========================================== */

function renderRecentChats() {

    // Always keep pinned chats at the top
    sortConversations();

    recentChats.innerHTML = "";

    if (conversations.length === 0) {

        recentChats.innerHTML = `

            <div class="empty-recents">

                No recent chats yet.

            </div>

        `;

        return;

    }


    conversations.forEach(chat => {

        const chatItem = document.createElement("div");

        chatItem.className = "chat-item";


        // Add pinned style
        if (chat.pinned) {

            chatItem.classList.add("pinned");

        }


        chatItem.innerHTML = `

            <span class="chat-title">

                ${escapeHTML(chat.title)}

            </span>


            <button class="chat-menu-btn">

                <i class="fa-solid fa-ellipsis"></i>

            </button>


            <div class="chat-menu">

                <button class="pin-chat">

                    <i class="fa-solid fa-thumbtack"></i>

                    ${chat.pinned ? "Unpin Chat" : "Pin Chat"}

                </button>


                <button class="delete-chat">

                    <i class="fa-solid fa-trash"></i>

                    Delete Chat

                </button>

            </div>

        `;


        // Open chat
        chatItem.querySelector(".chat-title").onclick = () => {

            openConversation(chat.id);

        };


        const menuBtn = chatItem.querySelector(".chat-menu-btn");

        const menu = chatItem.querySelector(".chat-menu");


        // Open menu
        menuBtn.onclick = (e) => {

            e.stopPropagation();


            document.querySelectorAll(".chat-menu").forEach(m => {

                if (m !== menu) {

                    m.classList.remove("active");

                }

            });


            menu.classList.toggle("active");

        };


        // Pin / Unpin chat
        chatItem.querySelector(".pin-chat").onclick = (e) => {

            e.stopPropagation();


            chat.pinned = !chat.pinned;


            saveData();
            renderAuditLogs();


            renderRecentChats();


            toast(

                chat.pinned 
                ? "Chat pinned 📌" 
                : "Chat unpinned",

                "success"

            );

        };


        // Delete chat
        chatItem.querySelector(".delete-chat").onclick = async (e) => {

            e.stopPropagation();


            conversations = conversations.filter(c => c.id !== chat.id);


            if (currentConversation && currentConversation.id === chat.id) {

                currentConversation = null;

                chatContainer.innerHTML = "";

                chatContainer.classList.remove("active");

                welcomeScreen.style.display = "flex";

            }


            saveData();
            renderAuditLogs();

            renderRecentChats();

            renderSearch();


            toast(

                "Chat deleted",

                "success"

            );

            try{
                await fetch(`${API_BASE}/conversations/${encodeURIComponent(chat.id)}`, {
                    method: "DELETE"
                });
            }catch(err){
                console.warn("Backend delete failed (chat still removed locally):", err);
            }

        };


        recentChats.appendChild(chatItem);


    });

}


/* ==========================================
   SORT PINNED CHATS FIRST
========================================== */

function sortConversations() {

    conversations.sort((a, b) => {


        // Pinned chats first

        if ((b.pinned || false) !== (a.pinned || false)) {

            return (b.pinned || false) - (a.pinned || false);

        }


        // Newest chats first

        return b.id - a.id;


    });

}

/* ==========================================
   OPEN CHAT
========================================== */

async function openConversation(id) {

    const chat = conversations.find(c => c.id === id);

    if (!chat) return;

    currentConversation = chat;

    welcomeScreen.style.display = "none";

    chatContainer.classList.add("active");

    chatContainer.innerHTML = "";

    // Backend-sourced sidebar entries start with empty messages —
    // fetch the full history the first time this chat is opened.
    if (chat.loaded === false) {

        try{

            const res = await fetch(`${API_BASE}/conversations/${encodeURIComponent(id)}`);
            const data = await res.json();

            chat.messages = (data.messages || []).map(m => ({
                sender: m.sender === "assistant" ? "ai" : "user",
                text: m.text
            }));
            chat.loaded = true;

        }catch(err){

            console.error("Failed to load conversation history:", err);

        }

    }

    chat.messages.forEach(msg => {

        addMessage(msg.sender, msg.text);

    });

}

/* ==========================================
   INITIALIZE
========================================== */

renderRecentChats();

/**
 * Supports two entry points from audit.html, since it links back
 * here rather than duplicating the login modal / chat view:
 *   index.html?auth=login   -> auto-opens the sign-in modal
 *   index.html?open=<id>    -> auto-opens that specific conversation
 */
(async function handleEntryParams(){

    const params = new URLSearchParams(window.location.search);

    if(currentUser?.user_id){

        await refreshConversationsFromBackend();

    }

    if(params.get("auth") === "login" && !currentUser){

        openModal(loginOverlay);

    }

    const openId = params.get("open");

    if(openId){

        // Guests: the chat may already be in local `conversations`.
        // Logged-in users: refreshConversationsFromBackend() above
        // already populated it. Either way, try to open it.
        const exists = conversations.find(c => String(c.id) === String(openId));

        if(exists){
            openConversation(exists.id);
        }

    }

    // Clean the query string so a page refresh doesn't re-trigger this.
    if(params.toString()){
        window.history.replaceState({}, "", window.location.pathname);
    }

})();


/* ==========================================
   SEARCH FUNCTIONALITY
========================================== */

const searchInput = document.getElementById("searchInput");

searchInput.addEventListener("input", renderSearch);

function renderSearch() {

    const query = searchInput.value.trim().toLowerCase();

    searchResults.innerHTML = "";

    const filtered = conversations.filter(chat =>
        chat.title.toLowerCase().includes(query)
    );

    if (filtered.length === 0) {

        searchResults.innerHTML = `

            <div class="no-results">

                No chats found.

            </div>

        `;

        return;

    }

    filtered.forEach(chat => {

        const div = document.createElement("div");

        div.className = "search-item";

        div.textContent = chat.title;

        div.onclick = () => {

            openConversation(chat.id);

            closeModal(searchOverlay);

        };

        searchResults.appendChild(div);

    });

}

/* ==========================================
   NEW CHAT
========================================== */

document.querySelector(".new-chat-btn").addEventListener("click", () => {

    currentConversation = null;

    chatContainer.innerHTML = "";

    chatContainer.classList.remove("active");

    welcomeScreen.style.display = "flex";

    promptInput.value = "";

    promptInput.style.height = "auto";

});

/* ==========================================
   TOAST NOTIFICATIONS
========================================== */

function toast(message, type = "success") {

    const container = document.getElementById("toastContainer");

    const item = document.createElement("div");

    item.className = `toast ${type}`;

    item.textContent = message;

    container.appendChild(item);

    setTimeout(() => {

        item.style.opacity = "0";

        item.style.transform = "translateX(40px)";

        setTimeout(() => {

            item.remove();

        },300);

    },2500);

}

/* ==========================================
   ESCAPE HTML
========================================== */

function escapeHTML(text){

    const div = document.createElement("div");

    div.innerText = text;

    return div.innerHTML;

}

/* ==========================================
   CLICK OUTSIDE PROFILE DROPDOWN
========================================== */

document.addEventListener("click",(e)=>{

    if(

        !profileDropdown.contains(e.target) &&
        !profileBtn.contains(e.target)

    ){

        profileDropdown.classList.remove("active");

    }

});

/* ==========================================
   ESC CLOSES MODALS
========================================== */

document.addEventListener("keydown",(e)=>{

    if(e.key==="Escape"){

        closeModal(loginOverlay);

        closeModal(signupOverlay);

        closeModal(searchOverlay);

        profileDropdown.classList.remove("active");

    }

});

/* ==========================================
   CHIP BUTTONS
========================================== */

chips.forEach(chip=>{

    chip.addEventListener("click",()=>{

        promptInput.value=chip.textContent;

        promptInput.focus();

        promptInput.dispatchEvent(new Event("input"));

    });

});

/* ==========================================
   LOAD LAST CHAT
========================================== */

if(conversations.length>0){

    renderRecentChats();

}

/* ==========================================
   LOAD USER UI
========================================== */

updateUserUI();

/* ==========================================
   PLACE CURSOR
========================================== */

window.addEventListener("load",()=>{

    promptInput.focus();

});

/* ==========================================
   SAVE BEFORE LEAVING
========================================== */

window.addEventListener("beforeunload",()=>{

    saveData();
    renderAuditLogs();

});

document.addEventListener("click", () => {

    document.querySelectorAll(".chat-menu").forEach(menu => {

        menu.classList.remove("active");

    });

});

/* ==========================================
   ACCOUNT + SETTINGS MODALS
========================================== */

const accountBtn = document.getElementById("accountBtn");
const settingsBtn = document.getElementById("settingsBtn");

const accountOverlay = document.getElementById("accountOverlay");
const settingsOverlay = document.getElementById("settingsOverlay");

const accountContent = document.getElementById("accountContent");
const settingsContent = document.getElementById("settingsContent");
const logoutConfirm = document.getElementById("logoutConfirm");
const logoutClose = document.getElementById("logoutClose");

/* ==========================================
   OPEN MODALS
========================================== */

accountBtn.addEventListener("click", () => {

    profileDropdown.classList.remove("active");

    openModal(accountOverlay);

    loadAccountPage("information");

});

settingsBtn.addEventListener("click", () => {

    profileDropdown.classList.remove("active");

    openModal(settingsOverlay);

    loadSettingsPage("model");

});

/* ==========================================
   CLOSE ACCOUNT / SETTINGS
========================================== */

accountOverlay.querySelector(".closeModal").addEventListener("click", () => {

    closeModal(accountOverlay);

});

settingsOverlay.querySelector(".closeModal").addEventListener("click", () => {

    closeModal(settingsOverlay);

});

window.addEventListener("click", (e) => {

    if (e.target === accountOverlay) {

        closeModal(accountOverlay);

    }

    if (e.target === settingsOverlay) {

        closeModal(settingsOverlay);

    }

});

/* ==========================================
   ACCOUNT SIDEBAR
========================================== */

const accountTabs = accountOverlay.querySelectorAll(".settings-tab");

accountTabs.forEach(tab => {

    tab.addEventListener("click", () => {

        accountTabs.forEach(btn => {

            btn.classList.remove("active");

        });

        tab.classList.add("active");

        loadAccountPage(tab.dataset.account);

    });

});

/* ==========================================
   SETTINGS SIDEBAR
========================================== */

const settingsTabs = settingsOverlay.querySelectorAll(".settings-tab");

settingsTabs.forEach(tab => {

    tab.addEventListener("click", () => {

        settingsTabs.forEach(btn => {

            btn.classList.remove("active");

        });

        tab.classList.add("active");

        loadSettingsPage(tab.dataset.setting);

    });

});

/* ==========================================
   ACCOUNT PLACEHOLDERS
========================================== */

function loadAccountPage(page){

    switch(page){

        case "information":

            accountContent.innerHTML = `

                <div class="settings-placeholder">

                    <i class="fa-solid fa-id-card"></i>

                    <h2>Personal Information</h2>

                    <p>

                        This section is under development.

                    </p>

                </div>

            `;

        break;

        case "password":

            accountContent.innerHTML = `

                <div class="settings-placeholder">

                    <i class="fa-solid fa-key"></i>

                    <h2>Change Password</h2>

                    <p>

                        This section is under development.

                    </p>

                </div>

            `;

        break;

        case "switch":

            accountContent.innerHTML = `

                <div class="settings-placeholder">

                    <i class="fa-solid fa-right-left"></i>

                    <h2>Switch Account</h2>

                    <p>

                        This section is under development.

                    </p>

                </div>

            `;

        break;

        case "signout":

            openModal(logoutOverlay);

        break;


    }

}

/* ==========================================
   SETTINGS PLACEHOLDERS
========================================== */

function loadSettingsPage(page){

    switch(page){

        case "model":

            settingsContent.innerHTML = `

                <div class="settings-placeholder">

                    <i class="fa-solid fa-robot"></i>

                    <h2>AI Model</h2>

                    <p>

                        This section is under development.

                    </p>

                </div>

            `;

        break;

        case "version":

            settingsContent.innerHTML = `

                <div class="settings-placeholder">

                    <i class="fa-solid fa-shield-halved"></i>

                    <h2>Guardrail Version</h2>

                    <p>

                        This section is under development.

                    </p>

                </div>

            `;

        break;

        case "history":

            settingsContent.innerHTML = `

                <div class="settings-placeholder">

                    <i class="fa-solid fa-trash"></i>

                    <h2>Clear Chat History</h2>

                    <p>

                        This section is under development.

                    </p>

                </div>

            `;

        break;

        case "highlight":

            settingsContent.innerHTML = `

                <div class="settings-placeholder">

                    <i class="fa-solid fa-triangle-exclamation"></i>

                    <h2>Highlight Suspicious Content</h2>

                    <p>

                        This section is under development.

                    </p>

                </div>

            `;

        break;

        case "theme":

            settingsContent.innerHTML = `

                <div class="settings-placeholder">

                    <i class="fa-solid fa-moon"></i>

                    <h2>Theme</h2>

                    <p>

                        This section is under development.

                    </p>

                </div>

            `;

        break;

        case "accent":

            settingsContent.innerHTML = `

                <div class="settings-placeholder">

                    <i class="fa-solid fa-palette"></i>

                    <h2>Accent Colour</h2>

                    <p>

                        This section is under development.

                    </p>

                </div>

            `;

        break;

    }

}




/* ==========================================
   ACCOUNT + SETTINGS INITIALIZATION
========================================== */

function resetAccountTabs() {

    accountTabs.forEach(tab => {

        tab.classList.remove("active");

    });

    const first = accountOverlay.querySelector('[data-account="information"]');

    if(first){

        first.classList.add("active");

    }

}

function resetSettingsTabs() {

    settingsTabs.forEach(tab => {

        tab.classList.remove("active");

    });

    const first = settingsOverlay.querySelector('[data-setting="model"]');

    if(first){

        first.classList.add("active");

    }

}

/* ==========================================
   OPEN DEFAULT PAGE EVERY TIME
========================================== */

if(accountBtn){

    accountBtn.addEventListener("click",()=>{

        resetAccountTabs();

        loadAccountPage("information");

    });

}

if(settingsBtn){

    settingsBtn.addEventListener("click",()=>{

        resetSettingsTabs();

        loadSettingsPage("model");

    });

}

/* ==========================================
   ESC CLOSES NEW WINDOWS
========================================== */

document.addEventListener("keydown",(e)=>{

    if(e.key==="Escape"){

        closeModal(accountOverlay);

        closeModal(settingsOverlay);

    }

});

/* ==========================================
   PREVENT DROPDOWN WHEN MODALS OPEN
========================================== */

function closeEverything(){

    profileDropdown.classList.remove("active");

    closeModal(accountOverlay);

    closeModal(settingsOverlay);

}

document.addEventListener("click",(e)=>{

    if(

        !profileDropdown.contains(e.target) &&

        !profileBtn.contains(e.target)

    ){

        profileDropdown.classList.remove("active");

    }

});

/* ==========================================
   PLACEHOLDER HELPERS
========================================== */

function comingSoon(title,icon){

    return `

        <div class="settings-placeholder">

            <i class="fa-solid ${icon}"></i>

            <h2>${title}</h2>

            <p>

                This section is under development.

            </p>

        </div>

    `;

}

/* ==========================================
   FUTURE FUNCTIONS
========================================== */

function updateTheme(theme){

    console.log("Theme selected:",theme);

}

function updateAccent(color){

    console.log("Accent selected:",color);

}

function clearChatHistory(){

    console.log("Clear history");

}

function switchAccount(){

    console.log("Switch account");

}



/* ==========================================
   OPTIONAL LOADING ANIMATION
========================================== */

function showSettingsLoading(container){

    container.innerHTML=`

        <div class="settings-placeholder">

            <i class="fa-solid fa-spinner fa-spin"></i>

            <h2>Loading...</h2>

        </div>

    `;

}

/* ==============================
   LOGOUT POPUP
============================== */

logoutClose.addEventListener("click", () => {

    closeModal(logoutOverlay);

});

logoutConfirm.addEventListener("click", async () => {

    await performLogout();

    closeModal(logoutOverlay);
    closeModal(accountOverlay);
    closeModal(settingsOverlay);

    toast("Signed out successfully.");

});

/* ==========================================
   READY
========================================== */

console.log("Account & Settings Loaded");

/* ==========================================
   AUDIT LOGS
========================================== */

function getAuditStats() {

    const total = conversations.length;

    const blocked = conversations.filter(c => c.status === "Blocked").length;

    const modified = conversations.filter(c => c.status === "Modified").length;

    const safe = conversations.filter(c => c.status === "Protected").length;

    return {

        total,

        safe,

        blocked,

        modified

    };

}

function renderAuditTable() {

    const tableBody = document.getElementById("auditTableBody");

    if (!tableBody) return;

    tableBody.innerHTML = "";

    conversations.forEach(chat => {

        const row = document.createElement("tr");

        row.innerHTML = `

            <td>${chat.id}</td>

            <td>${escapeHTML(chat.title)}</td>

            <td>${chat.model || "Gemini 2.5 Flash"}</td>

            <td>
                <span class="status ${chat.status.toLowerCase()}">
                    ${chat.status}
                </span>
            </td>

        `;

        tableBody.appendChild(row);

    });

}

function updateAuditCards() {

    const stats = getAuditStats();

    const total = document.getElementById("totalRequests");
    const safe = document.getElementById("safeRequests");
    const blocked = document.getElementById("blockedRequests");
    const modified = document.getElementById("modifiedResponses");

    if(total) total.textContent = stats.total;
    if(safe) safe.textContent = stats.safe;
    if(blocked) blocked.textContent = stats.blocked;
    if(modified) modified.textContent = stats.modified;

}

function renderAuditLogs(){

    updateAuditCards();

    renderAuditTable();

}

window.addEventListener("load",()=>{

    renderAuditLogs();

});

/* ==========================================
   BACKEND INTEGRATION STATUS
========================================== */

/*
Connected to the FastAPI backend at API_BASE (see top of file).

/chat, /logs, /dashboard-stats, /auth/*, and /conversations are all
wired up. Logged-in users' sidebar chats come from the real backend
(GET /conversations) and sync on login/page-load; full message
history for a chat loads lazily the first time it's opened.

KNOWN GAP: no route on the backend actually checks the JWT token yet
— auth.py issues tokens, but chat.py/conversations.py don't verify
who's calling. Fine for a single-user dev/demo setup; before treating
this as multi-user-safe, add a dependency that decodes the token
(utils/auth.py's decode_access_token) and rejects/scopes requests
accordingly.

Guest (not logged in) chats remain fully local/localStorage-only —
not synced to the sidebar from the backend, since the backend's
"guest" user_id is shared across every guest, not scoped per browser.
*/

/* ==========================================
   AI GUARDRAIL
   SCRIPT COMPLETE
========================================== */

