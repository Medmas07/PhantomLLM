from __future__ import annotations

import time
import threading
from enum import Enum

from agent.models.providers.base_ui import BaseUIProvider, SelectorConfig
from agent import worker as _worker


_TEXTAREA_SELECTOR = 'div[contenteditable="true"][data-lexical-editor="true"]#ask-input'
_RESPONSE_SELECTOR = 'div[id^="markdown-content-"]'

_SMALL_POPUP_ROOT  = 'div.fixed.bottom-md.right-md, div.fixed[class*="bottom-md"][class*="right-md"]'
_SMALL_POPUP_CLOSE = 'button[aria-label="Fermer"], button[aria-label="Close"]'

_HARD_DIALOG_ROOT  = 'div[role="dialog"][aria-modal="true"]'
_HARD_MODAL_INNER  = '[data-testid="login-modal"]'
_HARD_BACK_BTN     = 'button:has-text("Retour à l\'accueil"), button:has-text("Back to home")'
_HARD_EMAIL_INPUT  = 'input[type="email"], input[name="email"], input[placeholder*="mail"]'

_LOOP_TIMEOUT_S    = 120
_LOOP_TICK_MS      = 400


class LoginState(str, Enum):
    NONE        = "none"
    SMALL_POPUP = "small_popup"
    HARD        = "hard"


class PerplexityUIBrowser(BaseUIProvider):

    URL = "https://www.perplexity.ai"

    SELECTORS = SelectorConfig(
        textarea=_TEXTAREA_SELECTOR,
        response_container=_RESPONSE_SELECTOR,
        send_button="",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._send_lock            = threading.Lock()
        self._last_sent_text       = None
        self._last_login_action_ts = 0.0

    # ── Structural popup helpers ─────────────────────────────────────────────

    def _get_small_popup(self, page):
        base  = page.locator(_SMALL_POPUP_ROOT)
        count = base.count()
        for i in range(count):
            candidate = base.nth(i)
            try:
                if not candidate.is_visible():
                    continue
                if candidate.locator(_SMALL_POPUP_CLOSE).count() > 0:
                    return candidate
            except Exception:
                continue
        return None

    def _small_popup_visible(self, page) -> bool:
        return self._get_small_popup(page) is not None

    def _get_hard_dialog(self, page):
        base  = page.locator(_HARD_DIALOG_ROOT)
        count = base.count()
        for i in range(count):
            candidate = base.nth(i)
            try:
                if not candidate.is_visible():
                    continue
                if candidate.locator(_HARD_MODAL_INNER).count() == 0:
                    continue
                has_back  = candidate.locator(_HARD_BACK_BTN).count() > 0
                has_email = candidate.locator(_HARD_EMAIL_INPUT).count() > 0
                if has_back or has_email:
                    return candidate
            except Exception:
                continue
        return None

    def _hard_login_visible(self, page) -> bool:
        return self._get_hard_dialog(page) is not None

    def detect_login_state(self, page) -> LoginState:
        if self._hard_login_visible(page):
            return LoginState.HARD
        if self._small_popup_visible(page):
            return LoginState.SMALL_POPUP
        return LoginState.NONE

    # ── Cooldown ─────────────────────────────────────────────────────────────

    def _login_cooldown(self) -> bool:
        now = time.time()
        if (now - self._last_login_action_ts) < 2.0:
            return True
        self._last_login_action_ts = now
        return False

    # ── Response state ───────────────────────────────────────────────────────

    def _response_exists(self, page) -> bool:
        try:
            loc = page.locator(_RESPONSE_SELECTOR)
            if loc.count() == 0:
                return False
            return len(loc.last.inner_text(timeout=2000).strip()) > 20
        except Exception:
            return False

    def _request_started(self, page) -> bool:
        try:
            return page.locator(_RESPONSE_SELECTOR).count() > 0
        except Exception:
            return False

    # ── Editor helpers ───────────────────────────────────────────────────────

    def _editor_ready(self, page) -> bool:
        result = page.evaluate("""
            () => {
                const el = document.querySelector('#ask-input');
                if (!el) return 'MISSING';
                if (!el.isContentEditable) return 'NOT_EDITABLE';
                if (el.offsetParent === null) return 'NOT_VISIBLE';
                return 'OK';
            }
        """)
        return result == "OK"

    def _active_is_input(self, page) -> bool:
        tag = page.evaluate("() => document.activeElement?.tagName ?? ''")
        return tag in ("INPUT", "TEXTAREA")

    def _focus_editor(self, page) -> bool:
        """Click and focus #ask-input. Returns False if focus lands on INPUT/TEXTAREA."""
        try:
            box = page.locator(self.SELECTORS.textarea).first
            box.wait_for(state="visible", timeout=5_000)
            box.click()
            page.evaluate("document.querySelector('#ask-input')?.focus()")
        except Exception:
            return False
        return not self._active_is_input(page)

    def _clear_editor(self, page) -> None:
        page.evaluate("""
            () => {
                const el = document.querySelector('#ask-input');
                if (el) {
                    el.innerHTML = '';
                    el.dispatchEvent(new Event('input', { bubbles: true }));
                }
            }
        """)

    def _verify_input(self, page, text: str) -> bool:
        try:
            content = page.locator(self.SELECTORS.textarea).first.inner_text(timeout=2000)
            check   = text[:30] if len(text) >= 30 else text
            return check in content
        except Exception:
            return False

    # ── Login handlers ───────────────────────────────────────────────────────

    def _close_small_popup(self, page) -> None:
        popup = self._get_small_popup(page)
        if popup is None:
            return
        btn = popup.locator(_SMALL_POPUP_CLOSE).first
        try:
            btn.click(timeout=3000)
        except Exception:
            pass
        try:
            popup.wait_for(state="hidden", timeout=4000)
        except Exception:
            pass

    def _reset_hard_login(self, page) -> str:
        """Clear perplexity cookies and reload. Returns 'recovered' or 'resend'."""
        current_url = page.url
        context     = page.context

        try:
            cookies = context.cookies()
            context.clear_cookies()
            non_perplexity = [
                c for c in cookies
                if "perplexity.ai" not in c.get("domain", "")
            ]
            if non_perplexity:
                context.add_cookies(non_perplexity)
        except Exception:
            try:
                context.clear_cookies()
            except Exception:
                pass

        page.goto(current_url, timeout=60_000)
        page.wait_for_load_state("domcontentloaded")
        page.wait_for_timeout(1000)

        return "recovered" if self._response_exists(page) else "resend"

    # ── Control loop ─────────────────────────────────────────────────────────

    def _send_with_control_loop(self, page, text: str) -> None:
        deadline    = time.time() + _LOOP_TIMEOUT_S
        sent        = False
        type_retry  = 0
        submit_retry = 0

        while True:
            if time.time() > deadline:
                raise RuntimeError("CONTROL_LOOP_TIMEOUT")

            # ── Step 1: classify current UI state ────────────────────────────
            login_state = self.detect_login_state(page)

            if login_state == LoginState.HARD:
                if self._login_cooldown():
                    page.wait_for_timeout(_LOOP_TICK_MS)
                    continue
                outcome = self._reset_hard_login(page)
                if outcome == "recovered":
                    self._last_sent_text = text
                    return
                sent = False
                continue

            if login_state == LoginState.SMALL_POPUP:
                self._close_small_popup(page)
                continue

            # ── Step 2: check if already done ────────────────────────────────
            if sent and self._response_exists(page):
                return

            if sent and self._request_started(page):
                # streaming has started — wait for real content
                page.wait_for_timeout(_LOOP_TICK_MS)
                continue

            # ── Step 3: editor must be ready before typing ───────────────────
            if not self._editor_ready(page):
                page.wait_for_timeout(_LOOP_TICK_MS)
                continue

            # ── Step 4: type and submit ───────────────────────────────────────
            if not sent:
                # Guard: hard login must not be present before we touch the editor
                if self._hard_login_visible(page):
                    continue

                focused = self._focus_editor(page)
                if not focused:
                    # Focus landed on an input field — bail out for this tick
                    page.wait_for_timeout(_LOOP_TICK_MS)
                    continue

                # Guard again after focus (login can appear on focus event)
                if self._hard_login_visible(page):
                    continue

                self._clear_editor(page)

                page.keyboard.type(text, delay=10)

                # Guard after typing (login can appear after keypress)
                if self._hard_login_visible(page):
                    continue

                if not self._verify_input(page, text):
                    type_retry += 1
                    if type_retry > 3:
                        raise RuntimeError("INPUT_FAILED_AFTER_RETRIES")
                    self._clear_editor(page)
                    page.wait_for_timeout(300)
                    continue

                # Focus must still be on the contenteditable, not a form field
                if self._active_is_input(page):
                    page.wait_for_timeout(_LOOP_TICK_MS)
                    continue

                page.locator(self.SELECTORS.textarea).first.press("Enter")
                sent = True
                self._last_sent_text = text
                page.wait_for_timeout(600)
                continue

            # ── Step 5: submitted but no response yet — check submit worked ──
            if sent and not self._request_started(page):
                submit_retry += 1
                if submit_retry > 4:
                    raise RuntimeError("SUBMIT_NOOP")
                page.wait_for_timeout(_LOOP_TICK_MS)
                continue

            page.wait_for_timeout(_LOOP_TICK_MS)

    # ── Public API ───────────────────────────────────────────────────────────

    def send_message(self, page, text: str) -> None:
        with self._send_lock:
            if self._last_sent_text == text:
                return
            self._send_with_control_loop(page, text)


# ── Router ───────────────────────────────────────────────────────────────────

def generate(messages: list[dict], model: str = "perplexity", **kwargs) -> str:
    user_turns = [m for m in messages if m.get("role") == "user"]

    if not user_turns:
        raise ValueError("perplexity_ui requires user message")

    text    = user_turns[-1]["content"]
    timeout = int(kwargs.get("timeout", 180))

    return _worker.send(text, model="perplexity_ui", timeout=timeout)