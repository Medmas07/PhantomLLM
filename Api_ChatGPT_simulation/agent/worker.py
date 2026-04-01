"""
worker.py – Playwright browser worker thread.

NON-NEGOTIABLE RULES
─────────────────────
1. Playwright MUST run in a single dedicated thread (_playwright_worker).
2. No Playwright import or call is allowed outside this module.
3. All communication with the outside world goes through the module-level
   queues (_request_queue / _response_queue).

Architecture
────────────
External code (providers, API handlers, CLI) calls send() which:
    a) Enqueues a (request_id, payload) tuple on _request_queue
    b) Blocks waiting for the matching result on _response_queue

The worker thread:
    a) Reads from _request_queue
    b) Types the message into the ChatGPT browser textarea
    c) Waits for the model to finish streaming
    d) If the response contains an <ACTION> block → executes the tools
       and sends TOOL_RESULT back to ChatGPT
    e) Puts the final result on _response_queue

Public API
──────────
    start()        – Launch the thread (blocks until browser is ready)
    is_ready()     – True once browser is initialised
    get_error()    – Last crash message, or None
    get_status()   – Dict snapshot for the /status endpoint
    send(text, timeout) – Blocking request, returns response text

Extensibility note (requirement 8)
────────────────────────────────────
The textarea interaction is localised in _ui_send_message().
The selector is NOT hardcoded elsewhere.
A future browser-extension layer can replace this function with a call to
utils.detect_active_textarea() without touching the rest of the module.
"""

import random
import threading
import time
from queue import Empty, Queue


# ── Module-level state (private) ──────────────────────────────────────────────

_request_queue:  "Queue[tuple[str, dict]]" = Queue()
_response_queue: "Queue[dict]"             = Queue()

_browser_ready:        bool      = False
_system_context_sent:  bool      = False
_worker_error:         str|None  = None
_worker_thread:        threading.Thread|None = None


# ── Public API ────────────────────────────────────────────────────────────────

def is_ready() -> bool:
    """Return True once the browser is open and SYSTEM_CONTEXT has been sent."""
    return _browser_ready


def get_error() -> str | None:
    """Return the crash message if the worker has failed, else None."""
    return _worker_error


def get_status() -> dict:
    """Return a status snapshot suitable for the /status HTTP endpoint."""
    return {
        "browser_ready":       _browser_ready,
        "system_context_sent": _system_context_sent,
        "worker_error":        _worker_error,
    }


def send(text: str, timeout: int = 180) -> str:
    """
    Send a message to the ChatGPT browser and block until a response arrives.

    This function is thread-safe and can be called from multiple threads
    simultaneously (e.g. concurrent API requests).  Responses are matched
    to callers by a unique request ID so they cannot be mis-delivered.

    Args:
        text:    The user message to send.
        timeout: Maximum seconds to wait for the response.

    Returns:
        The assistant's final text (after any tool calls have been resolved).

    Raises:
        RuntimeError: Worker crashed or browser not ready.
        TimeoutError: No response within `timeout` seconds.
    """
    if _worker_error:
        raise RuntimeError(f"Playwright worker error: {_worker_error}")
    if not _browser_ready:
        raise RuntimeError("Playwright browser is not ready yet.")

    # Unique ID so concurrent callers can match their response
    req_id = f"req-{int(time.time() * 1000)}-{random.randint(1000, 9999)}"

    _request_queue.put((req_id, {"text": text, "timeout": timeout}))

    deadline = time.time() + timeout

    while time.time() < deadline:
        try:
            result = _response_queue.get(timeout=0.5)

            if result.get("id") == req_id:
                # This is our response
                if result.get("ok"):
                    return result.get("response", "")
                raise RuntimeError(result.get("error", "Unknown worker error"))
            else:
                # Belongs to another concurrent caller – put it back
                _response_queue.put(result)
                time.sleep(0.01)

        except Empty:
            pass  # Keep waiting

    raise TimeoutError(
        f"Playwright worker did not respond within {timeout} seconds."
    )


def start() -> None:
    """
    Launch the Playwright worker thread and block until the browser is ready.

    Idempotent: calling start() when the thread is already alive is a no-op.

    Raises:
        RuntimeError: If the worker fails to initialise within 120 seconds.
    """
    global _worker_thread

    if _worker_thread and _worker_thread.is_alive():
        return  # Already running

    _worker_thread = threading.Thread(
        target=_playwright_worker,
        name="playwright-worker",
        daemon=True,   # Exits automatically when the main process exits
    )
    _worker_thread.start()

    # Block until ready or error
    deadline = time.time() + 120
    while time.time() < deadline:
        if _browser_ready:
            return
        if _worker_error:
            raise RuntimeError(
                f"Playwright worker failed to start: {_worker_error}"
            )
        time.sleep(0.2)

    raise RuntimeError(
        "Timed out waiting for the Playwright browser to start (120s)."
    )


# ── Private: textarea interaction ──────────────────────────────────────────────
# Localised here so a future browser-extension layer only needs to replace
# this single function (see utils.detect_active_textarea stub).

def _ui_send_message(page, msg: str) -> None:
    """
    Type `msg` into the ChatGPT composer textarea and submit it.

    Implementation notes:
    - We inject via JavaScript instead of keyboard simulation to correctly
      handle multiline content and avoid timing issues with the React state.
    - page.wait_for_timeout() is used instead of time.sleep() wherever
      possible so Playwright can service its internal event loop.
    - The CSS selector is kept here and ONLY here (not spread across the file).
    """
    # Selector for ChatGPT's ProseMirror composer (as of 2025)
    TEXTAREA_SELECTOR = 'div.ProseMirror#prompt-textarea[contenteditable="true"]'

    box = page.locator(TEXTAREA_SELECTOR)
    box.wait_for(state="visible", timeout=60_000)
    box.click(force=True)
    page.wait_for_timeout(100)          # Let React register focus

    # Clear any existing draft
    box.press("Control+A")
    box.press("Backspace")

    # Inject text via JS – handles newlines and special characters correctly
    page.evaluate(
        """(text) => {
            const el = document.querySelector(
                'div.ProseMirror#prompt-textarea'
            );
            if (!el) return;
            el.focus();
            el.innerText = text;
            el.dispatchEvent(new Event('input', { bubbles: true }));
        }""",
        msg,
    )

    page.wait_for_timeout(100)          # Let React process the input event
    box.press("Enter")


# ── Private: response polling ─────────────────────────────────────────────────

def _wait_for_response(page, prev_count: int, timeout: int = 180) -> str:
    """
    Poll the assistant message list until a new stable response appears.

    Stability criterion: STABLE_ROUNDS consecutive polls return identical
    non-empty text AND any open <ACTION> tag has a matching </ACTION> close.

    Args:
        page:       Playwright Page object.
        prev_count: Number of assistant messages before the current prompt.
        timeout:    Max seconds to wait.

    Returns:
        The complete assistant response text, or "" on timeout.
    """
    POLL_MS      = 250   # milliseconds between polls
    STABLE_ROUNDS = 4    # how many identical snapshots = "done streaming"

    ASSISTANT_SELECTOR = 'div[data-message-author-role="assistant"]'
    items = page.locator(ASSISTANT_SELECTOR)

    start = time.time()

    # ── Phase 1: Wait for a new assistant message to appear ───────────────
    while items.count() <= prev_count:
        if time.time() - start > timeout:
            print("⚠️  Timeout: no new assistant message detected.")
            return ""
        page.wait_for_timeout(POLL_MS)

    # ── Phase 2: Wait for streaming to finish ─────────────────────────────
    last_snapshot = ""
    stable = 0

    while True:
        count = items.count()
        parts = [
            items.nth(i).inner_text().strip()
            for i in range(prev_count, count)
        ]
        text = "\n\n".join(p for p in parts if p)

        if "<ACTION>" in text and "</ACTION>" not in text:
            # Model is mid-stream on an ACTION block – reset stability counter
            stable = 0
        elif text == last_snapshot and text:
            stable += 1
        else:
            stable = 0

        last_snapshot = text

        if stable >= STABLE_ROUNDS:
            break

        if time.time() - start > timeout:
            print("⚠️  Timeout: response did not stabilise within limit.")
            break

        page.wait_for_timeout(POLL_MS)

    # Printing is the caller's responsibility (cli.py / api_server.py).
    # The worker is a background thread — it must not write to stdout here,
    # otherwise every response would appear twice in CLI mode.
    return text


# ── Worker thread entry-point ──────────────────────────────────────────────────

def _playwright_worker() -> None:
    """
    Main body of the Playwright worker thread.

    Lifecycle:
        1. Start Playwright + launch persistent Chrome context
        2. Navigate to ChatGPT, wait for Cloudflare / login
        3. Inject SYSTEM_CONTEXT once
        4. Loop: read _request_queue → send to ChatGPT → handle ACTION →
                 write result to _response_queue

    All imports are done inside this function so they only happen on the
    worker thread, which is required for Playwright's sync API to work
    correctly (Playwright sync API is NOT thread-safe across threads).
    """
    global _browser_ready, _system_context_sent, _worker_error

    # Lazy imports (must run in the worker thread)
    try:
        from agent.config.settings import cfg
        from agent.protocol.system_prompt import get_browser_system_prompt
        from agent.protocol.action_parser import try_extract_action
        from agent.tools.file_tools import execute_actions
        from playwright.sync_api import sync_playwright
    except Exception as exc:
        _worker_error = f"Import error in worker thread: {exc}"
        return

    playwright = None
    context    = None

    try:
        prov       = cfg.provider("openai_ui")
        profile_dir = prov.get(
            "profile_dir",
            r"C:\Users\medte\AppData\Local\PlaywrightProfile",
        )
        exe_path   = prov.get(
            "executable_path",
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        )
        chatgpt_url = prov.get("chatgpt_url", "https://chat.openai.com")

        print("🚀 Starting Playwright browser (worker thread)…")
        playwright = sync_playwright().start()

        context = playwright.chromium.launch_persistent_context(
            user_data_dir=profile_dir,
            executable_path=exe_path,
            headless=cfg.headless,   # Controlled by config.json
            slow_mo=100,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--start-maximized",
                "--no-first-run",
                "--no-default-browser-check",
            ],
        )

        page = context.new_page()

        # Hide the webdriver flag to reduce bot-detection risk
        page.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', { get: () => undefined });"
        )

        page.goto(chatgpt_url, timeout=60_000)

        # Allow time for Cloudflare challenge / manual login if needed
        print("⏳ Waiting for Cloudflare / login (20 s)…")
        page.wait_for_timeout(20_000)

        # Wait for the composer to be ready
        page.wait_for_selector(
            'div.ProseMirror#prompt-textarea[contenteditable="true"]',
            timeout=60_000,
        )

        # ── Inject system context once per session ────────────────────────
        # Pick the prompt that matches the current run mode so the persona
        # text ("CLI tool" vs "API server tool") is always accurate.
        system_ctx = get_browser_system_prompt(cfg.mode)
        prev = page.locator('div[data-message-author-role="assistant"]').count()
        print(f"📨 Sending SYSTEM_CONTEXT [{cfg.mode} mode]…")
        _ui_send_message(page, system_ctx)

        # ChatGPT may or may not reply to the system context – either is fine
        try:
            _wait_for_response(page, prev, timeout=60)
        except Exception:
            pass

        _system_context_sent = True
        _browser_ready       = True
        print("✅ Browser ready. SYSTEM_CONTEXT injected. Waiting for requests…")

        # ── Main request loop ─────────────────────────────────────────────
        while True:
            # Blocking wait for the next API / CLI request
            req_id, payload = _request_queue.get()
            msg     = payload["text"]
            timeout = int(payload.get("timeout", 180))

            try:
                prev_count = page.locator(
                    'div[data-message-author-role="assistant"]'
                ).count()

                _ui_send_message(page, msg)
                response = _wait_for_response(page, prev_count, timeout=timeout)

                # ── ACTION handling ───────────────────────────────────────
                action      = try_extract_action(response)
                tool_result = None

                if action:
                    tool_result = execute_actions(action)

                    # Send the tool output back to the model
                    prev2 = page.locator(
                        'div[data-message-author-role="assistant"]'
                    ).count()
                    _ui_send_message(page, f"TOOL_RESULT:\n{tool_result}")

                    # Wait for acknowledgement (soft timeout – don't fail request)
                    try:
                        _wait_for_response(page, prev2, timeout=timeout)
                    except Exception:
                        pass

                _response_queue.put({
                    "ok":          True,
                    "id":          req_id,
                    "response":    response,
                    "tool_result": tool_result,
                })

            except Exception as exc:
                _response_queue.put({
                    "ok":    False,
                    "id":    req_id,
                    "error": str(exc),
                })

    except Exception as exc:
        _worker_error  = f"Worker crashed: {exc}"
        _browser_ready = False
        print(f"💥 {_worker_error}")

    finally:
        # Best-effort cleanup – keep going even if one close() fails
        for obj, method in [(context, "close"), (playwright, "stop")]:
            if obj is not None:
                try:
                    getattr(obj, method)()
                except Exception:
                    pass
