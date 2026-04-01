"""
gemini_api.py – Provider: Google Gemini via the google-generativeai SDK.

Requires:
    pip install google-generativeai

API key priority:
    1. config.json  providers.gemini.api_key
    2. GOOGLE_API_KEY  environment variable

Docs: https://ai.google.dev/gemini-api/docs/quickstart
"""

import os

from agent.config.settings import cfg


def generate(messages: list[dict], model: str | None = None, **kwargs) -> str:
    """
    Call the Google Gemini API and return the response text.

    Args:
        messages: OpenAI-style message list.
                  system-role messages are prepended to the first user turn.
                  assistant-role messages become "model"-role in Gemini format.
        model:    Gemini model ID.  Defaults to config value.
        **kwargs: Ignored (Gemini SDK uses its own defaults).

    Returns:
        Assistant's text response.

    Raises:
        ImportError if google-generativeai is not installed.
        ValueError  if messages contains no user-role message.
    """
    try:
        import google.generativeai as genai
    except ImportError:
        raise ImportError(
            "google-generativeai package is required for Gemini provider.\n"
            "Install it with:  pip install google-generativeai"
        )

    prov = cfg.provider("gemini")
    api_key: str = prov.get("api_key") or os.environ.get("GOOGLE_API_KEY", "")
    resolved_model: str = model or prov.get("model", "gemini-1.5-pro")

    genai.configure(api_key=api_key)
    client = genai.GenerativeModel(resolved_model)

    # ── Convert OpenAI-style messages to Gemini history format ────────────
    # Gemini uses roles "user" and "model" (not "assistant").
    # System messages have no direct equivalent; prepend them to user text.

    system_prefix = ""
    history: list[dict] = []
    pending_user = ""

    for m in messages:
        role = m.get("role", "user")
        content = m.get("content", "")

        if role == "system":
            # Accumulate system messages; they will prefix the first user turn
            system_prefix += f"[System instruction: {content}]\n\n"

        elif role == "user":
            # If there is accumulated system text, prepend it once
            if system_prefix:
                pending_user = system_prefix + content
                system_prefix = ""
            else:
                pending_user = content

        elif role == "assistant":
            # Close the previous user turn and add the assistant reply
            if pending_user:
                history.append({"role": "user",  "parts": [pending_user]})
                pending_user = ""
            history.append({"role": "model", "parts": [content]})

    if not pending_user:
        raise ValueError(
            "gemini provider requires at least one user-role message."
        )

    # The last user message is the current prompt; history is everything before
    chat = client.start_chat(history=history)
    response = chat.send_message(pending_user)
    return response.text
