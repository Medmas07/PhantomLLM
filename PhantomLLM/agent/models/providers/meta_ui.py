from __future__ import annotations

import re
import time

from agent.models.providers.base_ui import BaseUIProvider, SelectorConfig
from agent import worker as _worker


_DIALOG_SELECTOR = 'div[role="dialog"]'
_YEAR_SELECTOR = '[aria-label="Ann\\u00e9e"]'
_YEAR_2000_SELECTOR = "text=2000"
_CONTINUE_ENABLED_SELECTOR = (
    'button[data-slot="button"]:not([disabled]):not([aria-disabled="true"])'
)
_INPUT_SELECTOR = (
    'input[placeholder*="Posez"], '
    'input[placeholder*="Demandez"], '
    'input[placeholder*="question"], '
    'input[placeholder*="Ask"]'
)
_SEND_ENABLED_SELECTOR = (
    'button[aria-label="Envoyer"][data-slot="button"]:not([disabled]):not([aria-disabled="true"])'
)
_RESPONSE_SELECTOR = "div.ur-markdown"


def _is_system_context_text(text: str) -> bool:
    return "You are ChatGPT" in text or "ACTION MODE RULES" in text


def _adapt_system_prompt(text: str) -> str:
    if not _is_system_context_text(text):
        return text
    text = re.sub(r"You are ChatGPT", "You are Meta AI", text, flags=re.IGNORECASE)
    text = re.sub(r"\bChatGPT\b", "Meta AI", text, flags=re.IGNORECASE)
    return text


def _first_visible(locator):
    try:
        count = locator.count()
    except Exception:
        return None
    for i in range(count):
        item = locator.nth(i)
        try:
            if item.is_visible():
                return item
        except Exception:
            continue
    return None


def _dialog_is_visible(page) -> bool:
    dialog = _first_visible(page.locator(_DIALOG_SELECTOR))
    return dialog is not None


def _handle_age_popup(page) -> None:
    dialog = _first_visible(page.locator(_DIALOG_SELECTOR))
    if dialog is None:
        return

    try:
        year_selector = _first_visible(page.locator(_YEAR_SELECTOR))
        if year_selector is None:
            raise RuntimeError("META_SEND_FAILED")
        year_selector.click(timeout=5_000)

        year_2000 = _first_visible(page.locator(_YEAR_2000_SELECTOR))
        if year_2000 is None:
            raise RuntimeError("META_SEND_FAILED")
        year_2000.click(timeout=5_000)

        continue_button = _first_visible(page.locator(_CONTINUE_ENABLED_SELECTOR))
        if continue_button is None:
            raise RuntimeError("META_SEND_FAILED")
        continue_button.wait_for(state="visible", timeout=5_000)
        continue_button.click(timeout=5_000)

        dialog.wait_for(state="hidden", timeout=10_000)
    except Exception as exc:
        raise RuntimeError("META_SEND_FAILED") from exc


def _find_input_box(page):
    candidates = page.locator(_INPUT_SELECTOR)
    try:
        count = candidates.count()
    except Exception:
        return None

    for i in range(count):
        item = candidates.nth(i)
        try:
            if not item.is_visible():
                continue
            if item.get_attribute("disabled") is not None:
                continue
            if item.get_attribute("readonly") is not None:
                continue
            return item
        except Exception:
            continue
    return None


def _wait_for_input_box(page, timeout: int = 20) -> object:
    deadline = time.time() + timeout
    while time.time() < deadline:
        _handle_age_popup(page)
        if _dialog_is_visible(page):
            _handle_age_popup(page)
        input_box = _find_input_box(page)
        if input_box is not None:
            try:
                input_box.wait_for(state="visible", timeout=1_000)
                return input_box
            except Exception:
                pass
        time.sleep(0.2)
    raise RuntimeError("META_SEND_FAILED")


def _wait_for_enabled_send_button(page, timeout: int = 10) -> object:
    deadline = time.time() + timeout
    while time.time() < deadline:
        _handle_age_popup(page)
        if _dialog_is_visible(page):
            _handle_age_popup(page)
        send_button = _first_visible(page.locator(_SEND_ENABLED_SELECTOR))
        if send_button is not None:
            try:
                send_button.wait_for(state="visible", timeout=1_000)
                return send_button
            except Exception:
                pass
        time.sleep(0.2)
    raise RuntimeError("META_SEND_FAILED")


def _verify_input_value(input_box, expected: str) -> bool:
    try:
        value = input_box.input_value(timeout=2_000)
    except Exception:
        return False
    expected_norm = " ".join(expected.split()).strip().lower()
    value_norm = " ".join(value.split()).strip().lower()
    if not expected_norm:
        return not value_norm
    if value_norm == expected_norm:
        return True
    if len(expected_norm) >= 32:
        return expected_norm[:32] in value_norm
    return False


def _read_input_value(input_box) -> str:
    try:
        return input_box.input_value(timeout=1_000) or ""
    except Exception:
        return ""


def _message_send_started(page, input_box, prev_count: int, baseline_value: str) -> bool:
    now_count = _get_response_count(page)
    if now_count > prev_count:
        return True

    current_value = _read_input_value(input_box).strip()
    if baseline_value.strip() and current_value != baseline_value.strip():
        return True

    # Some UIs disable send while generating.
    if _first_visible(page.locator(_SEND_ENABLED_SELECTOR)) is None:
        return True

    return False


def _send_prompt(page, prompt: str, *, prefer_fill: bool = False) -> None:
    _handle_age_popup(page)
    if _dialog_is_visible(page):
        _handle_age_popup(page)
        if _dialog_is_visible(page):
            raise RuntimeError("META_SEND_FAILED")

    input_box = _wait_for_input_box(page, timeout=20)

    try:
        input_box.click(timeout=3_000)
        input_box.press("Control+A")
        input_box.press("Backspace")
        input_box.fill(prompt, timeout=10_000)
        if not prefer_fill and not _verify_input_value(input_box, prompt):
            input_box.type(prompt, delay=8, timeout=10_000)
    except Exception:
        _handle_age_popup(page)
        if _dialog_is_visible(page):
            raise RuntimeError("META_SEND_FAILED")
        try:
            input_box = _wait_for_input_box(page, timeout=10)
            input_box.click(timeout=3_000)
            input_box.fill("", timeout=5_000)
            input_box.fill(prompt, timeout=5_000)
        except Exception as exc:
            raise RuntimeError("META_SEND_FAILED") from exc

    if not _verify_input_value(input_box, prompt):
        raise RuntimeError("META_SEND_FAILED")

    send_button = _wait_for_enabled_send_button(page, timeout=10)
    prev_count = _get_response_count(page)
    baseline_value = _read_input_value(input_box)

    if _dialog_is_visible(page):
        _handle_age_popup(page)
        if _dialog_is_visible(page):
            raise RuntimeError("META_SEND_FAILED")

    # Multi-attempt submit path to avoid silent no-op clicks.
    submit_errors: list[Exception] = []
    submit_attempts = (
        "click",
        "js_click",
        "press_enter",
    )
    for attempt in submit_attempts:
        try:
            if attempt == "click":
                send_button.click(timeout=5_000)
            elif attempt == "js_click":
                handle = send_button.element_handle()
                if handle is None:
                    raise RuntimeError("META_SEND_FAILED")
                page.evaluate("(el) => el.click()", handle)
            else:
                input_box.press("Enter", timeout=3_000)
        except Exception as exc:
            submit_errors.append(exc)
            continue

        deadline = time.time() + 4
        while time.time() < deadline:
            if _message_send_started(page, input_box, prev_count, baseline_value):
                return
            time.sleep(0.2)

    if submit_errors:
        raise RuntimeError("META_SEND_FAILED") from submit_errors[-1]
    raise RuntimeError("META_SEND_FAILED")


def _get_response_count(page) -> int:
    try:
        return page.locator(_RESPONSE_SELECTOR).count()
    except Exception:
        return 0


def _extract_last_response(page) -> str:
    loc = page.locator(_RESPONSE_SELECTOR)
    try:
        count = loc.count()
    except Exception:
        return ""

    if count == 0:
        return ""

    try:
        return loc.nth(count - 1).inner_text().strip()
    except Exception:
        return ""


def _wait_for_response(page, prev_count: int, timeout: int = 60) -> str:
    start_time = time.time()
    has_new_block = False

    while time.time() - start_time < timeout:
        count = _get_response_count(page)
        if count > prev_count:
            has_new_block = True
            break
        time.sleep(0.3)

    if not has_new_block:
        raise RuntimeError("META_SEND_FAILED")

    last_text = ""
    stable_rounds = 0

    while time.time() - start_time < timeout:
        text = _extract_last_response(page)

        if text == last_text:
            stable_rounds += 1
        else:
            stable_rounds = 0

        if text and stable_rounds >= 3:
            return text

        last_text = text
        time.sleep(0.4)

    final_text = _extract_last_response(page)
    if not final_text:
        raise RuntimeError("META_SEND_FAILED")
    return final_text


class MetaUIBrowser(BaseUIProvider):
    URL = "https://meta.ai/"

    SELECTORS = SelectorConfig(
        textarea=_INPUT_SELECTOR,
        response_container=_RESPONSE_SELECTOR,
        send_button='button[aria-label="Envoyer"]',
    )

    def ensure_loaded(self, page, login_timeout: int = 300_000) -> None:
        current_url = page.url
        needs_nav = (
            not current_url
            or current_url in ("about:blank", "")
            or not self.is_loaded(page)
        )
        if needs_nav:
            page.goto(self.URL, timeout=60_000)
            page.wait_for_timeout(2_000)

        timeout_s = max(10, int(login_timeout / 1000))
        _wait_for_input_box(page, timeout=timeout_s)
        _handle_age_popup(page)

    def send_message(self, page, text: str) -> None:
        adapted_text = _adapt_system_prompt(text)
        is_system_context = _is_system_context_text(text)
        try:
            _send_prompt(page, adapted_text, prefer_fill=is_system_context)
        except RuntimeError:
            if is_system_context:
                # Preload system-context must never crash startup for Meta UI.
                return
            raise

    def get_response_count(self, page) -> int:
        return _get_response_count(page)

    def extract_response(self, page, prev_count: int) -> str:
        _ = prev_count
        return _extract_last_response(page)

    def wait_for_response(self, page, prev_count: int, timeout: int = 60) -> str:
        return _wait_for_response(page, prev_count, timeout=timeout)


def generate(messages: list[dict], model: str = "meta", **kwargs) -> str:
    user_turns = [m for m in messages if m.get("role") == "user"]
    if not user_turns:
        raise ValueError("meta_ui provider requires at least one user-role message.")

    text = user_turns[-1].get("content", "")
    timeout = int(kwargs.get("timeout", 180))
    return _worker.send(text, model="meta_ui", timeout=timeout)
