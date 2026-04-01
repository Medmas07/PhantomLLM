"""
paths.py – Workspace path safety utilities.

ALL file operations performed by the agent are restricted to the workspace/
directory.  This prevents path-traversal attacks where the model (or a
compromised prompt) could try to read/write files outside the sandbox.

Usage:
    from agent.tools.paths import safe_path
    full_path = safe_path("src/main.py")   # workspace/src/main.py
"""

from pathlib import Path

from agent.config.settings import cfg


def safe_path(rel_path: str) -> Path:
    """
    Resolve a relative path safely within cfg.workspace.

    Args:
        rel_path: Relative path string provided by the model (e.g. "src/app.py").

    Returns:
        Absolute resolved Path guaranteed to be inside cfg.workspace.

    Raises:
        ValueError: If the path is absolute or contains ".." traversal.
    """
    # Normalise separators (model may use backslashes on Windows paths)
    rel_path = rel_path.replace("\\", "/")

    # Block absolute paths and explicit ".." segments
    parts = rel_path.split("/")
    if rel_path.startswith("/") or ".." in parts:
        raise ValueError(
            f"Forbidden path: {rel_path!r}. "
            "Only relative paths without '..' are allowed."
        )

    resolved = (cfg.workspace / rel_path).resolve()

    # Double-check: resolved path must still be inside workspace
    try:
        resolved.relative_to(cfg.workspace)
    except ValueError:
        raise ValueError(
            f"Path {rel_path!r} escapes the workspace after resolution."
        )

    return resolved