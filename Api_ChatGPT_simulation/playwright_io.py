# playwright_io.py
import time
import json
import re
import random

ACTION_RE = re.compile(r"<ACTION>\s*(\{.*?\})\s*</ACTION>", re.DOTALL)
TYPE_DELAY_BASE = 18
POLL_INTERVAL = 0.25
STABLE_ROUNDS = 4
TIMEOUT = 240
def human_delay():
    return random.randint(TYPE_DELAY_BASE - 5, TYPE_DELAY_BASE + 7)
def send_message(page, msg: str):
    box = page.locator('div.ProseMirror#prompt-textarea[contenteditable="true"]')
    box.wait_for(state="visible", timeout=60000)

    box.click(force=True)
    time.sleep(0.2)

    box.press("Control+A")
    box.press("Backspace")

    page.evaluate(
        """(text) => {
            const el = document.querySelector('div.ProseMirror#prompt-textarea');
            if (!el) return;
            el.focus();
            el.innerText = text;
            el.dispatchEvent(new Event('input', { bubbles: true }));
        }""",
        msg
    )

    time.sleep(0.2)
    box.press("Enter")

def wait_for_response_bundle(page, prev_count, timeout=180):
    print("⏳ Réponse en cours...\n")
    start = time.time()

    items = page.locator('div[data-message-author-role="assistant"]')

    while True:
        count = items.count()
        if count > prev_count:
            break
        if time.time() - start > timeout:
            print("⚠️ Timeout : aucune réponse détectée.")
            return ""
        time.sleep(0.25)

    last_snapshot = ""
    stable = 0

    while True:
        count = items.count()
        msgs = [items.nth(i).inner_text().strip() for i in range(prev_count, count)]
        text = "\n\n".join(m for m in msgs if m)

        if "<ACTION>" in text and "</ACTION>" not in text:
            stable = 0
        elif text == last_snapshot and text:
            stable += 1
        else:
            stable = 0

        if stable >= 4:
            break

        if time.time() - start > timeout:
            break

        last_snapshot = text
        time.sleep(0.25)

    print("🤖", text)
    print("-" * 60)
    return text

# def stream_actions(page, prev_count: int):
#     items = page.locator('div[data-message-author-role="assistant"]')
#     executed = []
#     seen_spans = set()
#
#     start = time.time()
#
#     while True:
#         count = items.count()
#         msgs = [items.nth(i).inner_text() for i in range(prev_count, count)]
#         text = "\n\n".join(msgs)
#
#         for m in ACTION_RE.finditer(text):
#             span = m.span()
#             if span in seen_spans:
#                 continue
#
#             payload = json.loads(m.group(1))
#             result = execute_actions(payload)
#             executed.append(result)
#             seen_spans.add(span)
#
#             send_message(page, json.dumps({"type": "TOOL_RESULT", "data": result}))
#
#         if time.time() - start > TIMEOUT:
#             break
#
#         time.sleep(POLL_INTERVAL)
#
#     return executed
