"""
qwen_api.py – Provider: Alibaba Qwen via DashScope OpenAI-compatible API.

Alibaba's DashScope platform exposes Qwen models through an OpenAI-compatible
endpoint, so we reuse the openai SDK with a custom base_url.

Requires:
    pip install openai

API key priority:
    1. config.json  providers.qwen.api_key
    2. DASHSCOPE_API_KEY  environment variable

Docs: https://help.aliyun.com/zh/dashscope/developer-reference/compatibility-of-openai-with-dashscope
"""

import os

from agent.config.settings import cfg


def generate(messages: list[dict], model: str | None = None, **kwargs) -> str:
    """
    Call the Alibaba Qwen (DashScope) API and return the response text.

    Args:
        messages: OpenAI-style message list (passed through as-is).
        model:    Qwen model ID.  Defaults to config value.
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
            "openai package is required for Qwen provider.\n"
            "Install it with:  pip install openai"
        )

    prov = cfg.provider("qwen")
    api_key: str  = prov.get("api_key") or os.environ.get("DASHSCOPE_API_KEY", "")
    base_url: str = prov.get(
        "base_url", "https://dashscope.aliyuncs.com/compatible-mode/v1"
    )
    resolved_model: str = model or prov.get("model", "qwen-max")

    client = OpenAI(api_key=api_key, base_url=base_url)

    response = client.chat.completions.create(
        model=resolved_model,
        messages=messages,
        max_tokens=int(kwargs.get("max_tokens", 4096)),
        temperature=float(kwargs.get("temperature", 0.7)),
    )

    return response.choices[0].message.content