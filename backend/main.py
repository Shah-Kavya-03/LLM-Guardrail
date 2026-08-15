"""
FastAPI entry point for the Real-time LLM Input/Output Guardrail backend.

Run with:
    uvicorn main:app --reload --port 8000

Docs at:
    http://localhost:8000/docs
"""

import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database.connection import connect_to_mongo, close_mongo_connection
from routers import health, chat, logs, auth, conversations

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await connect_to_mongo()
    yield
    # Shutdown
    await close_mongo_connection()


app = FastAPI(
    title="LLM Guardrail API",
    description="Real-time LLM Input/Output Guardrail backend",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — the frontend is static HTML/JS served from a different
# origin/port than the API, so the browser needs this to allow calls.
cors_origins = os.getenv("CORS_ORIGINS", "*").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers — each feature area registers its own router here.
# As routers/chat.py, routers/logs.py etc. get built, add them below.
app.include_router(health.router)
app.include_router(chat.router)
app.include_router(logs.router)
app.include_router(auth.router)
app.include_router(conversations.router)


@app.get("/")
async def root():
    return {
        "service": "LLM Guardrail API",
        "status": "running",
        "docs": "/docs",
    }
