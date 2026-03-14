# api_server.py
import time
import threading
from queue import Queue
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from playwright.sync_api import sync_playwright


# ===============================
# Queues (API ⇄ Playwright thread)
# ===============================
request_queue: "Queue[tuple[str, dict]]" = Queue()
response_queue: "Queue[dict]" = Queue()

# ===============================
# State flags
# ===============================
browser_ready = False
system_context_sent = False
worker_error: str | None = None

# One-at-a-time lock at API level (optional but safer)
api_lock = threading.Lock()


# ===============================
# Models
# ===============================
class MessageIn(BaseModel):
    text: str
    timeout: int | None = 180  # seconds (API wait timeout)


# ===============================
# Helpers: Playwright UI send
# ===============================
def ui_send_message(page, msg: str):
    """Send a message into ChatGPT composer and press Enter."""
    box = page.locator('div.ProseMirror#prompt-textarea[contenteditable="true"]')
    box.wait_for(state="visible", timeout=60000)

    box.click(force=True)
    time.sleep(0.1)

    # Clear
    box.press("Control+A")
    box.press("Backspace")

    # Insert (multiline safe)
    page.evaluate(
        """(text) => {
            const el = document.querySelector('div.ProseMirror#prompt-textarea');
            if (!el) return;
            el.focus();
            el.innerText = text;
            el.dispatchEvent(new Event('input', { bubbles: true }));
        }""",
        msg,
    )

    time.sleep(0.1)
    box.press("Enter")


# ===============================
# Worker thread (ONLY place where Playwright is used)
# ===============================
def playwright_worker():
    global browser_ready, system_context_sent, worker_error

    # Import your project modules INSIDE the worker thread
    try:
        from config import PROFILE_DIR
        from protocol import SYSTEM_CONTEXT, try_extract_action
        from playwright_io import wait_for_response_bundle
        from tools import execute_actions
    except Exception as e:
        worker_error = f"Import error in worker: {e}"
        return

    playwright = None
    context = None
    page = None

    try:
        print("🚀 Starting Playwright browser (worker thread)...")
        playwright = sync_playwright().start()

        context = playwright.chromium.launch_persistent_context(
            user_data_dir=PROFILE_DIR,
            executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            headless=False,
            slow_mo=100,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--start-maximized",
                "--no-first-run",
                "--no-default-browser-check",
            ],
        )

        page = context.new_page()
        page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        """)

        page.goto("https://chat.openai.com", timeout=60000)

        print("⏳ Waiting for Cloudflare / login...")
        time.sleep(20)

        page.wait_for_selector(
            'div.ProseMirror#prompt-textarea[contenteditable="true"]',
            timeout=60000,
        )

        # Inject system context once
        prev = page.locator('div[data-message-author-role="assistant"]').count()
        print("📨 Sending SYSTEM_CONTEXT...")
        ui_send_message(page, SYSTEM_CONTEXT)

        # Often no response -> ok
        try:
            wait_for_response_bundle(page, prev)
        except Exception:
            # don't fail startup if no response
            pass

        system_context_sent = True
        browser_ready = True
        print("✅ Browser ready & SYSTEM_CONTEXT injected")

        # Main loop: handle API requests
        while True:
            # request tuple: (request_id, payload)
            request_id, payload = request_queue.get()
            msg = payload["text"]
            timeout = payload.get("timeout", 180)

            try:
                prev_count = page.locator(
                    'div[data-message-author-role="assistant"]'
                ).count()

                ui_send_message(page, msg)

                response = wait_for_response_bundle(page, prev_count, timeout=timeout)

                action = try_extract_action(response)
                tool_result = None

                if action:
                    tool_result = execute_actions(action)

                    # Inform the model (optional but recommended)
                    prev2 = page.locator(
                        'div[data-message-author-role="assistant"]'
                    ).count()

                    ui_send_message(page, f"TOOL_RESULT:\n{tool_result}")
                    try:
                        wait_for_response_bundle(page, prev2, timeout=timeout)
                    except Exception:
                        pass

                response_queue.put({
                    "ok": True,
                    "id": request_id,
                    "response": response,
                    "tool_result": tool_result,
                })

            except Exception as e:
                response_queue.put({
                    "ok": False,
                    "id": request_id,
                    "error": str(e),
                })

    except Exception as e:
        worker_error = f"Worker crashed: {e}"
        browser_ready = False
        system_context_sent = False
        print("💥 Worker crashed:", worker_error)

    finally:
        # best-effort cleanup
        try:
            if context:
                context.close()
        except Exception:
            pass
        try:
            if playwright:
                playwright.stop()
        except Exception:
            pass


# ===============================
# Lifespan
# ===============================
@asynccontextmanager
async def lifespan(app: FastAPI):
    t = threading.Thread(target=playwright_worker, daemon=True)
    t.start()

    # wait until ready or error
    start = time.time()
    while not browser_ready and worker_error is None:
        time.sleep(0.2)
        if time.time() - start > 120:
            break

    yield
    # (optional) implement graceful stop later


# ===============================
# FastAPI app
# ===============================
app = FastAPI(lifespan=lifespan)


# ===============================
# Endpoints
# ===============================
@app.get("/status")
def status():
    return {
        "browser_ready": browser_ready,
        "system_context_sent": system_context_sent,
        "worker_error": worker_error,
    }


@app.post("/message")
def message(payload: MessageIn):
    if worker_error:
        raise HTTPException(500, worker_error)
    if not browser_ready:
        raise HTTPException(503, "Browser not ready")

    # serialize requests to avoid interleaving in one UI
    with api_lock:
        request_id = f"req-{int(time.time()*1000)}"
        request_queue.put((request_id, {"text": payload.text, "timeout": payload.timeout}))

        # wait for matching response
        deadline = time.time() + (payload.timeout or 180)
        while True:
            if time.time() > deadline:
                raise HTTPException(504, "Timeout waiting for model response")

            result = response_queue.get()
            if result.get("id") == request_id:
                if result.get("ok"):
                    return {
                        "response": result.get("response", ""),
                        "tool_result": result.get("tool_result"),
                    }
                raise HTTPException(500, result.get("error", "Unknown error"))
            else:
                # unexpected (rare). put back for the correct waiter
                response_queue.put(result)
                time.sleep(0.01)
