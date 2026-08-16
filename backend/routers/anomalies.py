"""
GET /anomalies

Runs Isolation Forest over audit_logs and returns flagged sessions
with plain-English reasons. Newly-found anomalies are also persisted
to the `anomalies` collection (see ml/anomaly_detector.py), so
GET /admin/anomalies (routers/admin.py) reflects them too without
needing to re-run detection.
"""

from fastapi import APIRouter

from ml.anomaly_detector import detect_anomalies

router = APIRouter(tags=["Anomalies"])


@router.get("/anomalies")
async def get_anomalies():
    result = await detect_anomalies(persist=True)

    if result["skipped"]:
        return {
            "message": (
                f"Not enough session data yet for anomaly detection "
                f"(need at least 5 sessions, have {result['sessions_analyzed']})."
            ),
            "anomalies": [],
        }

    return {
        "sessions_analyzed": result["sessions_analyzed"],
        "anomalies": result["anomalies_found"],
        "count": len(result["anomalies_found"]),
    }
