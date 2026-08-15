"""NVIDIA NIM client — OpenAI-compatible, see openai_compatible_client.py."""

from llm.openai_compatible_client import send as _send

_BASE_URL = "https://integrate.api.nvidia.com/v1"
_MODEL_NAME = "meta/llama-3.1-8b-instruct"


def send(messages: list[dict]) -> dict:
    return _send(
        messages,
        api_key_env_var="NVIDIA_API_KEY",
        base_url=_BASE_URL,
        model_name=_MODEL_NAME,
    )
