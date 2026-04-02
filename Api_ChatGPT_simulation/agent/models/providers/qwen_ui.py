"""
qwen_ui.py – Provider: Alibaba Qwen via chat.qwen.ai browser automation.

Selector notes
──────────────
Qwen's web interface (2025) uses a React-based chat UI hosted at chat.qwen.ai
(formerly tongyi.aliyun.com/qianwen). The input field is a contenteditable div.

Known selectors (2025-Q2):
  textarea           – `div[contenteditable="true"]#chat-input`
                       Best-guess; Qwen may use an id or data attribute.
  response_container – `div[class*="markdown-content"]`
                       Qwen renders responses as markdown inside a specific div.

⚠️  UNTESTED — these selectors are best-guesses. If they fail,
SelectorAmbiguityError will print step-by-step HTML inspection instructions.
Inspect the textarea and an assistant reply block, then share their HTML here.
"""

from agent.models.providers.base_ui import BaseUIProvider, SelectorConfig
from agent import worker as _worker


# ── Browser interaction class ─────────────────────────────────────────────────

class QwenUIBrowser(BaseUIProvider):
    """
    Alibaba Qwen chat.qwen.ai web interface driver.

    Selector status: ⚠️ UNTESTED — inspect and update selectors if they fail.
    """

    URL = "https://chat.qwen.ai"

    SELECTORS = SelectorConfig(
        # Qwen's input field. Alternatives to try if this fails:
        #   textarea[placeholder]
        #   div[contenteditable="true"][data-placeholder]
        textarea='div[contenteditable="true"]',

        # Each assistant response block. Alternatives:
        #   ".ai-message", "[class*='answer']", "div.agent-content"
        response_container='div[class*="markdown"]',

        # Qwen may require clicking a send button instead of pressing Enter.
        # Update this if Enter alone doesn't submit.
        send_button='button[aria-label="Send"]',
    )

    def send_message(self, page, text: str) -> None:
        """
        Inject text into Qwen's contenteditable input and submit.

        Tries the send button first; falls back to Enter key.
        """
        self._check_selector(page, self.SELECTORS.textarea, "textarea")

        box = page.locator(self.SELECTORS.textarea).first
        box.wait_for(state="visible", timeout=60_000)
        box.click(force=True)
        page.wait_for_timeout(100)

        box.press("Control+A")
        box.press("Backspace")

        self._inject_text_js(page, self.SELECTORS.textarea, text)
        page.wait_for_timeout(150)

        if self.SELECTORS.send_button:
            try:
                btn = page.locator(self.SELECTORS.send_button)
                btn.wait_for(state="visible", timeout=5_000)
                btn.click()
                return
            except Exception:
                pass

        box.press("Enter")


# ── Router-facing generate() ──────────────────────────────────────────────────

def generate(messages: list[dict], model: str = "qwen", **kwargs) -> str:
    """
    Forward the last user message to the Qwen browser tab via worker.send().
    """
    user_turns = [m for m in messages if m.get("role") == "user"]
    if not user_turns:
        raise ValueError("qwen_ui provider requires at least one user-role message.")

    text    = user_turns[-1].get("content", "")
    timeout = int(kwargs.get("timeout", 180))

    return _worker.send(text, model="qwen_ui", timeout=timeout)
