"""
base_ui.py – Abstract base class for ALL browser-driven UI providers.

Design principles
─────────────────
* Selectors are NEVER scattered through method bodies.
  Every selector lives in the SELECTORS class variable (SelectorConfig).
* When a selector produces 0 matches the system stops immediately and prints
  actionable guidance asking the user to supply the current HTML snippet.
  It does NOT guess, fall-back silently, or continue with wrong data.
* The default wait_for_response() polling loop handles streaming + <ACTION> blocks
  and can be overridden per-provider if the provider uses a loading indicator.
* get_active_textarea() is a stub for a future browser-extension layer.

Subclass checklist
──────────────────
  class MyProvider(BaseUIProvider):
      URL       = "https://..."
      SELECTORS = SelectorConfig(
          textarea           = "CSS selector for input",
          response_container = "CSS selector for ONE assistant message block",
          send_button        = "CSS selector for send btn (empty → use Enter)",
          loading_indicator  = "CSS selector while generating (optional)",
      )

      def send_message(self, page, text: str) -> None: ...   ← MUST implement
"""

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass


# ── Selector mismatch error ───────────────────────────────────────────────────

class SelectorAmbiguityError(Exception):
    """
    Raised when a CSS selector finds 0 elements in the live DOM.

    The error message contains step-by-step instructions for the user to
    inspect the page and share the correct HTML so the selector can be updated.
    It is caught by worker.py and returned as an error response to the caller.
    """


# ── Selector configuration dataclass ─────────────────────────────────────────

@dataclass
class SelectorConfig:
    """
    All CSS selectors for one provider, grouped in one place.

    Fields
    ──────
    textarea           Required. The main text input (contenteditable div
                       or <textarea>). Used by send_message().
    response_container Required. Matches ONE assistant message block.
                       Used by get_response_count() and extract_response().
    send_button        Optional. Click to submit. If empty, Enter key is used.
    loading_indicator  Optional. Present while the model is generating.
                       If set, wait_for_response() waits for it to disappear
                       instead of using the stability-polling approach.
    """
    textarea:           str = ""
    response_container: str = ""
    send_button:        str = ""
    loading_indicator:  str = ""


# ── Abstract base provider ────────────────────────────────────────────────────

class BaseUIProvider(ABC):
    """
    Abstract base for every Playwright-driven LLM provider.

    Subclasses MUST define:
        URL       (str)           – the chat URL to navigate to
        SELECTORS (SelectorConfig) – CSS selectors for this provider's DOM

    Subclasses MUST implement:
        send_message(page, text)  – type text and submit

    Subclasses MAY override:
        get_response_count()      – default: count SELECTORS.response_container
        extract_response()        – default: inner_text of new response elements
        wait_for_response()       – default: stability-polling loop
        ensure_loaded()           – default: navigate + wait for textarea
        is_loaded()               – default: domain check on page.url
    """

    URL: str = ""
    SELECTORS: SelectorConfig = None  # type: ignore  # must be set in subclass

    # ── Abstract interface ────────────────────────────────────────────────────

    @abstractmethod
    def send_message(self, page, text: str) -> None:
        """
        Type `text` into the input field and submit it.

        Implementation must:
          1. Locate the textarea using SELECTORS.textarea
          2. Call self._check_selector() first to detect DOM changes early
          3. Clear existing content
          4. Inject text (JS for contenteditable, page.fill() for <textarea>)
          5. Submit (Enter key OR click SELECTORS.send_button)
        """

    # ── Concrete methods (override only if provider behaviour differs) ────────

    def get_response_count(self, page) -> int:
        """Return the current number of assistant message elements in the DOM."""
        return page.locator(self.SELECTORS.response_container).count()

    def extract_response(self, page, prev_count: int) -> str:
        """
        Return the concatenated inner text of all assistant messages
        added to the DOM since prev_count.
        """
        items = page.locator(self.SELECTORS.response_container)
        count = items.count()
        parts = [
            items.nth(i).inner_text().strip()
            for i in range(prev_count, count)
        ]
        return "\n\n".join(p for p in parts if p)

    def wait_for_response(self, page, prev_count: int, timeout: int = 180) -> str:
        """
        Poll the DOM until a new, fully-streamed assistant response is stable.

        Algorithm:
          Phase 1 – Wait for at least one new message element to appear.
          Phase 2 – Poll every 250 ms; consider response "done" when the text
                    has been identical for STABLE_ROUNDS consecutive polls AND
                    there is no open (unclosed) <ACTION> tag.

        If SELECTORS.loading_indicator is set, Phase 2 instead waits for that
        element to disappear (more reliable for providers that use a spinner).
        """
        POLL_MS       = 250
        STABLE_ROUNDS = 4
        start = time.time()

        # ── Phase 1: wait for a new message to appear ─────────────────────
        while self.get_response_count(page) <= prev_count:
            if time.time() - start > timeout:
                return ""
            page.wait_for_timeout(POLL_MS)

        # ── Phase 2a: loading indicator variant ───────────────────────────
        if self.SELECTORS.loading_indicator:
            # Wait for the spinner/stop-button to disappear
            try:
                page.wait_for_selector(
                    self.SELECTORS.loading_indicator,
                    state="hidden",
                    timeout=(timeout - int(time.time() - start)) * 1000,
                )
            except Exception:
                pass  # timeout fallthrough; extract whatever is there
            return self.extract_response(page, prev_count)

        # ── Phase 2b: stability-polling variant ───────────────────────────
        last   = ""
        stable = 0
        while True:
            text = self.extract_response(page, prev_count)

            # An unclosed <ACTION> means the model is still streaming
            if "<ACTION>" in text and "</ACTION>" not in text:
                stable = 0
            elif text == last and text:
                stable += 1
            else:
                stable = 0

            last = text

            if stable >= STABLE_ROUNDS:
                break
            if time.time() - start > timeout:
                break

            page.wait_for_timeout(POLL_MS)

        return last

    def ensure_loaded(self, page, login_timeout: int = 300_000) -> None:
        """
        Ensure the tab is on the correct provider page and the textarea is visible.

        Navigation rules:
          - If the page URL is about:blank (new empty tab) → navigate to self.URL.
          - If is_loaded() returns False (user navigated away) → navigate back.
          - Otherwise (page already on provider domain) → do NOT navigate;
            the tab keeps its current conversation intact.

        After any navigation a 3 s SPA hydration pause is applied before
        checking for the textarea.
        """
        current_url = page.url
        needs_nav = (
            not current_url
            or current_url in ("about:blank", "")
            or not self.is_loaded(page)
        )

        if needs_nav:
            page.goto(self.URL, timeout=60_000)
            page.wait_for_timeout(3_000)  # SPA hydration pause

        # Fast path: textarea visible → ready
        try:
            page.wait_for_selector(self.SELECTORS.textarea, timeout=10_000)
            return
        except Exception:
            pass

        # Slow path: textarea not found — prompt for manual login
        name = self.__class__.__name__
        print(f"\n⚠️  LOGIN REQUIRED — Please log in to {name} in the browser window.")
        print(f"   Waiting up to {login_timeout // 60_000} min for login…")
        try:
            page.wait_for_selector(self.SELECTORS.textarea, timeout=login_timeout)
            print(f"✅ {name}: login detected. Ready.\n")
        except Exception:
            raise RuntimeError(
                f"Login timeout for {name}. "
                "Please log in manually and retry your message."
            )

    def is_loaded(self, page) -> bool:
        """
        Return True if the current tab URL belongs to this provider.
        Compares the domain part of self.URL against page.url.
        """
        try:
            domain = self.URL.split("//", 1)[1].split("/")[0]  # e.g. "chat.openai.com"
            return domain in page.url
        except Exception:
            return False

    # ── Protected helpers (for use inside send_message implementations) ───────

    def _check_selector(self, page, selector: str, context: str = "") -> None:
        """
        Verify that `selector` matches at least one element in the live DOM.

        Raises SelectorAmbiguityError with user-friendly HTML-inspection
        instructions if the selector produces 0 matches.

        Should be called at the TOP of send_message() before any interaction.
        """
        if not selector:
            raise SelectorAmbiguityError(
                f"[{self.__class__.__name__}] Selector for '{context}' is not configured.\n"
                f"Open SELECTORS in agent/models/providers/{self.__module__.split('.')[-1]}.py "
                "and set the correct CSS selector."
            )

        try:
            count = page.locator(selector).count()
        except Exception as exc:
            raise SelectorAmbiguityError(
                f"[{self.__class__.__name__}] Selector evaluation error for '{context}':\n"
                f"  selector : {selector!r}\n"
                f"  error    : {exc}\n"
                "Please share the current HTML of this element."
            ) from exc

        if count == 0:
            sep = "═" * 62
            raise SelectorAmbiguityError(
                f"\n{sep}\n"
                f"  SELECTOR NOT FOUND — {self.__class__.__name__} / {context}\n"
                f"{sep}\n"
                f"  Expected selector : {selector!r}\n"
                f"  Current URL       : {page.url}\n"
                f"\n"
                f"  The web interface HTML may have changed.\n"
                f"\n"
                f"  TO FIX:\n"
                f"    1. Open {self.URL} in the browser\n"
                f"    2. Right-click the {context} element → Inspect\n"
                f"    3. Copy the HTML of that element\n"
                f"    4. Share it here — the selector will be updated\n"
                f"{sep}"
            )

    def _inject_text_js(self, page, selector: str, text: str) -> None:
        """
        Inject text into a contenteditable element via JavaScript.

        Required for ProseMirror, Lexical, and Quill editors where
        Playwright's page.fill() / page.type() do not trigger the
        framework's internal state correctly.
        """
        page.evaluate(
            """([sel, txt]) => {
                const el = document.querySelector(sel);
                if (!el) return;
                el.focus();
                el.innerText = txt;
                el.dispatchEvent(new InputEvent('input', {
                    bubbles: true,
                    cancelable: true,
                    inputType: 'insertText',
                    data: txt,
                }));
            }""",
            [selector, text],
        )

    # ── Future extension stub ─────────────────────────────────────────────────

    def get_active_textarea(self):
        """
        [FUTURE INTERFACE] Dynamically detect the active textarea.

        This stub is reserved for a future browser-extension layer that will
        allow this agent to work with any LLM chat interface without
        hardcoded selectors.

        Currently every provider uses its own SELECTORS.textarea.
        When this is implemented it will replace that hardcoded approach.
        """
        raise NotImplementedError(
            "get_active_textarea() is reserved for future browser-extension support."
        )