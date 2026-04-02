"""
grok_ui.py – Provider: Grok (xAI) via grok.com browser automation.

This is xAI's Grok chatbot — NOT to be confused with Groq (inference platform).

Selector notes
──────────────
Grok's web interface (2025) is a React SPA. The input is a contenteditable div.

Known selectors (2025-Q2):
  textarea           – `div[contenteditable="true"][data-lexical-editor="true"]`
                       Grok uses Facebook's Lexical editor.
  response_container – `div[class*="message-bubble"][data-testid*="assistant"]`
                       Best-guess — may need updating after DOM inspection.

⚠️  UNTESTED — if selectors fail, SelectorAmbiguityError will print
step-by-step HTML inspection instructions. Inspect the input area and
the assistant reply container, then share their HTML here.

Note on URL: Grok is available at https://grok.com. If the interface moves
(e.g. back to x.com/i/grok), update URL below.
"""

from agent.models.providers.base_ui import BaseUIProvider, SelectorConfig
from agent import worker as _worker


# ── Browser interaction class ─────────────────────────────────────────────────

class GrokUIBrowser(BaseUIProvider):
    """
    Grok (xAI) web interface driver.

    Selector status: ⚠️ UNTESTED — selectors are best-guess based on Lexical editor pattern.
    """

    URL = "https://grok.com"

    SELECTORS = SelectorConfig(
        # Grok uses the Lexical editor (same Facebook library as Meta products).
        # The data-lexical-editor="true" attribute is Lexical's stable marker.
        textarea='div[contenteditable="true"][data-lexical-editor="true"]',

        # Grok assistant messages — update this selector after DOM inspection.
        # Right-click an assistant reply → Inspect → look for a stable container.
        response_container='div[data-testid="grok-message"][data-sender="grok"]',

        # Grok submits on Enter.
        send_button="",
    )

    def send_message(self, page, text: str) -> None:
        """
        Inject text into Grok's Lexical editor and press Enter to submit.

        Lexical (like ProseMirror) ignores direct DOM mutations, so we use
        JS injection to set text and fire the input event.
        """
        self._check_selector(page, self.SELECTORS.textarea, "textarea")

        box = page.locator(self.SELECTORS.textarea).first
        box.wait_for(state="visible", timeout=60_000)
        box.click(force=True)
        page.wait_for_timeout(100)

        box.press("Control+A")
        box.press("Backspace")

        self._inject_text_js(page, self.SELECTORS.textarea, text)
        page.wait_for_timeout(100)
        box.press("Enter")


# ── Router-facing generate() ──────────────────────────────────────────────────

def generate(messages: list[dict], model: str = "grok", **kwargs) -> str:
    """
    Forward the last user message to the Grok browser tab via worker.send().
    """
    user_turns = [m for m in messages if m.get("role") == "user"]
    if not user_turns:
        raise ValueError("grok_ui provider requires at least one user-role message.")

    text    = user_turns[-1].get("content", "")
    timeout = int(kwargs.get("timeout", 180))

    return _worker.send(text, model="grok_ui", timeout=timeout)
