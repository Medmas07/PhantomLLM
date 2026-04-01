"""
groq_api.py – Provider: Groq fast-inference platform.

Groq serves open-source models (LLaMA, Mixtral, etc.) with very low latency.
Their API is OpenAI-compatible; we use the official groq SDK for convenience.

Requires:
    pip install groq

API key priority:
    1. config.json  providers.groq.api_key
    2. GROQ_API_KEY  environment variable  (SDK default)

Docs: https://console.groq.com/docs/openai
"""

import os

from agent.config.settings import cfg


def generate(messages: list[dict], model: str | None = None, **kwargs) -> str:
    """
    Call the Groq API and return the response text.

    Args:
        messages: OpenAI-style message list (passed through as-is).
        model:    Groq model ID.  Defaults to config value.
        **kwargs:
            max_tokens   (int):   Default 4096.
            temperature  (float): Default 0.7.

    Returns:
        Assistant's text response.

    Raises:
        ImportError if groq is not installed.
    """
    try:
        from groq import Groq
    except ImportError:
        raise ImportError(
            "groq package is required for Groq provider.\n"
            "Install it with:  pip install groq"
        )

    prov = cfg.provider("groq")
    api_key: str = prov.get("api_key") or os.environ.get("GROQ_API_KEY", "")
    resolved_model: str = model or prov.get("model", "llama-3.3-70b-versatile")

    client = Groq(api_key=api_key)

    response = client.chat.completions.create(
        model=resolved_model,
        messages=messages,
        max_tokens=int(kwargs.get("max_tokens", 4096)),
        temperature=float(kwargs.get("temperature", 0.7)),
    )

    return response.choices[0].message.content