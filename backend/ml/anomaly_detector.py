"""
Isolation Forest anomaly detection over usage patterns.

Runs on audit_logs, aggregated per session_id into behavioral
features (request volume, how often things get blocked, average
threat severity, request pacing). Isolation Forest flags sessions
that look statistically unusual relative to the rest of the traffic
— not any single rule, but "this session's overall pattern doesn't
look like the others."

This deliberately works on top of audit_logs (which chat.py already
writes on every request) rather than needing new instrumentation.
"""

from collections import defaultdict
from datetime import datetime, timezone

import numpy as np
from sklearn.ensemble import IsolationForest

from database.connection import get_db

# Isolation Forest needs a reasonable number of samples to establish
# what "normal" looks like. Below this, flag nothing rather than
# overfit to noise from a handful of sessions.
MIN_SESSIONS_FOR_DETECTION = 5

FEATURE_NAMES = [
    "request_count",
    "blocked_ratio",
    "avg_threat_tier",
    "requests_per_minute",
]


def _build_session_features(logs: list[dict]) -> dict[str, dict]:
    """
    Groups audit_logs entries by session_id and computes one feature
    vector per session.
    """
    sessions = defaultdict(list)
    for log in logs:
        sessions[log["session_id"]].append(log)

    features = {}
    for session_id, entries in sessions.items():
        entries.sort(key=lambda e: e["timestamp"])

        request_count = len(entries)
        blocked_count = sum(
            1 for e in entries if e["status"] in ("Prompt Injection", "Harmful", "Jailbreak")
        )
        blocked_ratio = blocked_count / request_count
        avg_threat_tier = sum(e["threat_tier"] for e in entries) / request_count

        time_span_seconds = (entries[-1]["timestamp"] - entries[0]["timestamp"]).total_seconds()
        time_span_minutes = max(time_span_seconds / 60, 1 / 60)  # avoid div-by-zero for single requests
        requests_per_minute = request_count / time_span_minutes

        features[session_id] = {
            "user_id": entries[0]["user_id"],
            "request_count": request_count,
            "blocked_ratio": blocked_ratio,
            "avg_threat_tier": avg_threat_tier,
            "requests_per_minute": requests_per_minute,
        }

    return features


def _explain_anomaly(session_features: dict, all_features: list[dict]) -> str:
    """
    Isolation Forest tells us a session is unusual, not why. This
    picks the single feature furthest (in standard deviations) from
    the population mean, for a plain-English reason — same pattern as
    security/lime_explainer.py.
    """
    reasons = []

    for feature_name in FEATURE_NAMES:
        values = [f[feature_name] for f in all_features]
        mean = np.mean(values)
        std = np.std(values) or 1e-9  # avoid div-by-zero if all values identical
        z_score = (session_features[feature_name] - mean) / std
        reasons.append((abs(z_score), feature_name, z_score))

    reasons.sort(reverse=True)
    _, top_feature, top_z = reasons[0]

    direction = "unusually high" if top_z > 0 else "unusually low"

    readable = {
        "request_count": f"an {direction} number of requests in this session",
        "blocked_ratio": f"an {direction} proportion of blocked/flagged requests",
        "avg_threat_tier": f"{direction} average threat severity across requests",
        "requests_per_minute": f"an {direction} request rate (messages per minute)",
    }

    return readable.get(top_feature, "an unusual usage pattern").capitalize()


async def detect_anomalies(persist: bool = True) -> dict:
    """
    Run Isolation Forest over all audit_logs, grouped by session.

    Args:
        persist: if True, write newly-found anomalies to the
                 `anomalies` collection (skipping sessions already
                 flagged there, to avoid duplicate entries on repeat
                 runs).

    Returns:
        {
            "sessions_analyzed": int,
            "anomalies_found": [
                {"session_id": str, "user_id": str, "reason": str}, ...
            ],
            "skipped": bool,   # True if there wasn't enough data yet
        }
    """
    db = get_db()

    logs = [doc async for doc in db.audit_logs.find({})]
    session_features = _build_session_features(logs)

    if len(session_features) < MIN_SESSIONS_FOR_DETECTION:
        return {
            "sessions_analyzed": len(session_features),
            "anomalies_found": [],
            "skipped": True,
        }

    session_ids = list(session_features.keys())
    feature_matrix = np.array(
        [[session_features[sid][name] for name in FEATURE_NAMES] for sid in session_ids]
    )

    model = IsolationForest(contamination=0.1, random_state=42)
    predictions = model.fit_predict(feature_matrix)  # -1 = anomaly, 1 = normal

    all_feature_dicts = list(session_features.values())
    anomalies_found = []

    for session_id, prediction in zip(session_ids, predictions):
        if prediction != -1:
            continue

        sf = session_features[session_id]
        reason = _explain_anomaly(sf, all_feature_dicts)

        anomalies_found.append({
            "session_id": session_id,
            "user_id": sf["user_id"],
            "reason": reason,
        })

    if persist and anomalies_found:
        for anomaly in anomalies_found:
            existing = await db.anomalies.find_one({"session_id": anomaly["session_id"]})
            if existing:
                continue  # already flagged (e.g. from a prior run, or a jailbreak flag in chat.py)

            await db.anomalies.insert_one({
                "session_id": anomaly["session_id"],
                "user_id": anomaly["user_id"],
                "reason": anomaly["reason"],
                "flagged_at": datetime.now(timezone.utc),
            })

    return {
        "sessions_analyzed": len(session_features),
        "anomalies_found": anomalies_found,
        "skipped": False,
    }
