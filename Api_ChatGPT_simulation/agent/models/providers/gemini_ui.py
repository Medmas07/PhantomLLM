from __future__ import annotations

import re

from agent.models.providers.base_ui import BaseUIProvider, SelectorConfig
from agent import worker as _worker


def _adapt_system_prompt(text: str) -> str:
    """
    Replace any hardcoded model name in the system prompt with "Gemini".
    worker.py always generates prompts that say "You are ChatGPT ...".
    We intercept and fix the persona before sending it to the browser.
    """
    text = re.sub(
        r"You are ChatGPT",
        "You are Gemini",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"\bChatGPT\b",
        "Gemini",
        text,
        flags=re.IGNORECASE,
    )
    return text


# Ã¢â€â‚¬Ã¢â€â‚¬ Selectors Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬

_CSS_INPUT_PRIMARY  = 'div.ql-editor.textarea.new-input-ui[contenteditable="true"]'
_CSS_INPUT_FALLBACK = 'div.ql-editor[contenteditable="true"]'
_XPATH_INPUT_STRUCT = '//rich-textarea//div[contains(@class,"ql-editor") and @contenteditable="true"]'
_XPATH_INPUT_ROLE   = '//div[@role="textbox" and @contenteditable="true"]'

_CSS_SEND_PRIMARY   = 'button.send-button.submit'
_CSS_SEND_FALLBACK  = 'button[aria-label="Envoyer un message"], button[aria-label="Send message"]'
_XPATH_SEND_ICON    = '//button[.//mat-icon[@fonticon="send"]]'
_XPATH_SEND_STRICT  = (
    '//button[(@aria-label="Envoyer un message" or @aria-label="Send message") '
    'and not(@aria-disabled="true")]'
)

_CSS_RESPONSE_PRIMARY  = 'div.markdown-main-panel'
_XPATH_RESPONSE_STRUCT = '//message-content//div[contains(@class,"markdown")]'
_XPATH_RESPONSE_STRICT = '//div[contains(@class,"markdown-main-panel") and @aria-live]'


# Ã¢â€â‚¬Ã¢â€â‚¬ Element resolvers Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬

def _get_input_box(page):
    """
    Resolve the Gemini input field with multi-layer fallback.
    Returns the first visible + editable locator, or None.
    """
    candidates = [
        ("css", _CSS_INPUT_PRIMARY),
        ("css", _CSS_INPUT_FALLBACK),
        ("xpath", _XPATH_INPUT_STRUCT),
        ("xpath", _XPATH_INPUT_ROLE),
    ]
    for kind, sel in candidates:
        try:
            loc = page.locator(sel) if kind == "css" else page.locator(f"xpath={sel}")
            count = loc.count()
            for i in range(count):
                candidate = loc.nth(i)
                try:
                    if candidate.is_visible():
                        return candidate
                except Exception:
                    continue
        except Exception:
            continue
    return None


def _get_send_button(page):
    """
    Resolve the Gemini send button with multi-layer fallback.
    Returns the first visible + enabled locator, or None.
    """
    candidates = [
        ("css",   _CSS_SEND_PRIMARY),
        ("css",   _CSS_SEND_FALLBACK),
        ("xpath", _XPATH_SEND_ICON),
        ("xpath", _XPATH_SEND_STRICT),
    ]
    for kind, sel in candidates:
        try:
            loc = page.locator(sel) if kind == "css" else page.locator(f"xpath={sel}")
            count = loc.count()
            for i in range(count):
                candidate = loc.nth(i)
                try:
                    if not candidate.is_visible():
                        continue
                    disabled = candidate.get_attribute("aria-disabled")
                    if disabled == "true":
                        continue
                    bb = candidate.bounding_box()
                    if bb and bb["width"] > 0:
                        return candidate
                except Exception:
                    continue
        except Exception:
            continue
    return None


def _get_response_container(page):
    """
    Resolve a Gemini response container with multi-layer fallback.
    Returns the locator string that matches visible elements, or None.
    """
    candidates = [
        ("css",   _CSS_RESPONSE_PRIMARY),
        ("xpath", _XPATH_RESPONSE_STRUCT),
        ("xpath", _XPATH_RESPONSE_STRICT),
    ]
    for kind, sel in candidates:
        try:
            loc = page.locator(sel) if kind == "css" else page.locator(f"xpath={sel}")
            if loc.count() > 0:
                return loc
        except Exception:
            continue
    return None


def _get_last_response_locator(page):
    """
    Resolve the last visible Gemini response container locator.
    Returns the locator, or None if nothing is found.
    """
    loc = _get_response_container(page)
    if loc is None:
        return None
    try:
        count = loc.count()
    except Exception:
        return None
    if count <= 0:
        return None
    for i in range(count - 1, -1, -1):
        try:
            candidate = loc.nth(i)
            if candidate.is_visible():
                return candidate
        except Exception:
            continue
    return None


def _extract_last_response_text(page) -> str:
    """
    Return the full text of the last Gemini response container.
    """
    last = _get_last_response_locator(page)
    if last is None:
        return ""
    try:
        text = last.inner_text().strip()
    except Exception:
        return ""
    return text if text else ""


def _response_is_busy(page) -> bool:
    """
    Check whether the last response container is marked busy.
    """
    last = _get_last_response_locator(page)
    if last is None:
        return False
    try:
        return last.get_attribute("aria-busy") == "true"
    except Exception:
        return False


# Ã¢â€â‚¬Ã¢â€â‚¬ Validation helpers Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬

def _validate_input_element(page, element) -> dict:
    """
    Run JS-level validation on the resolved input element.
    Returns dict with exists/editable/visible/textLength.
    Raises RuntimeError on any failed check.
    """
    result = page.evaluate(
        """(el) => {
            if (!el) return { exists: false, editable: false, visible: false, textLength: 0 };
            return {
                exists:     true,
                editable:   el.isContentEditable,
                visible:    el.offsetParent !== null,
                textLength: (el.innerText || '').length,
            };
        }""",
        element.element_handle(),
    )
    if not result.get("exists"):
        raise RuntimeError("INPUT_NOT_FOUND")
    if not result.get("editable"):
        raise RuntimeError("INPUT_NOT_EDITABLE")
    if not result.get("visible"):
        raise RuntimeError("INPUT_NOT_FOUND")
    bb = element.bounding_box()
    if not bb or bb.get("height", 0) <= 0:
        raise RuntimeError("INPUT_NOT_FOUND")
    return result


def _validate_focus(page, element) -> None:
    """
    Assert that the active element is the given element, not a form input.
    """
    result = page.evaluate(
        """(target) => {
            const ae = document.activeElement;
            return {
                tag:     ae ? ae.tagName : '',
                isTarget: ae === target,
            };
        }""",
        element.element_handle(),
    )
    tag = result.get("tag", "")
    if tag in ("INPUT", "TEXTAREA"):
        raise RuntimeError("FOCUS_ERROR")
    if not result.get("isTarget"):
        raise RuntimeError("FOCUS_ERROR")


def _verify_typed_content(page, element, text: str) -> bool:
    try:
        content = element.inner_text(timeout=2000) or ""
        if not content.strip():
            return False

        # Exact-ish check with whitespace normalization.
        content_ws = " ".join(content.split()).lower()
        text_ws = " ".join(text.split()).lower()
        check_ws = text_ws[:80] if len(text_ws) >= 80 else text_ws
        if check_ws and check_ws in content_ws:
            return True

        # Fallback: alnum-only prefix check (robust to punctuation/emoji/UI formatting).
        content_alnum = "".join(ch for ch in content_ws if ch.isalnum())
        text_alnum = "".join(ch for ch in text_ws if ch.isalnum())
        check_alnum = text_alnum[:40] if len(text_alnum) >= 40 else text_alnum
        if check_alnum and check_alnum in content_alnum:
            return True

        # Last fallback: if we typed something non-empty and editor now has substantial text.
        return len(content_ws) >= max(10, min(len(text_ws), 30))
    except Exception:
        return False


def _validate_send_button(page, button) -> None:
    if button is None:
        raise RuntimeError("SEND_BUTTON_NOT_READY")
    try:
        if not button.is_visible():
            raise RuntimeError("SEND_BUTTON_NOT_READY")
        if button.get_attribute("aria-disabled") == "true":
            raise RuntimeError("SEND_BUTTON_NOT_READY")
        bb = button.bounding_box()
        if not bb or bb.get("width", 0) <= 0:
            raise RuntimeError("SEND_BUTTON_NOT_READY")
    except RuntimeError:
        raise
    except Exception:
        raise RuntimeError("SEND_BUTTON_NOT_READY")


# Ã¢â€â‚¬Ã¢â€â‚¬ Provider Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬

class GeminiUIBrowser(BaseUIProvider):

    URL = "https://gemini.google.com/app"

    SELECTORS = SelectorConfig(
        textarea=_CSS_INPUT_FALLBACK,
        response_container=_CSS_RESPONSE_PRIMARY,
        send_button=_CSS_SEND_FALLBACK,
    )

    def send_message(self, page, text: str) -> None:
        self._do_send(page, _adapt_system_prompt(text))

    def _do_send(self, page, text: str) -> None:
        # Ã¢â€â‚¬Ã¢â€â‚¬ Step 1: resolve input box Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
        page.wait_for_timeout(500)
        input_box = None
        for _ in range(3):
            input_box = _get_input_box(page)
            if input_box is not None:
                break
            page.wait_for_timeout(15_000 // 3)
        if input_box is None:
            raise RuntimeError("INPUT_NOT_FOUND")

        # Ã¢â€â‚¬Ã¢â€â‚¬ Step 2: validate element structure Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
        _validate_input_element(page, input_box)

        # Ã¢â€â‚¬Ã¢â€â‚¬ Step 3: click + focus Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
        input_box.click(timeout=5_000)
        page.wait_for_timeout(150)

        # Ã¢â€â‚¬Ã¢â€â‚¬ Step 4: validate focus Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
        _validate_focus(page, input_box)

        # Ã¢â€â‚¬Ã¢â€â‚¬ Step 5: clear content Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
        input_box.press("Control+A")
        page.wait_for_timeout(50)
        input_box.press("Delete")
        page.wait_for_timeout(50)

        # Ã¢â€â‚¬Ã¢â€â‚¬ Step 6: type text Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
        page.keyboard.insert_text(text)
        page.wait_for_timeout(200)

        # Ã¢â€â‚¬Ã¢â€â‚¬ Step 7: verify content Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
        if not _verify_typed_content(page, input_box, text):
            # retry once
            input_box.press("Control+A")
            input_box.press("Delete")
            page.wait_for_timeout(100)
            page.keyboard.insert_text(text)
            page.wait_for_timeout(200)
            if not _verify_typed_content(page, input_box, text):
                raise RuntimeError("INPUT_FAILED")

        # Ã¢â€â‚¬Ã¢â€â‚¬ Step 8: resolve send button Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
        send_btn = None
        for _ in range(3):
            send_btn = _get_send_button(page)
            if send_btn is not None:
                break
            page.wait_for_timeout(5_000 // 3)

        # Ã¢â€â‚¬Ã¢â€â‚¬ Step 9: validate send button Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
        _validate_send_button(page, send_btn)

        # Ã¢â€â‚¬Ã¢â€â‚¬ Step 10: click send Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
        prev_count = self.get_response_count(page)
        try:
            send_btn.click(timeout=3_000)
        except Exception:
            try:
                page.evaluate("(el) => el.click()", send_btn.element_handle())
            except Exception:
                raise RuntimeError("SUBMIT_NOOP")

        generation_started = False
        for _ in range(1_200 // 300):
            page.wait_for_timeout(300)
            btn = _get_send_button(page)
            if btn is None:
                generation_started = True
                break
            if self.get_response_count(page) > prev_count:
                generation_started = True
                break

        if not generation_started:
            try:
                input_box.press("Enter")
            except Exception:
                pass

            for _ in range(20_000 // 300):
                page.wait_for_timeout(300)
                btn = _get_send_button(page)
                if btn is None:
                    generation_started = True
                    break
                if self.get_response_count(page) > prev_count:
                    generation_started = True
                    break

        if not generation_started:
            raise RuntimeError("SUBMIT_NOOP")

    def get_response_count(self, page) -> int:
        loc = _get_response_container(page)
        if loc is None:
            return 0
        try:
            return loc.count()
        except Exception:
            return 0

    def extract_response(self, page, prev_count: int) -> str:
        _ = prev_count
        return _extract_last_response_text(page)

    def wait_for_response(self, page, prev_count: int, timeout: int = 180) -> str:
        _ = prev_count
        POLL_MS = 400
        STABLE_ROUNDS = 4
        import time as _time

        start_time = _time.time()
        last_text = ""
        stable_rounds = 0

        # Phase 1: wait for response start.
        phase1_limit = min(timeout, 30)
        while (_time.time() - start_time) < phase1_limit:
            text = _extract_last_response_text(page)
            if text:
                break
            if self.get_response_count(page) > 0:
                break
            page.wait_for_timeout(POLL_MS)

        # Phase 2: wait for final stabilization.
        while (_time.time() - start_time) < timeout:
            text = _extract_last_response_text(page)
            send_visible = _get_send_button(page) is not None
            busy = _response_is_busy(page)

            if text and text == last_text:
                stable_rounds += 1
            else:
                stable_rounds = 0

            if text and stable_rounds >= STABLE_ROUNDS and (send_visible or not busy):
                return text

            last_text = text
            page.wait_for_timeout(POLL_MS)

        # Timeout fallback.
        return _extract_last_response_text(page)

# Ã¢â€â‚¬Ã¢â€â‚¬ Router-facing generate() Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬

def generate(messages: list[dict], model: str = "gemini", **kwargs) -> str:
    user_turns = [m for m in messages if m.get("role") == "user"]
    if not user_turns:
        raise ValueError("gemini_ui provider requires at least one user-role message.")

    text    = user_turns[-1].get("content", "")
    timeout = int(kwargs.get("timeout", 180))

    return _worker.send(text, model="gemini_ui", timeout=timeout)
