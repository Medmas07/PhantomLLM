"""
versioning.py – Automatic file backups before destructive operations.

Before overwriting or patching a file, backup() saves a timestamped copy
under workspace/.versions/ mirroring the original directory structure.

This gives the user a simple audit trail and the ability to manually
restore a previous version without requiring git.

Example layout after two saves of workspace/src/app.py:
    workspace/
        .versions/
            src/
                app.py/
                    20240101-123000-a1b2c3d4e5f6.bak
                    20240101-130000-f6e5d4c3b2a1.bak
        src/
            app.py
"""

from datetime import datetime
from hashlib import sha256
from pathlib import Path

from agent.config.settings import cfg


def backup(path: Path) -> Path | None:
    """
    Create a versioned backup of `path` in the .versions directory.

    Args:
        path: Absolute path to the file to back up (must be inside workspace).

    Returns:
        Path to the created backup file, or None if the file does not exist yet.
    """
    if not path.exists():
        # Nothing to back up (first write)
        return None

    # Mirror the relative directory structure inside .versions/
    # e.g.  workspace/src/app.py  →  workspace/.versions/src/app.py/
    rel = path.relative_to(cfg.workspace)
    dest_dir = cfg.versions_dir / rel
    dest_dir.mkdir(parents=True, exist_ok=True)

    # Timestamp + first-12-chars of SHA-256 as filename
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    raw = path.read_bytes()
    h = sha256(raw).hexdigest()[:12]

    backup_path = dest_dir / f"{stamp}-{h}.bak"
    backup_path.write_bytes(raw)
    return backup_path