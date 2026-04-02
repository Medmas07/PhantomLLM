"""
deepseek_ui.py – Provider: DeepSeek via chat.deepseek.com browser automation.

Selector notes
──────────────
DeepSeek's chat interface (2025) uses a standard <textarea> element for input,
unlike ProseMirror/Quill. Playwright's page.fill() works correctly here.

Known selectors (2025-Q2):
  textarea           – `textarea#chat-input`
                       DeepSeek uses a stable id on its textarea.
  response_container – `div.ds-markdown`
                       DeepSeek wraps assistant markdown responses in this class.

⚠️  UNTESTED — if selectors fail, SelectorAmbiguityError will print
step-by-step HTML inspection instructions.
"""

from agent.models.providers.base_ui import BaseUIProvider, SelectorConfig
from agent import worker as _worker


# ── Browser interaction class ─────────────────────────────────────────────────

class DeepSeekUIBrowser(BaseUIProvider):
    """
    DeepSeek chat.deepseek.com web interface driver.

    Uses a standard <textarea> for input (no JS injection needed).
    """

    URL = "https://chat.deepseek.com"

    SELECTORS = SelectorConfig(
        # Standard textarea with a stable id.
        # If this fails, inspect the input element and look for textarea[placeholder].
        textarea="textarea#chat-input",

        # DeepSeek wraps each assistant reply in a div.ds-markdown block.
        # Alternative selectors to try: ".message-content", "[class*='markdown']"
        response_container="div.ds-markdown",

        # DeepSeek submits on Enter (Shift+Enter = newline).
        send_button="",
    )

    def send_message(self, page, text: str) -> None:
        """
        Clear the textarea, type the message, and press Enter to submit.

        Standard page.fill() is sufficient since DeepSeek uses a native textarea
        (no framework wrapping the input state).
        """
        self._check_selector(page, self.SELECTORS.textarea, "textarea")

        box = page.locator(self.SELECTORS.textarea)
        box.wait_for(state="visible", timeout=60_000)
        box.click()
        box.fill("")       # clear any draft
        box.fill(text)
        page.wait_for_timeout(100)

        if self.SELECTORS.send_button:
            page.click(self.SELECTORS.send_button)
        else:
            box.press("Enter")


# ── Router-facing generate() ──────────────────────────────────────────────────

def generate(messages: list[dict], model: str = "deepseek", **kwargs) -> str:
    """
    Forward the last user message to the DeepSeek browser tab via worker.send().
    """
    user_turns = [m for m in messages if m.get("role") == "user"]
    if not user_turns:
        raise ValueError("deepseek_ui provider requires at least one user-role message.")

    text    = user_turns[-1].get("content", "")
    timeout = int(kwargs.get("timeout", 180))

    return _worker.send(text, model="deepseek_ui", timeout=timeout)
