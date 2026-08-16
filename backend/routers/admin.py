"""
GET /admin/users
GET /admin/stats
GET /admin/anomalies
PUT /admin/user/:user_id/flag

All routes require a valid JWT belonging to a user with is_admin=true
(see utils/auth.py's get_current_admin_user_id). Since signup never
sets is_admin=true (see database/models.py's default), you'll need
to manually flip a user to admin the first time — see the note at
the bottom of this file.
"""

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, Depends, HTTPException

from database.connection import get_db
from utils.auth import get_current_admin_user_id

router = APIRouter(prefix="/admin", tags=["Admin"])


def _serialize_user(doc: dict) -> dict:
    return {
        "user_id": str(doc["_id"]),
        "name": doc.get("name"),
        "email": doc.get("email"),
        "created_at": doc.get("created_at").isoformat() if doc.get("created_at") else None,
        "is_flagged": doc.get("is_flagged", False),
        "is_admin": doc.get("is_admin", False),
    }


@router.get("/users")
async def list_users(admin_id: str = Depends(get_current_admin_user_id)):
    """Returns every registered user, with basic stats per user."""
    db = get_db()

    users = []
    async for user_doc in db.users.find({}):
        user = _serialize_user(user_doc)

        # Per-user request count, for a quick "how active is this
        # user" column in the Admin Panel.
        user_id_str = str(user_doc["_id"])
        request_count = await db.audit_logs.count_documents({"user_id": user_id_str})
        user["request_count"] = request_count

        users.append(user)

    return {"users": users, "count": len(users)}


@router.get("/stats")
async def admin_stats(admin_id: str = Depends(get_current_admin_user_id)):
    """
    System-wide stats for the Admin Panel dashboard. This overlaps
    with GET /dashboard-stats (used by audit.html) but additionally
    includes user-level numbers that only make sense in an admin
    context.
    """
    db = get_db()

    total_users = await db.users.count_documents({})
    flagged_users = await db.users.count_documents({"is_flagged": True})
    total_requests = await db.audit_logs.count_documents({})
    total_conversations = await db.conversations.count_documents({})
    total_anomalies = await db.anomalies.count_documents({})

    status_breakdown = {}
    async for doc in db.audit_logs.aggregate(
        [{"$group": {"_id": "$status", "count": {"$sum": 1}}}]
    ):
        status_breakdown[doc["_id"]] = doc["count"]

    api_usage = {}
    async for doc in db.api_usage.find({}):
        api_usage[doc["api_name"].lower()] = {
            "requests": doc.get("requests_count", 0),
            "is_rate_limited": doc.get("is_rate_limited", False),
        }

    return {
        "total_users": total_users,
        "flagged_users": flagged_users,
        "total_requests": total_requests,
        "total_conversations": total_conversations,
        "total_anomalies": total_anomalies,
        "status_breakdown": status_breakdown,
        "api_usage": api_usage,
    }


@router.get("/anomalies")
async def list_anomalies(admin_id: str = Depends(get_current_admin_user_id)):
    """Returns all flagged anomalous sessions, most recent first."""
    db = get_db()

    anomalies = []
    async for doc in db.anomalies.find({}).sort("flagged_at", -1):
        anomalies.append({
            "id": str(doc["_id"]),
            "session_id": doc.get("session_id"),
            "user_id": doc.get("user_id"),
            "reason": doc.get("reason"),
            "flagged_at": doc.get("flagged_at").isoformat() if doc.get("flagged_at") else None,
        })

    return {"anomalies": anomalies, "count": len(anomalies)}


@router.put("/user/{user_id}/flag")
async def flag_user(user_id: str, admin_id: str = Depends(get_current_admin_user_id)):
    """Flags a user as suspicious. Toggles: calling this again un-flags them."""
    db = get_db()

    try:
        object_id = ObjectId(user_id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="Invalid user_id.")

    user_doc = await db.users.find_one({"_id": object_id})
    if user_doc is None:
        raise HTTPException(status_code=404, detail="User not found.")

    new_flag_state = not user_doc.get("is_flagged", False)

    await db.users.update_one(
        {"_id": object_id},
        {"$set": {"is_flagged": new_flag_state}},
    )

    return {"user_id": user_id, "is_flagged": new_flag_state}


# ---------------------------------------------------------------
# NOTE: making your first admin user
#
# Signup never sets is_admin=true (see database/models.py) — there's
# intentionally no self-service way to grant yourself admin through
# the API, since that would be a security hole. To promote your own
# account after signing up normally, run this once via mongosh or
# MongoDB Compass:
#
#   db.users.updateOne(
#       { email: "your@email.com" },
#       { $set: { is_admin: true } }
#   )
# ---------------------------------------------------------------
