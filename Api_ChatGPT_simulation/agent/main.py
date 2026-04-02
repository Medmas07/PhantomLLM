"""
main.py – Unified entrypoint for the multi-provider browser-automation agent.

Run modes
─────────
    python -m agent.main            ← interactive mode + model selection
    python -m agent.main --cli      ← skip prompt, direct CLI
    python -m agent.main --api      ← skip prompt, direct API server
    python -m agent.main --cli --model claude

Startup sequence
────────────────
    1. Print security warning  (MANDATORY — printed before any browser launch)
    2. Prompt for mode         (unless --cli / --api flag given)
    3. Prompt for model        (unless --model flag given)
    4. Start Playwright worker (if selected model uses browser)
    5. Launch CLI or API server
"""

import argparse
import sys

from agent.config.settings import cfg


# ── Security warning (MANDATORY — printed before anything else) ───────────────

def _print_security_warning() -> None:
    """
    Print the mandatory security warning before any browser is launched.
    This is non-optional and must appear on every startup.
    """
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


# ── Available providers for the interactive menu ──────────────────────────────

_PROVIDER_MENU: list[tuple[str, str]] = [
    ("openai_ui",   "ChatGPT      (chat.openai.com)"),
    ("claude_ui",   "Claude       (claude.ai)"),
    ("gemini_ui",   "Gemini       (gemini.google.com)"),
    ("deepseek_ui", "DeepSeek     (chat.deepseek.com)"),
    ("grok_ui",     "Grok / xAI   (grok.com)"),
    ("qwen_ui",     "Qwen         (chat.qwen.ai)"),
    ("perplexity_ui","Perplexity  (perplexity.ai)"),
    ("mock",        "Mock         (no browser — testing only)"),
]

# Models that require the Playwright worker
_BROWSER_MODELS = frozenset(k for k, _ in _PROVIDER_MENU if k != "mock")


# ── Interactive prompts ───────────────────────────────────────────────────────

def _prompt_mode() -> str:
    """Ask user to choose CLI or API mode. Shows config.json default as hint."""
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
    Ask user to choose a provider. Shows config.json default_model as hint.
    Returns the provider key (e.g. "openai_ui", "claude_ui", …).
    """
    default_key = cfg.default_model

    print("Select model / provider:")
    for i, (key, label) in enumerate(_PROVIDER_MENU, start=1):
        marker = "  ← default" if key == default_key else ""
        print(f"  {i}. {label}{marker}")
    print()

    while True:
        try:
            raw = input(
                f"Enter number [1-{len(_PROVIDER_MENU)}] "
                f"[Enter = {default_key}]: "
            ).strip()
        except (EOFError, KeyboardInterrupt):
            print("\nAborted.")
            sys.exit(0)

        if raw == "":
            return default_key

        if raw.isdigit():
            idx = int(raw) - 1
            if 0 <= idx < len(_PROVIDER_MENU):
                return _PROVIDER_MENU[idx][0]

        print(f"  ⚠️  Please enter a number between 1 and {len(_PROVIDER_MENU)}.")


# ── Playwright worker startup ─────────────────────────────────────────────────

def _start_worker_if_needed(model: str) -> None:
    """
    Start the Playwright worker and eagerly open the tab + inject the system
    prompt for the selected model, so the browser is fully ready before the
    user types their first message.
    """
    if model in _BROWSER_MODELS:
        from agent import worker
        print(f"🚀 Starting browser context…")
        worker.start()   # blocks until browser context is open

        print(f"🌐 Opening tab for {model} and injecting system context…")
        worker.preload(model)   # opens tab, waits for login if needed, injects prompt
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

    # Propagate selected model to the live settings so api_server uses it
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
    """
    Parse arguments, print security warning, prompt for mode + model,
    then launch the selected runner.

    Flags bypass the interactive prompts:
        --cli / --api   skip mode prompt
        --model <name>  skip model prompt
    """
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
                        help="Skip model prompt (e.g. --model claude_ui)")
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
        mode = _prompt_mode()   # always interactive when no flag given

    # Write mode back to the live cfg singleton so worker.py and api_server.py
    # both see the user's runtime choice, not the stale config.json value.
    cfg.mode = mode

    # ── 3. Resolve model ──────────────────────────────────────────────────
    model = args.model if args.model else _prompt_model()
    print()

    # ── 4. Dispatch ───────────────────────────────────────────────────────
    if mode == "cli":
        _run_cli(model=model)
    else:
        _run_api(model=model, host=args.host, port=args.port)


if __name__ == "__main__":
    main()