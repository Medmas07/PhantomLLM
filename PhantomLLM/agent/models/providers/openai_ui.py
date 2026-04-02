"""
openai_ui.py – Provider: ChatGPT via Playwright browser automation.

Two parts
─────────
1. OpenAIUIBrowser (class) – used by worker.py to drive the ChatGPT tab.
   Selectors confirmed working as of 2025-Q2.

2. generate() (function)   – called by router.py; delegates to worker.send().
"""

from agent.models.providers.base_ui import BaseUIProvider, SelectorConfig
from agent import worker as _worker


# ── Browser interaction class ─────────────────────────────────────────────────

class OpenAIUIBrowser(BaseUIProvider):
    """
    ChatGPT web interface driver.

    Selectors status: ✅ CONFIRMED WORKING (tested by user, 2025).

    Input:   ProseMirror contenteditable div with id=prompt-textarea.
    Output:  div elements carrying data-message-author-role="assistant".
    """

    URL = "https://chat.openai.com"

    SELECTORS = SelectorConfig(
        # The ProseMirror composer — the id makes this highly stable.
        textarea='div.ProseMirror#prompt-textarea[contenteditable="true"]',

        # Every assistant turn is wrapped in this div.
        response_container='div[data-message-author-role="assistant"]',

        # ChatGPT submits on Enter; no explicit send button needed.
        send_button="",
    )

    def is_loaded(self, page) -> bool:
        """
        ChatGPT redirects chat.openai.com → chatgpt.com.
        Accept either domain so ensure_loaded() never re-navigates mid-session.
        """
        url = page.url
        return "chat.openai.com" in url or "chatgpt.com" in url

    def send_message(self, page, text: str) -> None:
        """
        Clear the composer, inject text via JS, and press Enter.

        JavaScript injection is required because ProseMirror does not expose
        a standard input event; page.fill() bypasses its internal state.
        """
        self._check_selector(page, self.SELECTORS.textarea, "textarea")

        box = page.locator(self.SELECTORS.textarea)
        box.wait_for(state="visible", timeout=60_000)
        box.click(force=True)
        page.wait_for_timeout(100)

        # Clear any draft that may exist
        box.press("Control+A")
        box.press("Backspace")

        # Inject via JS so ProseMirror's React state updates correctly
        self._inject_text_js(page, self.SELECTORS.textarea, text)
        page.wait_for_timeout(100)
        box.press("Enter")


# ── Router-facing generate() ──────────────────────────────────────────────────

def generate(messages: list[dict], model: str = "gpt-4", **kwargs) -> str:
    """
    Forward the last user message to the ChatGPT browser tab via worker.send().

    Args:
        messages: OpenAI-style message list. Only the last user turn is sent
                  (the browser tab retains its own conversation history).
        model:    Ignored at runtime; the tab uses whichever model is active.
        **kwargs: timeout (int) – max seconds to wait for response.

    Returns:
        The assistant's final text response.
    """
    user_turns = [m for m in messages if m.get("role") == "user"]
    if not user_turns:
        raise ValueError("openai_ui provider requires at least one user-role message.")

    text    = user_turns[-1].get("content", "")
    timeout = int(kwargs.get("timeout", 180))

    # "openai_ui" is the key used by worker.py to look up OpenAIUIBrowser
    return _worker.send(text, model="openai_ui", timeout=timeout)