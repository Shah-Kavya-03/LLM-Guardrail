"""
Generic OpenAI-compatible client.

Groq, Cerebras, NVIDIA NIM, and Mistral all expose an OpenAI-compatible
/chat/completions endpoint. This means one client implementation
handles all four — only base_url, api_key, and model_name differ per
provider. Each provider's *_client.py is a thin wrapper that just
supplies those three values, so adding a 6th OpenAI-compatible
provider later is a 10-line file, not a new client to write from
scratch.

(Gemini is the exception — it uses Google's own SDK/protocol, hence
gemini_client.py being separate and self-contained.)
"""

from openai import OpenAI, RateLimitError, APIError


def send(
    messages: list[dict],
    api_key_env_var: str,
    base_url: str,
    model_name: str,
) -> dict:
    """
    Send a conversation history to an OpenAI-compatible endpoint.

    Args:
        messages: [{"role": "user"|"assistant", "content": str}, ...]
        api_key_env_var: name of the .env variable holding the API key
        base_url: provider's OpenAI-compatible base URL
        model_name: provider's model identifier

    Returns:
        {"text": str, "error": None} on success, or
        {"text": None, "error": {"type": "rate_limit"|"other", "message": str}}
    """
    import os

    api_key = os.getenv(api_key_env_var)
    if not api_key or api_key.startswith("your_"):
        return {
            "text": None,
            "error": {"type": "other", "message": f"{api_key_env_var} is not set in .env"},
        }

    try:
        client = OpenAI(api_key=api_key, base_url=base_url)
        response = client.chat.completions.create(
            model=model_name,
            messages=messages,
        )
        return {"text": response.choices[0].message.content, "error": None}

    except RateLimitError as e:
        return {"text": None, "error": {"type": "rate_limit", "message": str(e)}}
    except APIError as e:
        return {"text": None, "error": {"type": "other", "message": str(e)}}
    except Exception as e:
        return {"text": None, "error": {"type": "other", "message": str(e)}}
