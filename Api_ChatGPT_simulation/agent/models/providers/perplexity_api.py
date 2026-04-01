"""
perplexity_api.py – Provider: Perplexity AI via OpenAI-compatible API.

Perplexity serves LLaMA-based models with real-time web search capabilities.
Their API is OpenAI-compatible; we reuse the openai SDK with a custom base_url.

Requires:
    pip install openai

API key priority:
    1. config.json  providers.perplexity.api_key
    2. PERPLEXITY_API_KEY  environment variable

Docs: https://docs.perplexity.ai/reference/post_chat_completions
"""

import os

from agent.config.settings import cfg


def generate(messages: list[dict], model: str | None = None, **kwargs) -> str:
    """
    Call the Perplexity AI API and return the response text.

    Args:
        messages: OpenAI-style message list (passed through as-is).
        model:    Perplexity model ID.  Defaults to config value.
        **kwargs:
            max_tokens   (int):   Default 4096.
            temperature  (float): Default 0.7.

    Returns:
        Assistant's text response.

    Raises:
        ImportError if openai is not installed.
    """
    try:
        from openai import OpenAI
    except ImportError:
        raise ImportError(
            "openai package is required for Perplexity provider.\n"
            "Install it with:  pip install openai"
        )

    prov = cfg.provider("perplexity")
    api_key: str  = prov.get("api_key") or os.environ.get("PERPLEXITY_API_KEY", "")
    base_url: str = prov.get("base_url", "https://api.perplexity.ai")
    resolved_model: str = model or prov.get(
        "model", "llama-3.1-sonar-large-128k-online"
    )

    client = OpenAI(api_key=api_key, base_url=base_url)

    response = client.chat.completions.create(
        model=resolved_model,
        messages=messages,
        max_tokens=int(kwargs.get("max_tokens", 4096)),
        temperature=float(kwargs.get("temperature", 0.7)),
    )

    return response.choices[0].message.content