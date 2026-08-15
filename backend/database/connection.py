"""
MongoDB connection manager.

Uses Motor (the async MongoDB driver) so database calls never block
FastAPI's event loop. Connection is opened once on app startup and
closed once on shutdown — see main.py's lifespan handler.
"""

import os
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase


class MongoDB:
    """Holds the single Motor client/database instance for the app."""

    client: AsyncIOMotorClient | None = None
    db: AsyncIOMotorDatabase | None = None


mongodb = MongoDB()


async def connect_to_mongo():
    """Open the MongoDB connection. Call once, on app startup."""
    mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    db_name = os.getenv("MONGO_DB_NAME", "llm_guardrail")

    mongodb.client = AsyncIOMotorClient(mongo_uri)
    mongodb.db = mongodb.client[db_name]

    # Fail fast and loudly if MongoDB isn't reachable, rather than
    # silently deferring the error to the first query.
    await mongodb.client.admin.command("ping")
    print(f"[MongoDB] Connected -> {mongo_uri} (db: {db_name})")

    await ensure_indexes()


async def close_mongo_connection():
    """Close the MongoDB connection. Call once, on app shutdown."""
    if mongodb.client:
        mongodb.client.close()
        print("[MongoDB] Connection closed")


def get_db() -> AsyncIOMotorDatabase:
    """
    Dependency-friendly accessor for the database instance.

    Usage in a route:
        from database.connection import get_db
        db = get_db()
        await db.audit_logs.find_one(...)
    """
    if mongodb.db is None:
        raise RuntimeError(
            "MongoDB is not connected yet. "
            "Did the app startup lifespan run?"
        )
    return mongodb.db


async def ensure_indexes():
    """
    Create indexes the app relies on. Safe to call every startup —
    create_index is a no-op if an identical index already exists.
    """
    db = mongodb.db

    await db.audit_logs.create_index("session_id")
    await db.audit_logs.create_index("user_id")
    await db.audit_logs.create_index("timestamp")

    await db.conversations.create_index("session_id", unique=True)
    await db.conversations.create_index("user_id")

    await db.users.create_index("email", unique=True)

    await db.anomalies.create_index("session_id")
    await db.anomalies.create_index("user_id")

    await db.api_usage.create_index("api_name", unique=True)

    print("[MongoDB] Indexes ensured")
