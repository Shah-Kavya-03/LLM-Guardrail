"""Groq API client — OpenAI-compatible, see openai_compatible_client.py."""

from llm.openai_compatible_client import send as _send

_BASE_URL = "https://api.groq.com/openai/v1"
_MODEL_NAME = "llama-3.3-70b-versatile"


def send(messages: list[dict]) -> dict:
    return _send(
        messages,
        api_key_env_var="GROQ_API_KEY",
        base_url=_BASE_URL,
        model_name=_MODEL_NAME,
    )
