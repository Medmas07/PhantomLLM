"""
claude_api.py – Provider: Anthropic Claude via the official Python SDK.

Requires:
    pip install anthropic

API key priority (first non-empty wins):
    1. config.json  providers.claude.api_key
    2. ANTHROPIC_API_KEY  environment variable  (SDK default)

Docs: https://docs.anthropic.com/en/api/getting-started
"""

from agent.config.settings import cfg


def generate(messages: list[dict], model: str | None = None, **kwargs) -> str:
    """
    Call the Anthropic Messages API and return the response text.

    Args:
        messages: OpenAI-style message list.
                  system-role messages are extracted and passed separately
                  (Anthropic API treats system as a top-level parameter).
        model:    Claude model ID.  Defaults to config value.
        **kwargs:
            max_tokens   (int):   Default 4096.
            temperature  (float): Default 0.7.

    Returns:
        Assistant's text response.

    Raises:
        ImportError if anthropic is not installed.
        anthropic.APIError on API-level errors.
    """
    try:
        import anthropic
    except ImportError:
        raise ImportError(
            "anthropic package is required for Claude provider.\n"
            "Install it with:  pip install anthropic"
        )

    prov = cfg.provider("claude")
    # Prefer explicit api_key in config; fall back to env var (SDK handles it)
    api_key: str | None = prov.get("api_key") or None
    resolved_model: str = model or prov.get("model", "claude-opus-4-6")

    client = anthropic.Anthropic(api_key=api_key)

    # ── Split system message from conversation turns ───────────────────────
    # Anthropic expects system prompt as a separate top-level field.
    system_parts: list[str] = []
    conv_messages: list[dict] = []

    for m in messages:
        role = m.get("role", "")
        content = m.get("content", "")
        if role == "system":
            system_parts.append(content)
        else:
            conv_messages.append({"role": role, "content": content})

    system_text = "\n\n".join(system_parts)

    response = client.messages.create(
        model=resolved_model,
        max_tokens=int(kwargs.get("max_tokens", 4096)),
        # Pass system only when present (NOT_GIVEN signals omission to the SDK)
        **({"system": system_text} if system_text else {}),
        messages=conv_messages,
    )

    return response.content[0].text