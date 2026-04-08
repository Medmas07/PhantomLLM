"""
action_parser_markdown.py - Detect and parse markdown-oriented ACTION payloads.

This parser is additive and keeps legacy action_parser.py untouched.
It supports:
1) <ACTION>{...}</ACTION>
2) <ACTION>```json ... ```</ACTION>

A payload is considered "markdown mode" only when it explicitly signals it via:
- content_format="markdown" (top-level or per action)
- protocol="markdown_v1"
- content_markdown/content_md field
- write/append content starting with a fenced code block
"""

import json
import re

_ACTION_BODY_PATTERN = re.compile(r"<ACTION>\s*(.*?)\s*</ACTION>", re.DOTALL)
_JSON_FENCE_PATTERN = re.compile(
    r"^\s*```(?:json)?\s*(\{.*\})\s*```\s*$",
    re.DOTALL,
)


def _unwrap_json_body(body: str) -> str:
    """Extract raw JSON object text from optional markdown code fences."""
    match = _JSON_FENCE_PATTERN.match(body.strip())
    if match:
        return match.group(1).strip()
    return body.strip()


def _is_markdown_payload(payload: dict) -> bool:
    """Return True only for payloads that explicitly opt into markdown mode."""
    if str(payload.get("protocol", "")).strip().lower() == "markdown_v1":
        return True

    top_format = str(payload.get("content_format", "")).strip().lower()
    if top_format == "markdown":
        return True

    actions = payload.get("actions")
    if isinstance(actions, list):
        action_list = [a for a in actions if isinstance(a, dict)]
    else:
        action_list = [payload]

    for action in action_list:
        if str(action.get("content_format", "")).strip().lower() == "markdown":
            return True
        if "content_markdown" in action or "content_md" in action:
            return True
        act_name = str(action.get("action", "")).strip().lower()
        content = action.get("content")
        if (
            act_name in {"write_file", "append_file"}
            and isinstance(content, str)
            and content.lstrip().startswith(("```", "~~~"))
        ):
            return True

    return False


def try_extract_action_markdown(text: str) -> dict | None:
    """
    Return the first markdown-oriented ACTION payload, else None.

    Structural requirement remains identical to legacy parser:
    payload must contain either "action" or "actions".
    """
    matches = _ACTION_BODY_PATTERN.findall(text)
    if not matches:
        return None

    for raw_body in matches:
        candidate = _unwrap_json_body(raw_body)
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError:
            continue

        if not isinstance(payload, dict):
            continue
        if "action" not in payload and "actions" not in payload:
            continue
        if _is_markdown_payload(payload):
            return payload

    return None
