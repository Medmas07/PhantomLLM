"""
perplexity_ui.py – Provider: Perplexity AI via perplexity.ai browser automation.

Selector notes
──────────────
Perplexity uses a standard <textarea> for its search/chat input (2025).
This is the simplest input type — Playwright's page.fill() works directly.

Known selectors (2025-Q2):
  textarea           – `textarea[placeholder]`
                       Perplexity's main input is a textarea with a placeholder.
                       More specific: `textarea[placeholder="Ask anything…"]`
                       but placeholder text changes; the generic form is safer.
  response_container – `div[class*="prose"]`
                       Perplexity renders responses in Tailwind "prose" containers.

⚠️  UNTESTED — if selectors fail, SelectorAmbiguityError will print
step-by-step HTML inspection instructions.
"""

from agent.models.providers.base_ui import BaseUIProvider, SelectorConfig
from agent import worker as _worker


# ── Browser interaction class ─────────────────────────────────────────────────

class PerplexityUIBrowser(BaseUIProvider):
    """
    Perplexity AI web interface driver.

    Uses a standard <textarea> — no JS injection required.
    Selector status: ⚠️ UNTESTED.
    """

    URL = "https://www.perplexity.ai"

    SELECTORS = SelectorConfig(
        # Standard textarea. Perplexity's placeholder text has varied over time;
        # using attribute-presence rather than attribute-value for stability.
        # If multiple textareas exist, use "textarea[data-testid='search-input']"
        # or inspect and share the HTML.
        textarea="textarea[placeholder]",

        # Perplexity wraps each answer in a prose-styled div.
        # Alternatives: "[class*='answer']", "div.answer-header + div"
        response_container='div[class*="prose"]',

        # Perplexity submits on Enter.
        send_button="",
    )

    def send_message(self, page, text: str) -> None:
        """
        Fill Perplexity's textarea and press Enter to submit.

        Standard page.fill() is used (native textarea, no framework wrapping).
        """
        self._check_selector(page, self.SELECTORS.textarea, "textarea")

        box = page.locator(self.SELECTORS.textarea).first
        box.wait_for(state="visible", timeout=60_000)
        box.click()
        box.fill("")    # clear any previous query
        box.fill(text)
        page.wait_for_timeout(100)

        if self.SELECTORS.send_button:
            page.click(self.SELECTORS.send_button)
        else:
            box.press("Enter")


# ── Router-facing generate() ──────────────────────────────────────────────────

def generate(messages: list[dict], model: str = "perplexity", **kwargs) -> str:
    """
    Forward the last user message to the Perplexity browser tab via worker.send().
    """
    user_turns = [m for m in messages if m.get("role") == "user"]
    if not user_turns:
        raise ValueError("perplexity_ui provider requires at least one user-role message.")

    text    = user_turns[-1].get("content", "")
    timeout = int(kwargs.get("timeout", 180))

    return _worker.send(text, model="perplexity_ui", timeout=timeout)
