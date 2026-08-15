"""
Simple health check endpoint. Useful to confirm the API is up and
that MongoDB is actually reachable, not just that Python imported ok.
"""

from fastapi import APIRouter
from database.connection import get_db

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health_check():
    db = get_db()
    await db.command("ping")
    return {
        "status": "ok",
        "database": "connected",
    }
