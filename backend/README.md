# LLM Guardrail Backend

## Every time you sit down to work on this project

1. **Check MongoDB is running**
   - `Win` key → search "Services" → find **MongoDB Server** → confirm Status = **Running**
   - Not running? Right-click it → **Start**

2. **Open a terminal, go to the project folder**
   ```bash
   cd path\to\llm-guardrail-backend
   ```

3. **Activate the virtual environment**
   ```bash
   venv\Scripts\activate
   ```
   Confirm you see `(venv)` at the start of your prompt — packages won't be found without this.

4. **Start the server**
   ```bash
   uvicorn main:app --reload --port 8000
   ```

5. **Confirm it's working**
   - `http://localhost:8000/health` → should return `{"status": "ok", "database": "connected"}`
   - `http://localhost:8000/docs` → interactive API docs

## To stop working
- `Ctrl+C` in the terminal running uvicorn
- MongoDB can keep running in the background (fine to leave it) or stop it from the Services app

## One-time setup (already done — don't repeat unless on a new machine)
- `pip install -r requirements.txt`
- `python -m spacy download en_core_web_lg`
- `.env` created from `.env.example`, `MONGO_URI` and `GEMINI_API_KEY` filled in
- MongoDB Community Server installed as a Windows service

## Build progress
- [x] Step 1-2: FastAPI + MongoDB connection, `.env` config
- [ ] Step 3: `POST /chat` — Presidio → toxicity → LLM pipeline
- [ ] Step 4: API rotation (Gemini → Groq → Cerebras → NVIDIA → Mistral)
- [ ] Step 5: Five-tier threat classification + LIME
- [ ] Step 6: `GET /logs`, `GET /dashboard-stats`
- [ ] Step 7: Auth endpoints
- [x] Step 8: Conversation history endpoints
- [x] Step 9: Admin endpoints
- [x] Step 10: Anomaly detection
- [x] Step 11: PDF reports
- [ ] Step 12: Settings endpoints
- [ ] Step 13: Final CORS + testing
