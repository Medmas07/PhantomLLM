from pathlib import Path
from config import WORKSPACE

def safe_path(rel_path: str) -> Path:
    rel_path = rel_path.replace("\\", "/")
    if rel_path.startswith("/") or ".." in rel_path.split("/"):
        raise ValueError("Chemin interdit")
    return (WORKSPACE / rel_path).resolve()
