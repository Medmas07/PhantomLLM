"""
cli.py – Interactive CLI loop.

Maintains a full conversation history so API-based providers receive context
from previous turns.

For the openai_ui provider the browser keeps its own session history, so only
the latest message matters — but we accumulate history here anyway so that
switching providers mid-session works transparently.

System prompt injection
───────────────────────
- openai_ui: worker.py injects SYSTEM_CONTEXT into the browser. Nothing extra
  is needed here.
- API providers (Claude, Gemini, …): get_system_prompt() returns
  SYSTEM_CONTEXT_API_CLI which is prepended to the history as a system message
  before the very first user turn.
"""

from agent.config.settings import cfg
from agent.models.router import generate
from agent.protocol.action_parser import strip_actions
from agent.protocol.system_prompt import get_system_prompt


def run_cli(model: str | None = None) -> None:
    """
    Start an interactive chat session in the terminal.

    Args:
        model: Provider key to use (e.g. "openai_ui", "claude").
               Defaults to cfg.default_model if not provided.

    Exits cleanly on:
        - User typing "exit" or "quit"
        - Ctrl-C (KeyboardInterrupt)
        - Ctrl-D / EOF (EOFError, e.g. piped input)
    """
    selected_model = model or cfg.default_model

    print(f"\n🤖 Agent CLI  [model: {selected_model}]")
    print("   Type 'exit' or 'quit' to stop.\n")

    # ── Build initial history ─────────────────────────────────────────────
    # For API providers, prepend the system prompt as the first message.
    # For openai_ui, worker.py already injected it into the browser tab.
    history: list[dict] = []

    system_prompt = get_system_prompt(provider=selected_model, mode="cli")
    if system_prompt:
        history.append({"role": "system", "content": system_prompt})
        print("📋 System prompt injected for API provider.\n")

    # ── Conversation loop ─────────────────────────────────────────────────
    while True:
        try:
            user_input = input(">> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n👋 Goodbye.")
            break

        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit"):
            print("👋 Goodbye.")
            break

        # Append user turn before calling the model
        history.append({"role": "user", "content": user_input})

        try:
            response = generate(selected_model, history)
        except (RuntimeError, TimeoutError, ValueError) as exc:
            # Remove the failed turn so the user can retry cleanly
            history.pop()
            print(f"\n❌ Error: {exc}\n")
            continue
        except Exception as exc:
            history.pop()
            print(f"\n💥 Unexpected error: {exc}\n")
            continue

        # Keep full response in history (ACTION blocks preserved for context),
        # but display only the clean human-readable text to the user.
        history.append({"role": "assistant", "content": response})
        print(f"\n{strip_actions(response)}\n")
        print("-" * 60)
