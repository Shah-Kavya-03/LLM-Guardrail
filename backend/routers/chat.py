"""
POST /chat — the core guardrail pipeline.

User Prompt
    -> classify (Presidio + Detoxify + injection patterns)
    -> if blocked: log + return, never call an LLM
    -> if allowed: fetch conversation history, call LLM
    -> classify the LLM's response too
    -> save conversation + audit log
    -> return JSON to frontend
"""

from datetime import datetime, timezone

from fastapi import APIRouter
from pydantic import BaseModel

from database.connection import get_db
from database.models import new_audit_log, new_conversation, new_message
from security.threat_classifier import classify, STATUS_SAFE, STATUS_PII
from security.lime_explainer import explain
from llm.api_router import get_completion, FRIENDLY_CAPACITY_MESSAGE

router = APIRouter(tags=["Chat"])


class ChatRequest(BaseModel):
    prompt: str
    session_id: str
    user_id: str = "guest"


@router.post("/chat")
async def chat(req: ChatRequest):
    db = get_db()

    # ---- 1. Classify the incoming prompt ----
    input_classification = classify(req.prompt)

    # Blocked prompts never reach an LLM and never store raw text.
    if input_classification["blocked"]:
        lime_explanation = explain(input_classification)

        await db.audit_logs.insert_one(
            new_audit_log(
                session_id=req.session_id,
                title=req.prompt[:50],
                prompt_masked=input_classification["masked_text"],
                response=None,
                model_used=None,
                api_used=None,
                status=input_classification["status"],
                threat_tier=input_classification["threat_tier"],
                lime_explanation=lime_explanation,
                user_id=req.user_id,
            )
        )

        # Jailbreak attempts flag the user account for review.
        if input_classification["status"] == "Jailbreak":
            await db.anomalies.insert_one(
                {
                    "session_id": req.session_id,
                    "user_id": req.user_id,
                    "reason": "Jailbreak attempt detected",
                    "flagged_at": datetime.now(timezone.utc),
                }
            )

        return {
            "status": input_classification["status"],
            "response": None,
            "blocked_reason": lime_explanation,
            "lime_explanation": lime_explanation,
            "masked_prompt": input_classification["masked_text"],
            "model_used": None,
            "api_used": None,
            "threat_tier": input_classification["threat_tier"],
        }

    # ---- 2. Allowed (Safe or PII Detected) -> build conversation history ----
    masked_prompt = input_classification["masked_text"]

    conversation = await db.conversations.find_one({"session_id": req.session_id})
    if conversation is None:
        conversation = new_conversation(
            session_id=req.session_id, user_id=req.user_id, model_used="Gemini"
        )
        await db.conversations.insert_one(conversation)

    # Last 10 messages for context, oldest first.
    history_messages = conversation.get("messages", [])[-10:]
    llm_messages = [
        {"role": "user" if m["sender"] == "user" else "assistant", "content": m["text"]}
        for m in history_messages
    ]
    llm_messages.append({"role": "user", "content": masked_prompt})

    # ---- 3. Call the LLM (with rotation) ----
    completion = await get_completion(llm_messages)

    if completion["all_rate_limited"]:
        await db.audit_logs.insert_one(
            new_audit_log(
                session_id=req.session_id,
                title=req.prompt[:50],
                prompt_masked=masked_prompt,
                response=None,
                model_used=None,
                api_used=None,
                status="Rate Limited",
                threat_tier=input_classification["threat_tier"],
                lime_explanation=FRIENDLY_CAPACITY_MESSAGE,
                user_id=req.user_id,
            )
        )
        return {
            "status": input_classification["status"],
            "response": None,
            "blocked_reason": FRIENDLY_CAPACITY_MESSAGE,
            "lime_explanation": FRIENDLY_CAPACITY_MESSAGE,
            "masked_prompt": masked_prompt,
            "model_used": None,
            "api_used": None,
            "threat_tier": input_classification["threat_tier"],
        }

    # ---- 4. Classify the LLM's response too ----
    output_classification = classify(completion["text"])
    final_response = output_classification["masked_text"]  # PII-masked if needed

    # ---- 5. Persist conversation ----
    await db.conversations.update_one(
        {"session_id": req.session_id},
        {
            "$push": {
                "messages": {
                    "$each": [
                        new_message("user", masked_prompt),
                        new_message("assistant", final_response),
                    ]
                }
            },
            "$set": {
                "status": "Modified" if input_classification["status"] == STATUS_PII else "Protected",
                "model_used": completion["model_used"],
                "api_used": completion["api_used"],
            },
        },
    )

    # ---- 6. Audit log ----
    status = input_classification["status"]
    lime_explanation = explain(input_classification) if status != STATUS_SAFE else None

    await db.audit_logs.insert_one(
        new_audit_log(
            session_id=req.session_id,
            title=req.prompt[:50],
            prompt_masked=masked_prompt,
            response=final_response,
            model_used=completion["model_used"],
            api_used=completion["api_used"],
            status=status,
            threat_tier=input_classification["threat_tier"],
            lime_explanation=lime_explanation,
            user_id=req.user_id,
        )
    )

    return {
        "status": status,
        "response": final_response,
        "blocked_reason": None,
        "lime_explanation": lime_explanation,
        "masked_prompt": masked_prompt,
        "model_used": completion["model_used"],
        "api_used": completion["api_used"],
        "threat_tier": input_classification["threat_tier"],
    }
