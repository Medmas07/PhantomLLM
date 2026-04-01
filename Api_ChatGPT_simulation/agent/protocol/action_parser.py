"""
action_parser.py – Parses <ACTION>…</ACTION> blocks from model responses.

The model signals a tool call by wrapping a JSON payload in <ACTION> tags.
This module extracts and validates those payloads without executing them.

Separation of concerns:
    - Parsing happens here (protocol layer)
    - Execution happens in agent/tools/file_tools.py (tools layer)
"""

import json
import re

# Matches <ACTION> { … } </ACTION> across multiple lines.
# Uses DOTALL so "." matches newlines inside the JSON body.
_ACTION_PATTERN = re.compile(
    r"<ACTION>\s*(\{.*?\})\s*</ACTION>",
    re.DOTALL,
)


def try_extract_action(text: str) -> dict | None:
    """
    Scan a model response for the first valid ACTION block.

    Returns the parsed JSON dict if found and structurally valid.
    Returns None if no ACTION tag is present or all tags contain invalid JSON.

    A valid payload must have either:
      - "action"  key  → single-action form  {"action": "write_file", ...}
      - "actions" key  → batch form          {"actions": [{...}, {...}]}
    """
    matches = _ACTION_PATTERN.findall(text)
    if not matches:
        return None

    for raw_json in matches:
        try:
            payload = json.loads(raw_json)
        except json.JSONDecodeError:
            # Malformed JSON in this tag – try the next match
            continue

        # Structural validation: must be single or batch action
        if "action" in payload or "actions" in payload:
            return payload

    # All tags were either invalid JSON or unknown structure
    return None
