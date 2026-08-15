"""
GET /conversations?user_id=...
GET /conversations/:session_id
DELETE /conversations/:session_id

Powers the future Universal Sidebar: listing a user's past chats,
reopening one, and deleting one.
"""

from fastapi import APIRouter, HTTPException

from database.connection import get_db

router = APIRouter(prefix="/conversations", tags=["Conversations"])


def _serialize_conversation(doc: dict, include_messages: bool = False) -> dict:
    result = {
        "session_id": doc.get("session_id"),
        "user_id": doc.get("user_id"),
        "status": doc.get("status"),
        "model_used": doc.get("model_used"),
        "api_used": doc.get("api_used"),
        "created_at": doc.get("created_at").isoformat() if doc.get("created_at") else None,
        "message_count": len(doc.get("messages", [])),
        # A short preview title for sidebar list items — first user
        # message, truncated, so the sidebar doesn't need a separate
        # "title" field synced from audit_logs.
        "title": _preview_title(doc.get("messages", [])),
    }
    if include_messages:
        result["messages"] = [
            {
                "sender": m["sender"],
                "text": m["text"],
                "timestamp": m["timestamp"].isoformat() if m.get("timestamp") else None,
            }
            for m in doc.get("messages", [])
        ]
    return result


def _preview_title(messages: list[dict]) -> str:
    for m in messages:
        if m.get("sender") == "user":
            text = m.get("text", "")
            return text[:50] + ("..." if len(text) > 50 else "")
    return "New Chat"


@router.get("")
async def list_conversations(user_id: str):
    """Returns all conversations for a user, most recent first."""
    db = get_db()

    cursor = db.conversations.find({"user_id": user_id}).sort("created_at", -1)
    conversations = [_serialize_conversation(doc) async for doc in cursor]

    return {"conversations": conversations, "count": len(conversations)}


@router.get("/{session_id}")
async def get_conversation(session_id: str):
    """Returns full message history for one session."""
    db = get_db()

    doc = await db.conversations.find_one({"session_id": session_id})
    if doc is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")

    return _serialize_conversation(doc, include_messages=True)


@router.delete("/{session_id}")
async def delete_conversation(session_id: str):
    """Deletes a conversation. Does not delete its audit_logs entries —
    those remain for compliance/traceability (DPDP Act 2023 requires
    audit trail retention even if the user deletes their chat)."""
    db = get_db()

    result = await db.conversations.delete_one({"session_id": session_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Conversation not found.")

    return {"message": "Conversation deleted.", "session_id": session_id}
