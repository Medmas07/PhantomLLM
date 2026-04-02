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
import sys

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
    ("gemini_ui",     "Gemini       (gemini.google.com)  (pending)"),
    ("meta_ui",       "Meta AI      (https://meta.ai/) (pending)"),
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
    "perplexity_ui",
    "claude_ui",
    "deepseek_ui",
    "grok_ui",
    "qwen_ui",
})

# Providers that have no implementation yet — fail fast with a clear message.
_UNIMPLEMENTED_PROVIDERS: frozenset[str] = frozenset({
    "meta_ui",
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


# ── Playwright worker startup ─────────────────────────────────────────────────

def _start_worker_if_needed(model: str) -> None:
    if model in _BROWSER_MODELS:
        from agent import worker
        print(f"🚀 Starting browser context…")
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

    # ── 4. Dispatch ───────────────────────────────────────────────────────
    if mode == "cli":
        _run_cli(model=model)
    else:
        _run_api(model=model, host=args.host, port=args.port)


if __name__ == "__main__":
    main()