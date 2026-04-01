"""
main.py – Unified entrypoint for the multi-provider LLM agent.

Run as a module from the project root:
    python -m agent.main            ← interactive mode + model selection (default)
    python -m agent.main --cli      ← skip prompt, go straight to CLI
    python -m agent.main --api      ← skip prompt, go straight to API server
    python -m agent.main --cli --model claude   ← CLI forced to Claude

Prompt behaviour (when no --cli / --api flag is given):
    1. Ask: "Select mode:  1. CLI  2. API"
    2. Ask: "Select model: 1. openai_ui  2. claude  ..."
    config.json values are shown as defaults/suggestions, never auto-selected.
"""

import argparse
import sys

from agent.config.settings import cfg

# ── Available providers shown in the interactive menu ─────────────────────────
# (key, display label, extra info shown to user)
_PROVIDER_MENU: list[tuple[str, str]] = [
    ("openai_ui",   "ChatGPT via browser     (Playwright – no API key needed)"),
    ("claude",      "Anthropic Claude        (requires ANTHROPIC_API_KEY)"),
    ("gemini",      "Google Gemini           (requires GOOGLE_API_KEY)"),
    ("deepseek",    "DeepSeek                (requires DEEPSEEK_API_KEY)"),
    ("groq",        "Groq fast inference     (requires GROQ_API_KEY)"),
    ("qwen",        "Alibaba Qwen            (requires DASHSCOPE_API_KEY)"),
    ("perplexity",  "Perplexity AI           (requires PERPLEXITY_API_KEY)"),
    ("mock",        "Mock / no-op            (testing – no API key needed)"),
]

_OPENAI_UI_ALIASES = frozenset({
    "openai_ui", "chatgpt", "gpt-4", "gpt-4o", "gpt-3.5-turbo"
})


# ── Interactive prompts ───────────────────────────────────────────────────────

def _prompt_mode() -> str:
    """
    Ask the user to choose a run mode.
    Shows config.json value as a hint but always waits for explicit input.

    Returns: "cli" or "api"
    """
    default_hint = f"  (current default in config.json: {cfg.mode!r})"
    print("\nSelect mode:")
    print(f"  1. CLI interactive{default_hint if cfg.mode == 'cli' else ''}")
    print(f"  2. API server (localhost){default_hint if cfg.mode == 'api' else ''}")
    print()

    while True:
        try:
            raw = input("Enter 1 or 2 [or press Enter for default]: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nAborted.")
            sys.exit(0)

        if raw == "":
            # Accept the config.json default
            return cfg.mode if cfg.mode in ("cli", "api") else "cli"
        if raw == "1":
            return "cli"
        if raw == "2":
            return "api"

        print("  ⚠️  Please enter 1 or 2.")


def _prompt_model() -> str:
    """
    Ask the user to choose a provider / model.
    Shows config.json default_model as the pre-selected option.

    Returns: provider key string (e.g. "openai_ui", "claude", …)
    """
    default_key   = cfg.default_model
    default_index = next(
        (i for i, (k, _) in enumerate(_PROVIDER_MENU) if k == default_key),
        0,
    )

    print("\nSelect model / provider:")
    for i, (key, label) in enumerate(_PROVIDER_MENU, start=1):
        marker = " ← default" if key == default_key else ""
        print(f"  {i}. {label}{marker}")
    print()

    while True:
        try:
            raw = input(
                f"Enter number [1-{len(_PROVIDER_MENU)}] "
                f"or press Enter for default ({default_key}): "
            ).strip()
        except (EOFError, KeyboardInterrupt):
            print("\nAborted.")
            sys.exit(0)

        if raw == "":
            return default_key  # Accept config.json default

        if raw.isdigit():
            idx = int(raw) - 1
            if 0 <= idx < len(_PROVIDER_MENU):
                return _PROVIDER_MENU[idx][0]

        print(f"  ⚠️  Please enter a number between 1 and {len(_PROVIDER_MENU)}.")


# ── Playwright worker startup ─────────────────────────────────────────────────

def _start_worker_if_needed(model: str) -> None:
    """Start the Playwright worker thread if the chosen model uses the browser."""
    if model in _OPENAI_UI_ALIASES:
        from agent import worker
        print(f"🚀 Starting Playwright worker for model {model!r}…")
        worker.start()   # Blocks until browser ready; raises on failure


# ── Mode runners ──────────────────────────────────────────────────────────────

def _run_cli(model: str) -> None:
    """Start the interactive CLI loop."""
    _start_worker_if_needed(model)

    from agent.cli import run_cli
    run_cli(model=model)


def _run_api(model: str, host: str, port: int) -> None:
    """Start the FastAPI server via uvicorn."""
    try:
        import uvicorn
    except ImportError:
        print(
            "❌ uvicorn is not installed.\n"
            "   Install it with:  pip install uvicorn[standard]"
        )
        sys.exit(1)

    # Override the live settings so the API server uses the selected provider
    # without requiring the user to edit config.json first.
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
    Parse CLI arguments, resolve mode + model, and launch the correct runner.

    When flags are absent the user is ALWAYS prompted interactively.
    config.json values are shown as suggestions / defaults, never auto-selected.
    """
    parser = argparse.ArgumentParser(
        prog="python -m agent.main",
        description="ChatGPT Simulation – Multi-Provider LLM Agent",
    )

    # Mode flags (mutually exclusive)
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--cli", action="store_true",
        help="Skip prompt and run in CLI interactive mode",
    )
    mode_group.add_argument(
        "--api", action="store_true",
        help="Skip prompt and run as local API server (FastAPI + uvicorn)",
    )

    parser.add_argument(
        "--model", type=str, default=None,
        help="Skip model prompt and use this provider (e.g. --model claude)",
    )
    parser.add_argument(
        "--host", type=str, default="127.0.0.1",
        help="API server bind address (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port", type=int, default=8000,
        help="API server port (default: 8000)",
    )

    args = parser.parse_args()

    # ── Resolve mode ──────────────────────────────────────────────────────
    # Flags take priority; otherwise always ask the user interactively.
    if args.cli:
        mode = "cli"
    elif args.api:
        mode = "api"
    else:
        # No flag → always prompt, regardless of config.json
        mode = _prompt_mode()

    # ── Resolve model ─────────────────────────────────────────────────────
    # --model flag takes priority; otherwise always ask the user interactively.
    if args.model:
        model = args.model
    else:
        # No flag → always prompt, regardless of config.json
        model = _prompt_model()

    print()  # Visual separator before launch output

    # ── Dispatch ──────────────────────────────────────────────────────────
    if mode == "cli":
        _run_cli(model=model)
    else:
        _run_api(model=model, host=args.host, port=args.port)


if __name__ == "__main__":
    main()