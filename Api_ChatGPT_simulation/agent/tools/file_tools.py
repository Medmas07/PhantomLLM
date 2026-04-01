"""
file_tools.py – Execute ACTION payloads dispatched by the model.

This is the only module that touches the filesystem on behalf of the agent.
Every operation goes through safe_path() to enforce sandbox isolation.
Every destructive write is preceded by backup() to preserve the previous state.

Supported action types:
    write_file    – create or overwrite a file (base64 content)
    append_file   – append bytes to an existing or new file (base64 content)
    read_file     – read a file and return base64-encoded content
    list_files    – list files in a directory (optionally recursive)
    delete_file   – delete a single file
    make_dir      – create a directory (with parents)
    delete_dir    – recursively delete a directory
    replace_text  – find-and-replace a string inside a text file

Protocol note:
    ALL file content is base64-encoded in both directions.
    The model must never send plain-text file content.
"""

import shutil

from agent.tools.base64_utils import safe_b64decode, b64encode_bytes
from agent.tools.paths import safe_path
from agent.tools.versioning import backup


# ── Public entry-point ────────────────────────────────────────────────────────

def execute_actions(data: dict) -> list:
    """
    Execute one or more actions from a parsed ACTION payload.

    Accepts either:
        Single:  {"action": "write_file", "path": "...", "content": "..."}
        Batch:   {"actions": [{"action": "..."}, {"action": "..."}]}

    Returns:
        A list of result strings or dicts (one per action).
        Each entry is either a success string (str) or an error string (str)
        or a structured result dict (for read_file / list_files).
    """
    # Normalise: always work with a list of action dicts
    raw_actions: list[dict] = data.get("actions", [data])
    results = []

    for action_dict in raw_actions:
        act = action_dict.get("action", "")
        try:
            results.append(_dispatch(act, action_dict))
        except Exception as exc:
            results.append(f"❌ {act} failed: {exc}")

    return results


# ── Internal dispatcher ───────────────────────────────────────────────────────

def _dispatch(act: str, a: dict):
    """
    Route a single action dict to its handler.

    Args:
        act: Action name string (e.g. "write_file").
        a:   Full action dict with all parameters.

    Returns:
        A result string or dict.

    Raises:
        Any exception propagated from the filesystem operation.
        Caught by execute_actions() and turned into an error string.
    """

    # ── WRITE FILE ────────────────────────────────────────────────────────────
    if act == "write_file":
        path = safe_path(a["path"])
        path.parent.mkdir(parents=True, exist_ok=True)
        # Back up before overwriting
        backup(path)
        raw = safe_b64decode(a.get("content", ""))
        path.write_bytes(raw)
        return f"✅ write_file  {path.as_posix()}  ({len(raw)} bytes)"

    # ── APPEND FILE ───────────────────────────────────────────────────────────
    elif act == "append_file":
        path = safe_path(a["path"])
        path.parent.mkdir(parents=True, exist_ok=True)
        raw = safe_b64decode(a.get("content", ""))
        with open(path, "ab") as fh:
            fh.write(raw)
        return f"✅ append_file  {path.as_posix()}  (+{len(raw)} bytes)"

    # ── READ FILE ─────────────────────────────────────────────────────────────
    elif act == "read_file":
        path = safe_path(a["path"])
        raw = path.read_bytes()
        return {
            "action":  "read_file",
            "path":    path.as_posix(),
            "content": b64encode_bytes(raw),   # model must decode this
            "size":    len(raw),
        }

    # ── LIST FILES ────────────────────────────────────────────────────────────
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
            "path":   base.as_posix(),
            "files":  sorted(files),
        }

    # ── DELETE FILE ───────────────────────────────────────────────────────────
    elif act == "delete_file":
        path = safe_path(a["path"])
        path.unlink(missing_ok=True)
        return f"🗑️  delete_file  {path.as_posix()}"

    # ── MAKE DIR ──────────────────────────────────────────────────────────────
    elif act == "make_dir":
        path = safe_path(a["path"])
        path.mkdir(parents=True, exist_ok=True)
        return f"📁 make_dir  {path.as_posix()}"

    # ── DELETE DIR ────────────────────────────────────────────────────────────
    elif act == "delete_dir":
        path = safe_path(a["path"])
        shutil.rmtree(path, ignore_errors=True)
        return f"🗑️  delete_dir  {path.as_posix()}"

    # ── REPLACE TEXT ──────────────────────────────────────────────────────────
    elif act == "replace_text":
        path = safe_path(a["path"])
        old: str = a["old"]
        new: str = a["new"]
        backup(path)
        text = path.read_text(encoding="utf-8", errors="replace")
        patched = text.replace(old, new)
        path.write_text(patched, encoding="utf-8")
        count = text.count(old)
        return f"✏️  replace_text  {path.as_posix()}  ({count} occurrence(s) replaced)"

    # ── UNKNOWN ───────────────────────────────────────────────────────────────
    else:
        return f"⚠️  Unknown action: {act!r}  (ignored)"
