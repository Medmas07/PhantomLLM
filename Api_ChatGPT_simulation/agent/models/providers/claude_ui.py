"""
claude_ui.py – Provider: Claude via claude.ai browser automation.

Selector notes
──────────────
Claude's web interface uses a Lexical (Facebook) rich-text editor, not
ProseMirror. Lexical editors expose a `contenteditable` div but do NOT
update React state through standard DOM mutations, so we use the same
JS-injection approach as openai_ui.py.

Known-stable selectors (2025-Q2):
  textarea           – `div[contenteditable="true"].ProseMirror`
                       Claude switched to ProseMirror after early 2024.
                       If this breaks, inspect the composer div and share
                       its HTML — SelectorAmbiguityError will guide you.
  response_container – `div[data-testid="assistant-message-content"]`
                       Anthropic uses data-testid for automation stability.

If any selector stops matching, SelectorAmbiguityError is raised with
step-by-step inspection instructions.
"""

from agent.models.providers.base_ui import BaseUIProvider, SelectorConfig
from agent import worker as _worker


# ── Browser interaction class ─────────────────────────────────────────────────

class ClaudeUIBrowser(BaseUIProvider):
    """
    Claude.ai web interface driver.

    Selector status: ⚠️ UNTESTED — based on Claude's 2025 HTML structure.
    If selectors fail, SelectorAmbiguityError will print inspection instructions.
    """

    URL = "https://claude.ai/new"

    SELECTORS = SelectorConfig(
        # Claude uses ProseMirror for its composer (2024–2025).
        # If multiple contenteditable divs exist on the page, this may need
        # a more specific ancestor selector such as:
        #   fieldset div.ProseMirror[contenteditable="true"]
        textarea='div.ProseMirror[contenteditable="true"]',

        # Anthropic stabilises these with data-testid attributes.
        response_container='div[data-testid="assistant-message-content"]',

        # Claude submits on Enter (Shift+Enter = newline).
        send_button="",
    )

    def send_message(self, page, text: str) -> None:
        """
        Inject text into Claude's ProseMirror composer and submit with Enter.

        Uses JS injection (same as ChatGPT) because ProseMirror ignores
        standard DOM mutations for React state updates.
        """
        self._check_selector(page, self.SELECTORS.textarea, "textarea")

        box = page.locator(self.SELECTORS.textarea).first  # guard against dupes
        box.wait_for(state="visible", timeout=60_000)
        box.click(force=True)
        page.wait_for_timeout(100)

        box.press("Control+A")
        box.press("Backspace")

        self._inject_text_js(page, self.SELECTORS.textarea, text)
        page.wait_for_timeout(100)
        box.press("Enter")


# ── Router-facing generate() ──────────────────────────────────────────────────

def generate(messages: list[dict], model: str = "claude", **kwargs) -> str:
    """
    Forward the last user message to the Claude browser tab via worker.send().

    Args:
        messages: OpenAI-style message list. Last user turn is forwarded.
        model:    Ignored at runtime; uses whichever Claude model is active.
        **kwargs: timeout (int).

    Returns:
        The assistant's final text response.
    """
    user_turns = [m for m in messages if m.get("role") == "user"]
    if not user_turns:
        raise ValueError("claude_ui provider requires at least one user-role message.")

    text    = user_turns[-1].get("content", "")
    timeout = int(kwargs.get("timeout", 180))

    return _worker.send(text, model="claude_ui", timeout=timeout)