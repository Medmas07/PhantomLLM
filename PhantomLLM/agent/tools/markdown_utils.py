"""
markdown_utils.py - Helpers for markdown fenced content transport.

Used by the markdown ACTION path to keep file content human-readable for LLMs.
"""

import re

_FENCED_PATTERN = re.compile(
    r"^\s*([`~]{3,})([^\n`]*)\n([\s\S]*?)\n\1\s*$"
)


def decode_markdown_content(value: str) -> tuple[str, str]:
    """
    Decode markdown content, accepting either fenced or raw text.

    Returns:
        (language_hint, text_content)
    """
    if not isinstance(value, str):
        raise TypeError("Markdown content must be a string.")

    text = value.strip()
    match = _FENCED_PATTERN.match(text)
    if match:
        language = match.group(2).strip()
        body = match.group(3)
        return language, body
    return "", value


def encode_markdown_fence(text: str, language: str = "text") -> str:
    """
    Encode plain text into a markdown fenced block.

    Fence length is increased automatically if the payload already contains
    triple backticks.
    """
    if not isinstance(text, str):
        raise TypeError("Text to encode as markdown must be a string.")

    fence = "```"
    while fence in text:
        fence += "`"

    lang = (language or "").strip()
    header = f"{fence}{lang}".rstrip()
    return f"{header}\n{text}\n{fence}"
