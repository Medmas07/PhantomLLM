"""
settings.py – Loads config.json and exposes a typed Settings singleton.

All other modules do:
    from agent.config.settings import cfg

cfg is loaded once at import time and can be hot-reloaded via cfg.reload().
"""

import json
import shutil
import sys
from pathlib import Path

# ── Path constants ────────────────────────────────────────────────────────────

# config.json lives next to this file (agent/config/)
_CONFIG_FILE = Path(__file__).parent / "config.json"

# agent/ package root (one level above agent/config/)
_AGENT_ROOT = Path(__file__).resolve().parent.parent


def _default_profile_dir() -> str:
    """
    Cross-platform default persistent browser profile directory.
    Kept under the user home so it works for both CLI and service mode.
    """
    home = Path.home()
    if sys.platform.startswith("win"):
        return str(home / "AppData" / "Local" / "PhantomLLM" / "PlaywrightProfile")
    if sys.platform.startswith("linux"):
        return str(home / ".cache" / "phantomllm" / "playwright-profile")
    return str(home / ".phantomllm" / "playwright-profile")


def _detect_browser_executable() -> str:
    """
    Try to detect a Chromium/Chrome executable on the current OS.
    Returns empty string when no candidate is found.
    """
    candidates: list[str] = []
    if sys.platform.startswith("win"):
        candidates.extend([
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files\Chromium\Application\chrome.exe",
            r"C:\Program Files (x86)\Chromium\Application\chrome.exe",
            "chrome",
            "chromium",
        ])
    elif sys.platform.startswith("linux"):
        candidates.extend([
            "google-chrome",
            "google-chrome-stable",
            "chromium-browser",
            "chromium",
            "/usr/bin/google-chrome",
            "/usr/bin/google-chrome-stable",
            "/usr/bin/chromium-browser",
            "/usr/bin/chromium",
        ])
    else:
        candidates.extend(["google-chrome", "chromium"])

    for candidate in candidates:
        p = Path(candidate)
        if p.is_absolute() and p.exists():
            return str(p)
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    return ""


# ── Raw loader ────────────────────────────────────────────────────────────────

def _load() -> dict:
    """
    Read config.json from disk and merge with built-in defaults.
    Unknown keys in config.json are preserved transparently.
    """
    defaults: dict = {
        "mode":          "cli",
        "default_model": "openai_ui",
        "browser_backend": "playwright",
        "camoufox_fetch_prompted": False,
        "fallback_enabled": True,
        "fallback_models": ["openai_ui", "gemini_ui", "perplexity_ui"],
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
        self.mode:            str  = self._data.get("mode",          "cli")
        self.default_model:   str  = self._data.get("default_model", "openai_ui")
        self.browser_backend: str  = str(
            self._data.get("browser_backend", "playwright")
        ).strip().lower()
        if self.browser_backend not in {"playwright", "camoufox"}:
            self.browser_backend = "playwright"
        self.camoufox_fetch_prompted: bool = bool(
            self._data.get("camoufox_fetch_prompted", False)
        )
        self.fallback_enabled: bool = bool(
            self._data.get("fallback_enabled", True)
        )
        raw_fallback = self._data.get("fallback_models", [])
        if isinstance(raw_fallback, list):
            self.fallback_models: list[str] = [
                str(x).strip() for x in raw_fallback if str(x).strip()
            ]
        else:
            self.fallback_models = []
        if not self.fallback_models:
            self.fallback_models = ["openai_ui", "gemini_ui", "perplexity_ui"]
            self._data["fallback_models"] = self.fallback_models
        self.headless:        bool = self._data.get("headless",      False)

        # Provider defaults (cross-platform)
        providers = self._data.setdefault("providers", {})
        openai_ui_cfg = providers.setdefault("openai_ui", {})
        if not str(openai_ui_cfg.get("profile_dir", "")).strip():
            openai_ui_cfg["profile_dir"] = _default_profile_dir()
        exe_raw = str(openai_ui_cfg.get("executable_path", "")).strip()
        if exe_raw:
            # Allow short command names like "google-chrome".
            resolved = shutil.which(exe_raw)
            if resolved:
                openai_ui_cfg["executable_path"] = resolved
        else:
            auto_exe = _detect_browser_executable()
            if auto_exe:
                openai_ui_cfg["executable_path"] = auto_exe

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

    def save(self) -> None:
        """Persist current config to disk (config.json)."""
        with open(_CONFIG_FILE, "w", encoding="utf-8") as fh:
            json.dump(self._data, fh, indent=2, ensure_ascii=False)
            fh.write("\n")

    def __repr__(self) -> str:
        return (
            f"Settings(mode={self.mode!r}, default_model={self.default_model!r}, "
            f"browser_backend={self.browser_backend!r}, "
            f"camoufox_fetch_prompted={self.camoufox_fetch_prompted}, "
            f"fallback_enabled={self.fallback_enabled}, "
            f"fallback_models={self.fallback_models}, "
            f"headless={self.headless}, workspace={self.workspace})"
        )


# ── Singleton ─────────────────────────────────────────────────────────────────
# Import this object everywhere; never instantiate Settings directly.

cfg = Settings(_load())
