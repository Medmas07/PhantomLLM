"""
main.py – Unified entrypoint for the multi-provider browser-automation agent.

Run modes
─────────
    python -m agent.main            ← interactive mode + model selection
    python -m agent.main --cli      ← skip prompt, direct CLI
    python -m agent.main --api      ← skip prompt, direct API server
    python -m agent.main --cli --model chatgpt

Startup sequence
────────────────
    1. Print security warning  (MANDATORY — printed before any browser launch)
    2. Prompt for mode         (unless --cli / --api flag given)
    3. Prompt for model        (unless --model flag given)
    4. Start Playwright worker (if selected model uses browser)
    5. Launch CLI or API server

Development priority
────────────────────
    NEXT FOCUS: gemini_ui — next provider to debug and stabilize.
    All future provider work should target gemini_ui first.
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from agent.config.settings import cfg


# ── Security warning (MANDATORY — printed before anything else) ───────────────

def _print_security_warning() -> None:
    W = 62
    bar = "═" * W
    print(f"\n╔{bar}╗")
    print(f"║{'':62}║")
    print(f"║{'  ⚠️   WARNING':^62}║")
    print(f"║{'':62}║")
    print(f"║  This tool automates browser interaction with LLM services.{'':2}║")
    print(f"║  Using automation may violate provider terms of service.{'':4}║")
    print(f"║{'':62}║")
    print(f"║  You risk:{'':51}║")
    print(f"║  - temporary or permanent account suspension{'':17}║")
    print(f"║  - captcha / Cloudflare blocks{'':31}║")
    print(f"║{'':62}║")
    print(f"║  RECOMMENDATION: Use a secondary account.{'':20}║")
    print(f"║{'':62}║")
    print(f"╚{bar}╝\n")


# ── Provider menu ─────────────────────────────────────────────────────────────
# Format: (model_key, display_label)
# Special sentinel "__use_api__" triggers API server mode (option 10).
#
# NEXT FOCUS: gemini_ui — debugging and stabilization target.

_PROVIDER_MENU: list[tuple[str, str]] = [
    ("openai_ui",     "ChatGPT      (chat.openai.com)  ← default (stable)"),
    ("gemini_ui",     "Gemini       (gemini.google.com)  (stable)"),
    ("meta_ui",       "Meta AI      (https://meta.ai/)"),
    ("baidu_ui",      "Baidu AI     (requires VPN) (pending)"),
    ("perplexity_ui", "Perplexity   (unstable, pending)"),
    ("claude_ui",     "Claude       (coming soon)"),
    ("deepseek_ui",   "DeepSeek     (chat.deepseek.com) (coming soon)"),
    ("grok_ui",       "Grok / xAI   (grok.com) (coming soon)"),
    ("qwen_ui",       "Qwen         (chat.qwen.ai) (coming soon)"),
    ("__use_api__",   "Use API"),
]

# Providers that require a live Playwright browser session.
# Excludes unimplemented stubs and the API sentinel.
_BROWSER_MODELS: frozenset[str] = frozenset({
    "openai_ui",
    "gemini_ui",     # NEXT FOCUS: stabilize gemini_ui
    "meta_ui",
    "perplexity_ui",
    "claude_ui",
    "deepseek_ui",
    "grok_ui",
    "qwen_ui",
})

# Providers that have no implementation yet — fail fast with a clear message.
_UNIMPLEMENTED_PROVIDERS: frozenset[str] = frozenset({
    "baidu_ui",
})

# Default model key (option 1 = ChatGPT).
_DEFAULT_MODEL = "openai_ui"


# ── Interactive prompts ───────────────────────────────────────────────────────

def _prompt_mode() -> str:
    default_hint = f"  (config.json default: {cfg.mode!r})"
    print("Select mode:")
    print(f"  1. CLI interactive{default_hint if cfg.mode == 'cli' else ''}")
    print(f"  2. API server (localhost){default_hint if cfg.mode == 'api' else ''}")
    print()

    while True:
        try:
            raw = input("Enter 1 or 2 [Enter = keep default]: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nAborted.")
            sys.exit(0)

        if raw == "":
            return cfg.mode if cfg.mode in ("cli", "api") else "cli"
        if raw == "1":
            return "cli"
        if raw == "2":
            return "api"
        print("  ⚠️  Please enter 1 or 2.")


def _prompt_model() -> str:
    """
    Ask user to choose a provider from the ordered menu.
    Returns a model key (e.g. "openai_ui") or "__use_api__".
    Default = _DEFAULT_MODEL (ChatGPT, option 1).
    """
    print("Select model / provider:")
    for i, (key, label) in enumerate(_PROVIDER_MENU, start=1):
        marker = "  ← default" if key == _DEFAULT_MODEL else ""
        print(f"  {i}. {label}{marker}")
    print()

    n = len(_PROVIDER_MENU)
    while True:
        try:
            raw = input(f"Enter number [1-{n}] [Enter = ChatGPT]: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nAborted.")
            sys.exit(0)

        if raw == "":
            return _DEFAULT_MODEL

        if raw.isdigit():
            idx = int(raw) - 1
            if 0 <= idx < n:
                return _PROVIDER_MENU[idx][0]

        print(f"  ⚠️  Please enter a number between 1 and {n}.")


def _prompt_yes_no(question: str, default_yes: bool = True) -> bool:
    """Interactive yes/no prompt with a default answer."""
    suffix = "[yes/no]"
    default_hint = "yes" if default_yes else "no"
    while True:
        try:
            raw = input(f"{question} {suffix} [Enter = {default_hint}]: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nAborted.")
            sys.exit(0)

        if raw == "":
            return default_yes

        ans = raw.lower()
        if ans in {"y", "yes"}:
            return True
        if ans in {"n", "no"}:
            return False

        print("  ⚠️  Please answer with yes or no.")


def _save_config_safely() -> None:
    """Persist config.json; non-fatal if disk write fails."""
    try:
        cfg.save()
    except Exception as exc:
        print(f"⚠️  Could not save config.json: {exc}")


def _configure_chromium_path_first_time(interactive: bool) -> None:
    """
    On first use (or invalid saved path), ask user for Chromium/Chrome binary path
    and persist it for future runs.
    """
    if cfg.browser_backend != "playwright":
        return

    def _resolve_browser_executable(value: str) -> str:
        candidate = value.strip().strip('"').strip("'")
        if not candidate:
            return ""
        p = Path(candidate)
        if p.exists():
            return str(p)
        resolved = shutil.which(candidate)
        return resolved or ""

    def _detect_browser_executable() -> str:
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

        for item in candidates:
            resolved = _resolve_browser_executable(item)
            if resolved:
                return resolved
        return ""

    openai_cfg = cfg.provider("openai_ui")
    current = str(openai_cfg.get("executable_path", "")).strip()
    resolved_current = _resolve_browser_executable(current)
    if resolved_current:
        if current != resolved_current:
            providers = cfg._data.setdefault("providers", {})
            openai_provider = providers.setdefault("openai_ui", {})
            openai_provider["executable_path"] = resolved_current
            cfg._apply()
            _save_config_safely()
        return

    auto_detected = _detect_browser_executable()
    if auto_detected:
        providers = cfg._data.setdefault("providers", {})
        openai_provider = providers.setdefault("openai_ui", {})
        openai_provider["executable_path"] = auto_detected
        cfg._apply()
        _save_config_safely()
        print(f"✅ Auto-detected Chromium path: {auto_detected}\n")
        return

    if not interactive:
        raise RuntimeError(
            "Playwright backend requires a valid Chromium/Chrome executable path.\n"
            "Set providers.openai_ui.executable_path in agent/config/config.json, "
            "or install Chrome/Chromium, or switch to --browser camoufox."
        )

    print("🛠️  First-time browser setup (Playwright)")
    if current:
        print(f"   Saved path not found: {current}")

    if sys.platform.startswith("win"):
        default_path = current or r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    elif sys.platform.startswith("linux"):
        default_path = current or "google-chrome"
    else:
        default_path = current or "chromium"
    while True:
        raw = input(
            f'Enter Chromium/Chrome executable path [Enter = "{default_path}"]: '
        ).strip()
        candidate = _resolve_browser_executable(raw or default_path)
        if candidate:
            providers = cfg._data.setdefault("providers", {})
            openai_provider = providers.setdefault("openai_ui", {})
            openai_provider["executable_path"] = candidate
            cfg._apply()
            _save_config_safely()
            print("✅ Chromium path saved for next runs.\n")
            return
        print("  ⚠️  Browser not found. Enter a valid path or binary name.")


def _offer_camoufox_fetch_for_background(interactive: bool) -> None:
    """
    Ask once (interactive) to pre-download Camoufox binaries when running in
    headless/background mode, then save the user's choice.
    """
    if cfg.browser_backend != "camoufox":
        return
    if not cfg.headless:
        return
    if cfg.camoufox_fetch_prompted:
        return
    if not interactive:
        return

    print("📦 Camoufox cache setup")
    want_fetch = _prompt_yes_no(
        "Download/cache Camoufox now for faster background (headless) runs?",
        default_yes=True,
    )

    if not want_fetch:
        cfg._data["camoufox_fetch_prompted"] = True
        cfg._apply()
        _save_config_safely()
        print("ℹ️  Skipped Camoufox cache download.\n")
        return

    print("⬇️  Downloading Camoufox browser binaries...")
    cmd = [sys.executable, "-m", "camoufox", "fetch"]
    result = subprocess.run(cmd, check=False)
    if result.returncode == 0:
        cfg._data["camoufox_fetch_prompted"] = True
        cfg._data["camoufox_cached"] = True
        cfg._apply()
        _save_config_safely()
        print("✅ Camoufox binaries cached.\n")
    else:
        cfg._data["camoufox_cached"] = False
        cfg._apply()
        _save_config_safely()
        print(
            "⚠️  Camoufox cache download failed. "
            "You can retry later with: python -m camoufox fetch\n"
        )


def _run_first_time_browser_setup(model: str, interactive: bool) -> None:
    """Run interactive first-time setup for the selected browser backend."""
    if model not in _BROWSER_MODELS:
        return
    _configure_chromium_path_first_time(interactive=interactive)
    _offer_camoufox_fetch_for_background(interactive=interactive)


# ── Playwright worker startup ─────────────────────────────────────────────────

def _start_worker_if_needed(model: str) -> None:
    if model in _BROWSER_MODELS:
        from agent import worker
        print(
            f"🚀 Starting browser context "
            f"[backend={cfg.browser_backend}, headless={cfg.headless}]…"
        )
        worker.start()

        print(f"🌐 Opening tab for {model} and injecting system context…")
        worker.preload(model)
        print(f"✅ {model} is ready.\n")


# ── Mode runners ──────────────────────────────────────────────────────────────

def _run_cli(model: str) -> None:
    _start_worker_if_needed(model)
    from agent.cli import run_cli
    run_cli(model=model)


def _run_api(model: str, host: str, port: int) -> None:
    try:
        import uvicorn
    except ImportError:
        print("❌ uvicorn not installed.  Run: pip install uvicorn[standard]")
        sys.exit(1)

    if model != cfg.default_model:
        cfg._data["default_model"] = model
        cfg.default_model          = model

    print(f"\n🌐 Starting API server at  http://{host}:{port}")
    print(f"   Swagger docs:           http://{host}:{port}/docs")
    print(f"   Default model:          {model}\n")

    uvicorn.run(
        "agent.api_server:app",
        host=host,
        port=port,
        reload=False,
        log_level="info",
    )


# ── Entrypoint ────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="python -m agent.main",
        description="Multi-Provider Browser-Automation LLM Agent",
    )
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument("--cli", action="store_true",
                            help="Skip prompt → run CLI mode")
    mode_group.add_argument("--api", action="store_true",
                            help="Skip prompt → run API server mode")
    parser.add_argument("--model", type=str, default=None,
                        help="Skip model prompt (e.g. --model gemini_ui)")
    parser.add_argument(
        "--browser",
        choices=("playwright", "camoufox"),
        default=None,
        help="Browser backend for UI automation (default: config.json value)",
    )
    vis_group = parser.add_mutually_exclusive_group()
    vis_group.add_argument(
        "--show-browser",
        action="store_true",
        help="Run browser in visible mode (headless=false)",
    )
    vis_group.add_argument(
        "--hide-browser",
        action="store_true",
        help="Run browser in hidden mode (headless=true)",
    )
    parser.add_argument("--host", type=str, default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    # ── 1. Security warning — always first ───────────────────────────────
    _print_security_warning()

    # ── 2. Resolve mode ───────────────────────────────────────────────────
    if args.cli:
        mode = "cli"
    elif args.api:
        mode = "api"
    else:
        mode = _prompt_mode()

    cfg.mode = mode

    # Optional runtime overrides for browser backend / visibility.
    if args.browser is not None:
        cfg.browser_backend = args.browser
    if args.show_browser:
        cfg.headless = False
    elif args.hide_browser:
        cfg.headless = True

    # ── 3. Resolve model ──────────────────────────────────────────────────
    model = args.model if args.model else _prompt_model()
    print()

    # Option 10 "Use API" overrides mode to API server.
    if model == "__use_api__":
        model = cfg.default_model or _DEFAULT_MODEL
        _run_api(model=model, host=args.host, port=args.port)
        return

    # Guard: unimplemented providers fail immediately with a clear message.
    if model in _UNIMPLEMENTED_PROVIDERS:
        raise RuntimeError(f"Provider not implemented: {model}")

    _run_first_time_browser_setup(model=model, interactive=sys.stdin.isatty())

    # ── 4. Dispatch ───────────────────────────────────────────────────────
    if mode == "cli":
        _run_cli(model=model)
    else:
        _run_api(model=model, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
