# Deployment Plan

Target stack: **Hugging Face Spaces (Docker SDK)** for the backend,
**MongoDB Atlas** for the database, **Netlify/Vercel** for the static
frontend.

---

## 1. ML model placement — prompt injection detection

**Decision:** the injection/jailbreak detector runs in **rules mode**
locally, **ML mode** in deployment. This is controlled by a single
environment variable, not a code change.

| | Local dev | Deployment |
|---|---|---|
| `INJECTION_DETECTOR_MODE` | `rules` | `ml` |
| Model | none | `deepset/deberta-v3-base-injection` (Hugging Face) |
| Where | `security/injection_detector.py` | same file, same function |
| Load time | instant | model downloads on first request after container start (lazy-loaded, not at import) |

**Why lazy-loaded:** if `_get_ml_classifier()` ran at import time,
every local `uvicorn --reload` restart would try to load the model
even in rules mode. It's only imported/loaded the first time
`detect_injection()` is actually called with mode="ml" — so local
dev stays fast, and the deployed container only pays the load cost
once, on its first real request.

**Why this split instead of ML everywhere:** the ML model needs
`transformers` + a downloaded checkpoint (~500MB). Loading that on
every local `--reload` restart during active development would be
slow and pointless when testing unrelated code. Deployment only
restarts occasionally, so the one-time load cost there is fine.

**Action needed before deployment:** set `INJECTION_DETECTOR_MODE=ml`
in the Space's secrets (see section 3). No code change required —
this is exactly why the flag exists.

**Known gap:** the current ML mode doesn't distinguish "jailbreak"
from generic "injection" (see comment in `_detect_ml()`) — both map
to the injection tier. Rules mode still separately detects jailbreak
patterns. Acceptable for v1; a dedicated jailbreak-classification
step is a fair v2 addition once real deployment traffic shows whether
this distinction actually matters in practice.

---

## 2. MongoDB — local to Atlas

- [ ] Create a free Atlas cluster (M0 tier) at https://www.mongodb.com/cloud/atlas
- [ ] Add a database user (username/password) under **Database Access**
- [ ] Under **Network Access**, allow access from anywhere (`0.0.0.0/0`) —
      Spaces containers don't have a fixed IP, so IP allowlisting a
      specific address isn't practical here
- [ ] Copy the connection string from **Connect → Drivers** — looks like:
      `mongodb+srv://<user>:<password>@cluster0.xxxxx.mongodb.net/`
- [ ] This becomes the new `MONGO_URI` secret (section 3) — **nothing
      else changes**. `database/connection.py` already reads
      `MONGO_URI`/`MONGO_DB_NAME` from the environment; it doesn't
      know or care whether that's `localhost` or Atlas.

---

## 3. Environment variables / secrets

Locally these live in `.env`. In deployment, **do not ship a `.env`
file** — set each of these individually in **Space → Settings →
Variables and secrets**:

| Variable | Local value | Deployment value |
|---|---|---|
| `MONGO_URI` | `mongodb://localhost:27017` | Atlas connection string |
| `MONGO_DB_NAME` | `llm_guardrail` | `llm_guardrail` (unchanged) |
| `GEMINI_API_KEY` | your key | same key (or a separate prod key) |
| `GROQ_API_KEY`, `CEREBRAS_API_KEY`, `NVIDIA_API_KEY`, `MISTRAL_API_KEY` | your keys | same |
| `SECRET_KEY` | dev placeholder | a real random secret — generate with `python -c "import secrets; print(secrets.token_hex(32))"` |
| `CORS_ORIGINS` | `http://localhost:5500,...` | your deployed frontend URL, e.g. `https://your-app.netlify.app` |
| `INJECTION_DETECTOR_MODE` | `rules` | `ml` |

---

## 4. Hugging Face Spaces — container specifics

- [ ] Space SDK must be **Docker** (not Gradio/Streamlit — those are
      for simpler demo UIs, not a full FastAPI backend)
- [ ] App **must listen on port `7860`** — HF Spaces' required port.
      Change the uvicorn command accordingly (see Dockerfile below)
- [ ] Filesystem is **read-only except `/tmp`** — any model cache
      (spaCy, Hugging Face transformers, Detoxify) must be redirected
      to `/tmp` via environment variables in the Dockerfile, or the
      container will fail to load models at runtime
- [ ] Remove `--reload` from the uvicorn start command — that flag is
      for local development only and adds unnecessary overhead in
      production
- [ ] Public Spaces expose code and logs publicly. If that's not
      acceptable, use a Private Space instead — but note that then
      requires a Hugging Face access token for anyone (including
      teammates) to reach the API

### Dockerfile (create at project root)

```dockerfile
FROM python:3.11-slim

# Redirect all model caches to /tmp — the only writable directory
# on Hugging Face Spaces.
ENV HF_HOME=/tmp/huggingface \
    TRANSFORMERS_CACHE=/tmp/huggingface \
    XDG_CACHE_HOME=/tmp/cache \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN python -m spacy download en_core_web_sm

COPY . .

EXPOSE 7860

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]
```

Note: uses `en_core_web_sm` (not `_lg`) to keep the image smaller and
startup faster — see section 5.

### README.md YAML header (required by HF Spaces, add to top of README.md)

```yaml
---
title: LLM Guardrail Backend
emoji: 🛡️
colorFrom: blue
colorTo: gray
sdk: docker
app_port: 7860
---
```

---

## 5. Other necessary code/config changes

- [ ] **spaCy model**: switch `en_core_web_lg` → `en_core_web_sm` in
      the Dockerfile's download step. The large model adds real
      memory/startup weight for accuracy gains that don't matter much
      at this project's scale — this was flagged back at initial setup
      as the fallback option if `_lg` ever caused issues, and it's the
      right default for a constrained container
- [ ] **Frontend `script.js` / `audit.js`**: change
      `http://localhost:8000` to the deployed Space's public URL
      (e.g. `https://your-username-llm-guardrail.hf.space`)
- [ ] **CORS**: confirmed above (`CORS_ORIGINS`), but double check
      after deploying the frontend — the exact deployed URL (with
      `https://`, no trailing slash) must match exactly
- [ ] **`.gitignore`**: confirm `.env` is still excluded before
      pushing to the Space's git repo — secrets go through the HF
      dashboard, never committed

---

## 6. Deployment-day order of operations

1. Set up MongoDB Atlas, get connection string
2. Push code to the Hugging Face Space (Docker SDK)
3. Add all secrets in Space settings (section 3)
4. Set `INJECTION_DETECTOR_MODE=ml`
5. Wait for build to finish, check Space logs for startup errors
6. Hit `https://<your-space>.hf.space/health` to confirm Mongo connects
7. Deploy frontend to Netlify/Vercel, update its API base URL
8. Update `CORS_ORIGINS` to match the real deployed frontend URL
9. Full end-to-end test: safe prompt, PII prompt, injection prompt,
   from the actual deployed frontend
