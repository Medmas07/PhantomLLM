"""
file_tools_markdown.py - Execute markdown ACTION payloads.

This module is additive and does not replace legacy base64 file_tools.py.
It handles the same action set, but for write/append/read it prefers
markdown fenced content for text files.
"""

import shutil

from agent.config.settings import cfg
from agent.tools.base64_utils import b64encode_bytes
from agent.tools.markdown_utils import decode_markdown_content, encode_markdown_fence
from agent.tools.paths import safe_path
from agent.tools.versioning import backup


def _rel(path) -> str:
    """Return workspace-relative POSIX path for consistent tool output."""
    try:
        return path.relative_to(cfg.workspace).as_posix()
    except ValueError:
        return path.as_posix()


def _is_markdown_mode(action_dict: dict, top_format: str) -> bool:
    """Whether this action should decode content as markdown text."""
    if top_format == "markdown":
        return True

    action_format = str(action_dict.get("content_format", "")).strip().lower()
    if action_format == "markdown":
        return True

    if "content_markdown" in action_dict or "content_md" in action_dict:
        return True

    content = action_dict.get("content")
    if isinstance(content, str) and content.lstrip().startswith(("```", "~~~")):
        return True

    return False


def _extract_markdown_text(action_dict: dict, top_format: str) -> str:
    """Extract text body from markdown-oriented content fields."""
    if not _is_markdown_mode(action_dict, top_format):
        raise ValueError(
            "Markdown action missing markdown marker "
            "(content_format=markdown or content_markdown/content_md)."
        )

    raw_value = (
        action_dict.get("content_markdown")
        or action_dict.get("content_md")
        or action_dict.get("content")
        or ""
    )
    _, text = decode_markdown_content(str(raw_value))
    return text


def execute_actions_markdown(data: dict) -> list:
    """
    Execute one or more markdown actions.

    Accepts either:
        {"action": "...", ...}
        {"actions": [{...}, {...}], "content_format": "markdown"}
    """
    raw_actions = data.get("actions", [data])
    top_format = str(data.get("content_format", "")).strip().lower()
    results = []

    for action_dict in raw_actions:
        act = action_dict.get("action", "")
        try:
            results.append(_dispatch(act, action_dict, top_format))
        except Exception as exc:
            results.append(f"ERROR {act} failed: {exc}")

    return results


def _dispatch(act: str, a: dict, top_format: str):
    """Route one markdown action dict to its filesystem handler."""
    if act == "write_file":
        path = safe_path(a["path"])
        path.parent.mkdir(parents=True, exist_ok=True)
        backup(path)
        text = _extract_markdown_text(a, top_format)
        raw = text.encode("utf-8")
        path.write_bytes(raw)
        return f"OK write_file {_rel(path)} ({len(raw)} bytes, markdown)"

    elif act == "append_file":
        path = safe_path(a["path"])
        path.parent.mkdir(parents=True, exist_ok=True)
        text = _extract_markdown_text(a, top_format)
        raw = text.encode("utf-8")
        with open(path, "ab") as fh:
            fh.write(raw)
        return f"OK append_file {_rel(path)} (+{len(raw)} bytes, markdown)"

    elif act == "read_file":
        path = safe_path(a["path"])
        raw = path.read_bytes()
        try:
            text = raw.decode("utf-8")
            return {
                "action": "read_file",
                "path": _rel(path),
                "content_markdown": encode_markdown_fence(text, "text"),
                "size": len(raw),
                "encoding": "utf-8",
            }
        except UnicodeDecodeError:
            return {
                "action": "read_file",
                "path": _rel(path),
                "content_base64": b64encode_bytes(raw),
                "size": len(raw),
                "encoding": "base64",
            }

    elif act == "list_files":
        base = safe_path(a.get("path", "."))
        recursive = bool(a.get("recursive", False))
        files: list[str] = []

        if recursive:
            for p in base.rglob("*"):
                if p.is_file():
                    files.append(p.relative_to(base).as_posix())
        else:
            for p in base.iterdir():
                if p.is_file():
                    files.append(p.name)

        return {
            "action": "list_files",
            "path": _rel(base),
            "files": sorted(files),
        }

    elif act == "delete_file":
        path = safe_path(a["path"])
        path.unlink(missing_ok=True)
        return f"OK delete_file {_rel(path)}"

    elif act == "make_dir":
        path = safe_path(a["path"])
        path.mkdir(parents=True, exist_ok=True)
        return f"OK make_dir {_rel(path)}"

    elif act == "delete_dir":
        path = safe_path(a["path"])
        shutil.rmtree(path, ignore_errors=True)
        return f"OK delete_dir {_rel(path)}"

    elif act == "replace_text":
        path = safe_path(a["path"])
        old = a["old"]
        new = a["new"]
        backup(path)
        text = path.read_text(encoding="utf-8", errors="replace")
        patched = text.replace(old, new)
        path.write_text(patched, encoding="utf-8")
        count = text.count(old)
        return f"OK replace_text {_rel(path)} ({count} occurrence(s) replaced)"

    else:
        return f"WARN Unknown action: {act!r} (ignored)"
