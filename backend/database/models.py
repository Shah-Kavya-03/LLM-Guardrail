"""
Collection schema reference for the llm_guardrail database.

MongoDB is schemaless, so these are plain dicts, not enforced models.
This file exists so every router/service builds documents with the
same shape instead of drifting. Keep it in sync with any field changes.

Collections:
    audit_logs     - one entry per processed prompt/response
    conversations  - full chat history grouped by session_id
    users           - registered users (passwords hashed, never plain)
    anomalies       - sessions flagged by the anomaly detector
    api_usage       - per-provider rate limit / usage tracking
"""

from datetime import datetime, timezone
from typing import Optional


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def new_audit_log(
    session_id: str,
    title: str,
    prompt_masked: str,
    response: Optional[str],
    model_used: Optional[str],
    api_used: Optional[str],
    status: str,
    threat_tier: int,
    lime_explanation: Optional[str],
    user_id: str,
) -> dict:
    """Shape of a document in the `audit_logs` collection."""
    return {
        "session_id": session_id,
        "title": title,
        "prompt_masked": prompt_masked,   # NEVER raw PII — masked only
        "response": response,
        "model_used": model_used,
        "api_used": api_used,
        "status": status,                 # Safe | Blocked | PII Detected | Harmful | Jailbreak
        "threat_tier": threat_tier,       # 1-5
        "lime_explanation": lime_explanation,
        "timestamp": now_utc(),
        "user_id": user_id,
    }


def new_conversation(session_id: str, user_id: str, model_used: str) -> dict:
    """Shape of a document in the `conversations` collection."""
    return {
        "session_id": session_id,
        "user_id": user_id,
        "messages": [],                   # list of {sender, text, timestamp}
        "status": "Protected",
        "model_used": model_used,
        "api_used": None,
        "created_at": now_utc(),
    }


def new_message(sender: str, text: str) -> dict:
    """One entry in a conversation's `messages` array."""
    return {
        "sender": sender,                 # "user" | "assistant"
        "text": text,
        "timestamp": now_utc(),
    }


def new_user(name: str, email: str, password_hashed: str, is_admin: bool = False) -> dict:
    """Shape of a document in the `users` collection."""
    return {
        "name": name,
        "email": email,
        "password_hashed": password_hashed,
        "created_at": now_utc(),
        "is_flagged": False,
        "is_admin": is_admin,
    }


def new_anomaly(session_id: str, user_id: str, reason: str) -> dict:
    """Shape of a document in the `anomalies` collection."""
    return {
        "session_id": session_id,
        "user_id": user_id,
        "reason": reason,
        "flagged_at": now_utc(),
    }


def new_api_usage(api_name: str) -> dict:
    """Shape of a document in the `api_usage` collection (one per provider)."""
    return {
        "api_name": api_name,
        "requests_count": 0,
        "tokens_used": 0,
        "last_used": None,
        "is_rate_limited": False,
        "rate_limit_reset_at": None,
    }
