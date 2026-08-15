"""
Gemini API client.

Wraps google-generativeai so api_router.py can call every provider
through the same shape of function: send(messages) -> {text, error}.
This is what lets a new provider be added later without touching
chat.py — only api_router.py's rotation list changes.
"""

import os
import google.generativeai as genai

_MODEL_NAME = "gemini-1.5-flash"


def _get_model():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key or api_key == "your_gemini_api_key_here":
        raise RuntimeError("GEMINI_API_KEY is not set in .env")
    genai.configure(api_key=api_key)
    return genai.GenerativeModel(_MODEL_NAME)


def send(messages: list[dict]) -> dict:
    """
    Send a conversation history to Gemini.

    Args:
        messages: [{"role": "user"|"assistant", "content": str}, ...]
                  in chronological order, last item = current prompt.

    Returns:
        {"text": str, "error": None} on success, or
        {"text": None, "error": {"type": "rate_limit"|"other", "message": str}}
    """
    try:
        model = _get_model()

        # Gemini's SDK uses role "model" instead of "assistant", and
        # expects a "parts" list rather than plain "content".
        history = [
            {
                "role": "model" if m["role"] == "assistant" else "user",
                "parts": [m["content"]],
            }
            for m in messages[:-1]
        ]
        current_prompt = messages[-1]["content"]

        chat = model.start_chat(history=history)
        response = chat.send_message(current_prompt)

        return {"text": response.text, "error": None}

    except Exception as e:
        error_str = str(e).lower()
        if "429" in error_str or "rate limit" in error_str or "quota" in error_str:
            return {"text": None, "error": {"type": "rate_limit", "message": str(e)}}
        return {"text": None, "error": {"type": "other", "message": str(e)}}
