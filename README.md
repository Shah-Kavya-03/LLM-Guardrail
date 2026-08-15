# Real-time LLM Input/Output Guardrail

A full-stack guardrail system that sits between a user and an LLM,
scanning every prompt and response for PII, toxicity, and prompt
injection/jailbreak attempts before allowing it through — with a
five-tier threat classification, automatic rotation across 5 free
LLM providers, and a full audit trail for DPDP Act 2023 compliance.

```
├── backend/     FastAPI + MongoDB — the guardrail pipeline and API
└── frontend/    Plain HTML/CSS/JS — chat UI + audit dashboard
```

---

## Project structure

**`backend/`** — see `backend/README.md` for the day-to-day startup
checklist. Quick summary:
- `main.py` — FastAPI app entry point
- `routers/` — one file per API area (`chat`, `logs`, `auth`, `conversations`, ...)
- `security/` — PII masking (Presidio), toxicity scoring (Detoxify), injection/jailbreak detection, five-tier classification
- `llm/` — provider clients (Gemini + 4 OpenAI-compatible providers) and the rotation logic
- `database/` — MongoDB connection + collection schemas
- `DEPLOYMENT.md` — full deployment plan (Hugging Face Spaces + MongoDB Atlas)

**`frontend/`**
- `index.html` / `js/script.js` — the chat interface, connects to the backend's `/chat`, `/auth/*`, and `/conversations` endpoints
- `audit.html` / `js/audit.js` — the audit dashboard, connects to `/logs` and `/dashboard-stats`
- `css/` — styling (`style.css`, `audit.css`)

---

## Running the project locally

**1. Backend** (see `backend/README.md` for full detail):
```bash
cd backend
venv\Scripts\activate        # Windows
source venv/bin/activate     # Ubuntu
uvicorn main:app --reload --port 8000
```
Confirm it's up: `http://localhost:8000/health`

**2. Frontend:**
Just open `frontend/index.html` directly in your browser — no build step, no server required. It talks to the backend at `http://localhost:8000` (see `API_BASE` at the top of `js/script.js` / `js/audit.js` — change this if you deploy the backend elsewhere).

---

## One-time setup (new machine / fresh clone)

```bash
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt --no-cache-dir
python -m spacy download en_core_web_lg
copy .env.example .env
```
Then fill in `.env` with your real MongoDB URI and LLM API keys — see `backend/.env.example` for the full list of variables and what each one does.

**MongoDB must be running** (Community Server installed locally, or point `MONGO_URI` at an Atlas cluster).

---

## Security notes

- `.env` is git-ignored — **never commit real API keys**. `.env.example` holds placeholders only.
- `backend/venv/` is git-ignored — don't commit it; `requirements.txt` is what lets anyone rebuild it.
- Raw PII is never stored in MongoDB — only Presidio-masked text (DPDP Act 2023 requirement).

---

## Build status

See `backend/README.md`'s checklist for the step-by-step backend build
progress (steps 1–13). As of now: steps 1–8 are complete (core
pipeline, provider rotation, logs/dashboard, auth, conversation
history), plus both frontend pages are wired to real backend data.
Remaining: admin endpoints, anomaly detection, PDF reports, settings
endpoints, and final deployment.
