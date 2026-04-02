"""
gemini_ui.py – Provider: Google Gemini via gemini.google.com browser automation.

Selector notes
──────────────
Gemini's web interface uses a Quill rich-text editor wrapped in a custom
`<rich-textarea>` web component. The editable div is `.ql-editor` inside it.

Known-stable selectors (2025-Q2):
  textarea           – `rich-textarea .ql-editor`
                       The Quill editor inside Google's custom web component.
  response_container – `div.response-container`  (or `model-response`)
                       Gemini wraps each model turn in a container element.

⚠️  Gemini's DOM changes frequently. If selectors fail, SelectorAmbiguityError
will print step-by-step HTML inspection instructions.

Submission note: Gemini submits via the send button (Enter alone may insert
a newline in Quill). We use the send button selector as the primary submit
method with an Enter fallback.
"""

from agent.models.providers.base_ui import BaseUIProvider, SelectorConfig
from agent import worker as _worker


# ── Browser interaction class ─────────────────────────────────────────────────

class GeminiUIBrowser(BaseUIProvider):
    """
    Google Gemini web interface driver.

    Selector status: ⚠️ UNTESTED — based on Gemini's 2025 HTML structure.
    If selectors fail, SelectorAmbiguityError will print inspection instructions.
    """

    URL = "https://gemini.google.com/app"

    SELECTORS = SelectorConfig(
        # Quill editor inside Gemini's <rich-textarea> web component.
        # If this fails, inspect the input area and look for [contenteditable="true"].
        textarea='rich-textarea .ql-editor[contenteditable="true"]',

        # Each Gemini model response is wrapped in a container element.
        # Alternatives to try if this fails: "model-response", ".response-container"
        response_container="model-response",

        # Gemini has a dedicated send button (paper-plane icon).
        # If the button selector changes, check for a button with aria-label="Send message"
        send_button='button[aria-label="Send message"]',
    )

    def send_message(self, page, text: str) -> None:
        """
        Inject text into the Quill editor and click the send button.

        Quill's internal state is managed via its API; we use JS injection
        to set the text and fire an input event so Quill registers it.
        Then we click the send button (Enter inserts a newline in Quill).
        """
        self._check_selector(page, self.SELECTORS.textarea, "textarea")

        box = page.locator(self.SELECTORS.textarea).first
        box.wait_for(state="visible", timeout=60_000)
        box.click()
        page.wait_for_timeout(100)

        # Clear via keyboard — Ctrl+A + Delete works in Quill
        box.press("Control+A")
        box.press("Delete")

        self._inject_text_js(page, self.SELECTORS.textarea, text)
        page.wait_for_timeout(150)

        # Prefer button click; fall back to Enter if button not found
        if self.SELECTORS.send_button:
            try:
                btn = page.locator(self.SELECTORS.send_button)
                btn.wait_for(state="visible", timeout=5_000)
                btn.click()
                return
            except Exception:
                pass  # fallback to Enter

        box.press("Enter")


# ── Router-facing generate() ──────────────────────────────────────────────────

def generate(messages: list[dict], model: str = "gemini", **kwargs) -> str:
    """
    Forward the last user message to the Gemini browser tab via worker.send().

    Args:
        messages: OpenAI-style message list. Last user turn is forwarded.
        model:    Ignored at runtime; uses whichever Gemini model is active.
        **kwargs: timeout (int).

    Returns:
        The assistant's final text response.
    """
    user_turns = [m for m in messages if m.get("role") == "user"]
    if not user_turns:
        raise ValueError("gemini_ui provider requires at least one user-role message.")

    text    = user_turns[-1].get("content", "")
    timeout = int(kwargs.get("timeout", 180))

    return _worker.send(text, model="gemini_ui", timeout=timeout)