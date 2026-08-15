"""Cerebras API client — OpenAI-compatible, see openai_compatible_client.py."""

from llm.openai_compatible_client import send as _send

_BASE_URL = "https://api.cerebras.ai/v1"
_MODEL_NAME = "llama-3.3-70b"


def send(messages: list[dict]) -> dict:
    return _send(
        messages,
        api_key_env_var="CEREBRAS_API_KEY",
        base_url=_BASE_URL,
        model_name=_MODEL_NAME,
    )
