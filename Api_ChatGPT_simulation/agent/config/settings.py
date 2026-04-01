"""
settings.py – Loads config.json and exposes a typed Settings singleton.

All other modules do:
    from agent.config.settings import cfg

cfg is loaded once at import time and can be hot-reloaded via cfg.reload().
"""

import json
from pathlib import Path

# ── Path constants ────────────────────────────────────────────────────────────

# config.json lives next to this file (agent/config/)
_CONFIG_FILE = Path(__file__).parent / "config.json"

# agent/ package root (one level above agent/config/)
_AGENT_ROOT = Path(__file__).resolve().parent.parent


# ── Raw loader ────────────────────────────────────────────────────────────────

def _load() -> dict:
    """
    Read config.json from disk and merge with built-in defaults.
    Unknown keys in config.json are preserved transparently.
    """
    defaults: dict = {
        "mode":          "cli",
        "default_model": "openai_ui",
        "headless":      False,
        "workspace":     "./workspace",
        "providers":     {},
    }

    if _CONFIG_FILE.exists():
        with open(_CONFIG_FILE, "r", encoding="utf-8") as fh:
            user_cfg = json.load(fh)
        # Deep-merge providers, shallow-merge everything else
        user_providers = user_cfg.pop("providers", {})
        defaults.update(user_cfg)
        defaults["providers"].update(user_providers)

    return defaults


# ── Settings class ────────────────────────────────────────────────────────────

class Settings:
    """
    Thin, typed wrapper around the raw config dict.

    Attributes:
        mode          – "cli" or "api"
        default_model – name used when no model is specified
        headless      – whether to run Playwright in headless mode
        workspace     – resolved Path to the sandboxed file workspace

    Methods:
        provider(name) – returns the config sub-dict for a named provider
        reload()       – hot-reload config.json without restarting
    """

    def __init__(self, data: dict) -> None:
        self._data = data
        self._apply()

    def _apply(self) -> None:
        """Apply the current _data dict to typed attributes."""
        self.mode:          str  = self._data.get("mode",          "cli")
        self.default_model: str  = self._data.get("default_model", "openai_ui")
        self.headless:      bool = self._data.get("headless",      False)

        # Resolve workspace path.
        # If relative, it is resolved relative to the agent/ root so the
        # package stays self-contained regardless of CWD.
        ws_raw = self._data.get("workspace", "./workspace")
        ws_path = Path(ws_raw)
        if not ws_path.is_absolute():
            self.workspace: Path = (_AGENT_ROOT / ws_path).resolve()
        else:
            self.workspace = ws_path.resolve()

        # Ensure directories exist at load time
        self.workspace.mkdir(parents=True, exist_ok=True)

        # .versions/ sub-directory for automatic file backups
        self.versions_dir: Path = self.workspace / ".versions"
        self.versions_dir.mkdir(parents=True, exist_ok=True)

    def provider(self, name: str) -> dict:
        """
        Return the provider-specific config dict.
        Returns an empty dict if the provider is not configured.

        Example:
            api_key = cfg.provider("claude").get("api_key", "")
        """
        return self._data.get("providers", {}).get(name, {})

    def reload(self) -> None:
        """Hot-reload config.json from disk. Thread-safe for reads (GIL)."""
        self._data = _load()
        self._apply()

    def __repr__(self) -> str:
        return (
            f"Settings(mode={self.mode!r}, default_model={self.default_model!r}, "
            f"headless={self.headless}, workspace={self.workspace})"
        )


# ── Singleton ─────────────────────────────────────────────────────────────────
# Import this object everywhere; never instantiate Settings directly.

cfg = Settings(_load())