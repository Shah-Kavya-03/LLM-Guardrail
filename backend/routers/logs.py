"""
GET /logs and GET /dashboard-stats.

These power audit.html's table and summary cards, replacing the
localStorage reads in audit.js with real data from the audit_logs
collection.
"""

from collections import defaultdict
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Query

from database.connection import get_db

router = APIRouter(tags=["Logs & Dashboard"])


def _serialize_log(doc: dict) -> dict:
    """Convert a MongoDB audit_logs document into JSON-safe output."""
    return {
        "id": str(doc["_id"]),
        "session_id": doc.get("session_id"),
        "title": doc.get("title"),
        "prompt_masked": doc.get("prompt_masked"),
        "response": doc.get("response"),
        "model_used": doc.get("model_used"),
        "api_used": doc.get("api_used"),
        "status": doc.get("status"),
        "threat_tier": doc.get("threat_tier"),
        "lime_explanation": doc.get("lime_explanation"),
        "timestamp": doc.get("timestamp").isoformat() if doc.get("timestamp") else None,
        "user_id": doc.get("user_id"),
    }


@router.get("/logs")
async def get_logs(
    limit: int = Query(200, ge=1, le=1000),
    user_id: str | None = None,
):
    """
    Returns audit log entries, most recent first.

    Optional `user_id` filter, and `limit` (default 200, capped at
    1000) so a growing collection doesn't return unbounded data to
    the frontend table.
    """
    db = get_db()
    query = {"user_id": user_id} if user_id else {}

    cursor = db.audit_logs.find(query).sort("timestamp", -1).limit(limit)
    logs = [_serialize_log(doc) async for doc in cursor]

    return {"logs": logs, "count": len(logs)}


@router.get("/dashboard-stats")
async def get_dashboard_stats():
    """
    Returns aggregate stats for the audit dashboard: totals by status,
    threats by type, threats by hour (last 24h), and per-provider
    usage/rate-limit status.
    """
    db = get_db()

    total = await db.audit_logs.count_documents({})
    safe = await db.audit_logs.count_documents({"status": "Safe"})
    pii_detected = await db.audit_logs.count_documents({"status": "PII Detected"})
    blocked = await db.audit_logs.count_documents(
        {"status": {"$in": ["Prompt Injection", "Harmful", "Jailbreak"]}}
    )
    jailbreak = await db.audit_logs.count_documents({"status": "Jailbreak"})
    # "Modified" maps to PII Detected in the original frontend's three-state
    # model (Protected/Blocked/Modified) — see conversations.status.
    modified = pii_detected

    # Threats by type — every status bucket, for a breakdown chart.
    threats_by_type = {}
    async for doc in db.audit_logs.aggregate(
        [{"$group": {"_id": "$status", "count": {"$sum": 1}}}]
    ):
        threats_by_type[doc["_id"]] = doc["count"]

    # Threats by hour, last 24 hours — for a time-series chart.
    since = datetime.now(timezone.utc) - timedelta(hours=24)
    hourly_counts = defaultdict(int)
    async for doc in db.audit_logs.find({"timestamp": {"$gte": since}}):
        hour_bucket = doc["timestamp"].strftime("%Y-%m-%dT%H:00")
        hourly_counts[hour_bucket] += 1
    threats_by_hour = [
        {"hour": hour, "count": count}
        for hour, count in sorted(hourly_counts.items())
    ]

    # Per-provider usage breakdown.
    api_usage_breakdown = {}
    async for doc in db.api_usage.find({}):
        api_usage_breakdown[doc["api_name"].lower()] = {
            "requests": doc.get("requests_count", 0),
            "tokens": doc.get("tokens_used", 0),
            "is_rate_limited": doc.get("is_rate_limited", False),
        }

    return {
        "total": total,
        "safe": safe,
        "blocked": blocked,
        "modified": modified,
        "pii_detected": pii_detected,
        "jailbreak": jailbreak,
        "threats_by_type": threats_by_type,
        "threats_by_hour": threats_by_hour,
        "api_usage_breakdown": api_usage_breakdown,
    }
