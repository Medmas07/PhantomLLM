"""
worker.py – Multi-tab Playwright browser worker thread.

NON-NEGOTIABLE RULES (unchanged from v1)
─────────────────────────────────────────
1. Playwright runs ONLY in this module, in a single dedicated thread.
2. No Playwright import or call is allowed outside this module.
3. All communication goes through _request_queue / _response_queue.

New in v2: Multi-tab management
────────────────────────────────
One browser context is shared across all providers.
Each provider gets its own tab (Page) opened lazily on first use.

    _tabs = {
        "openai_ui":    <Page: chat.openai.com>,
        "claude_ui":    <Page: claude.ai>,
        "gemini_ui":    <Page: gemini.google.com>,
        ...
    }

The worker routes each request to the correct provider class (BaseUIProvider
subclass) and calls its send_message() / wait_for_response() methods.

send() API change (v2)
──────────────────────
Old: send(text, timeout)
New: send(text, model, timeout)   ← model selects the provider tab
"""

import random
import threading
import time
from pathlib import Path
from queue import Empty, Queue


# ── Module-level state ────────────────────────────────────────────────────────

_request_queue:  "Queue[tuple[str, dict]]" = Queue()
_response_queue: "Queue[dict]"             = Queue()

_browser_ready: bool      = False
_worker_error:  str|None  = None
_worker_thread: threading.Thread|None = None

# These are owned exclusively by the worker thread; no other thread touches them.
_context              = None   # Playwright BrowserContext
_tabs:                dict     = {}   # provider_key → Page
_system_context_sent: dict     = {}   # provider_key → bool
_provider_instances:  dict     = {}   # provider_key → BaseUIProvider instance


# ── Public API ────────────────────────────────────────────────────────────────

def is_ready() -> bool:
    """True once the browser context is open and accepting requests."""
    return _browser_ready


def get_error() -> str | None:
    """The crash message if the worker has died, otherwise None."""
    return _worker_error


def get_status() -> dict:
    """Status snapshot for the /status HTTP endpoint."""
    return {
        "browser_ready":  _browser_ready,
        "worker_error":   _worker_error,
        "open_tabs":      list(_tabs.keys()),
        "system_context": {k: v for k, v in _system_context_sent.items()},
    }


def send(text: str, model: str = "openai_ui", timeout: int = 180) -> str:
    """
    Send a message to the browser worker and block until a response arrives.

    Thread-safe. Multiple API handlers can call this concurrently; the worker
    processes requests serially (one browser tab at a time) and responses are
    matched back to callers by a unique request ID.

    Args:
        text:    User message to send.
        model:   Provider key (e.g. "openai_ui", "claude_ui", "gemini_ui").
        timeout: Max seconds to wait.

    Returns:
        The assistant's final text after any tool calls are resolved.

    Raises:
        RuntimeError: Worker crashed or browser not ready.
        TimeoutError: No response within timeout.
    """
    if _worker_error:
        raise RuntimeError(f"Playwright worker error: {_worker_error}")
    if not _browser_ready:
        raise RuntimeError("Playwright browser is not ready yet.")

    req_id = f"req-{int(time.time() * 1000)}-{random.randint(1000, 9999)}"
    _request_queue.put((req_id, {"text": text, "model": model, "timeout": timeout}))

    deadline = time.time() + timeout

    while time.time() < deadline:
        try:
            result = _response_queue.get(timeout=0.5)
            if result.get("id") == req_id:
                if result.get("ok"):
                    return result.get("response", "")
                raise RuntimeError(result.get("error", "Unknown worker error"))
            else:
                # Belongs to another concurrent caller; put it back
                _response_queue.put(result)
                time.sleep(0.01)
        except Empty:
            pass

    raise TimeoutError(
        f"Playwright worker did not respond within {timeout} seconds "
        f"(model={model!r})."
    )


def preload(model: str, timeout: int = 120) -> None:
    """
    Open the browser tab for `model` and inject the system prompt immediately.

    Called right after start() so the tab is ready before the user types
    their first message. Sends a special "preload" request through the
    normal queue; the worker handles it by doing tab-init + system-context
    injection and then returns without waiting for a chat response.

    Raises RuntimeError if the worker is not running or preload fails.
    Raises TimeoutError if the tab/login takes longer than `timeout` seconds.
    """
    if _worker_error:
        raise RuntimeError(f"Playwright worker error: {_worker_error}")
    if not _browser_ready:
        raise RuntimeError("Playwright browser is not ready yet.")

    req_id = f"preload-{int(time.time() * 1000)}-{random.randint(1000, 9999)}"
    _request_queue.put((req_id, {"type": "preload", "model": model, "timeout": timeout}))

    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            result = _response_queue.get(timeout=0.5)
            if result.get("id") == req_id:
                if result.get("ok"):
                    return
                raise RuntimeError(result.get("error", "Preload failed"))
            else:
                _response_queue.put(result)
                time.sleep(0.01)
        except Empty:
            pass

    raise TimeoutError(
        f"Preload timed out after {timeout}s (model={model!r}). "
        "If login is required, increase the timeout or log in manually."
    )


def start() -> None:
    """
    Launch the Playwright worker thread and block until the browser is ready.

    In v2 "ready" means the browser context is open — individual provider tabs
    are initialised lazily on first use, so startup is instant.

    Idempotent: calling start() when the thread is already alive is a no-op.
    Raises RuntimeError on startup failure (e.g. Chrome not found).
    """
    global _worker_thread

    if _worker_thread and _worker_thread.is_alive():
        return

    _worker_thread = threading.Thread(
        target=_playwright_worker,
        name="playwright-worker",
        daemon=True,
    )
    _worker_thread.start()

    deadline = time.time() + 120
    while time.time() < deadline:
        if _browser_ready:
            return
        if _worker_error:
            raise RuntimeError(f"Worker failed to start: {_worker_error}")
        time.sleep(0.2)

    raise RuntimeError("Timed out waiting for the Playwright browser (120 s).")


# ── Private: provider registry ────────────────────────────────────────────────

def _build_provider_class_map() -> dict:
    """
    Import all UI provider classes and return a key → class mapping.

    Called INSIDE the worker thread (after playwright imports) to avoid
    circular-import issues at module load time.
    """
    from agent.models.providers.openai_ui    import OpenAIUIBrowser
    from agent.models.providers.meta_ui      import MetaUIBrowser
    from agent.models.providers.claude_ui    import ClaudeUIBrowser
    from agent.models.providers.gemini_ui    import GeminiUIBrowser
    from agent.models.providers.deepseek_ui  import DeepSeekUIBrowser
    from agent.models.providers.grok_ui      import GrokUIBrowser
    from agent.models.providers.qwen_ui      import QwenUIBrowser
    from agent.models.providers.perplexity_ui import PerplexityUIBrowser

    return {
        "openai_ui":     OpenAIUIBrowser,
        "meta_ui":       MetaUIBrowser,
        "claude_ui":     ClaudeUIBrowser,
        "gemini_ui":     GeminiUIBrowser,
        "deepseek_ui":   DeepSeekUIBrowser,
        "grok_ui":       GrokUIBrowser,
        "qwen_ui":       QwenUIBrowser,
        "perplexity_ui": PerplexityUIBrowser,
    }


# ── Private: tab helpers ──────────────────────────────────────────────────────

def _get_or_create_tab(context, provider_key: str, provider) -> "Page":
    """
    Return the existing Page for provider_key, or create a new tab.

    A new tab is also created when the existing one has been closed
    (e.g. user accidentally closed it in the browser).
    """
    existing = _tabs.get(provider_key)
    if existing is not None and not existing.is_closed():
        return existing

    # New tab
    page = context.new_page()
    # Hide webdriver fingerprint
    page.add_init_script(
        "Object.defineProperty(navigator, 'webdriver', { get: () => undefined });"
    )
    # Navigate to provider URL
    print(f"🆕 Opening new tab for: {provider_key} → {provider.URL}")
    page.goto(provider.URL, timeout=60_000)

    _tabs[provider_key] = page
    _system_context_sent[provider_key] = False   # fresh tab = needs system context
    return page


# ── Worker thread entry-point ─────────────────────────────────────────────────

def _playwright_worker() -> None:
    """
    Main body of the Playwright worker thread.

    Startup:
        1. Import provider classes (lazy, inside this thread)
        2. Start Playwright + launch persistent Chrome context
        3. Set _browser_ready = True  (tabs open lazily on first request)

    Request loop:
        For each (req_id, payload) from _request_queue:
          a. Resolve provider class from payload["model"]
          b. Get or create the provider's tab
          c. ensure_loaded() — navigates if needed, waits for manual login
          d. Inject SYSTEM_CONTEXT once per provider per session
          e. send_message() + wait_for_response()
          f. Handle ACTION blocks (file tools)
          g. Put result on _response_queue
    """
    global _browser_ready, _worker_error

    # ── Lazy imports (must run in this thread for Playwright sync API) ────
    try:
        from agent.config.settings import cfg
        from agent.protocol.system_prompt import get_browser_system_prompt
        from agent.protocol.action_parser import try_extract_action
        from agent.tools.file_tools import execute_actions
        from agent.models.providers.base_ui import SelectorAmbiguityError
    except Exception as exc:
        _worker_error = f"Import error in worker thread: {exc}"
        return

    # ── Build provider → class map ────────────────────────────────────────
    try:
        provider_class_map = _build_provider_class_map()
    except Exception as exc:
        _worker_error = f"Failed to build provider map: {exc}"
        return

    playwright = None
    context    = None
    camoufox_browser = None
    backend = str(getattr(cfg, "browser_backend", "playwright")).strip().lower()
    if backend not in {"playwright", "camoufox"}:
        backend = "playwright"

    try:
        # ── Start Playwright + Chrome ─────────────────────────────────────
        prov_cfg    = cfg.provider("openai_ui")
        profile_dir = str(
            prov_cfg.get("profile_dir", "") or (cfg.workspace / ".browser-profile")
        )
        Path(profile_dir).mkdir(parents=True, exist_ok=True)

        if backend == "camoufox":
            print("Starting Camoufox browser context (multi-tab mode)...")
            try:
                from camoufox.sync_api import Camoufox
            except Exception as exc:
                raise RuntimeError(
                    "Camoufox backend selected but `camoufox` is not installed. "
                    "Install it with: pip install camoufox && python -m camoufox fetch"
                ) from exc

            camoufox_browser = Camoufox(
                headless=cfg.headless,
                persistent_context=True,
                user_data_dir=profile_dir,
            )
            context = camoufox_browser.__enter__()
        else:
            from playwright.sync_api import sync_playwright

            exe_path = str(prov_cfg.get("executable_path", "")).strip()

            print("Starting Playwright browser context (multi-tab mode)...")
            playwright = sync_playwright().start()

            launch_kwargs = dict(
                user_data_dir=profile_dir,
                headless=cfg.headless,
                slow_mo=100,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--start-maximized",
                    "--no-first-run",
                    "--no-default-browser-check",
                ],
            )
            if exe_path:
                launch_kwargs["executable_path"] = exe_path

            context = playwright.chromium.launch_persistent_context(**launch_kwargs)

        # Browser is ready; tabs open lazily on first request
        _browser_ready = True
        print(
            f"Browser context ready (backend={backend}). "
            "Provider tabs will open on first use."
        )

        # ── Main request loop ─────────────────────────────────────────────
        while True:
            req_id, payload = _request_queue.get()   # blocks
            req_type = payload.get("type", "chat")   # "chat" | "preload"
            model    = payload.get("model", "openai_ui")
            timeout  = int(payload.get("timeout", 180))

            try:
                # ── Resolve provider ──────────────────────────────────────
                if model not in provider_class_map:
                    raise ValueError(
                        f"Unknown provider key: {model!r}. "
                        f"Available: {sorted(provider_class_map)}"
                    )

                # Lazy-instantiate provider (one instance per key)
                if model not in _provider_instances:
                    _provider_instances[model] = provider_class_map[model]()
                provider = _provider_instances[model]

                # ── Get or create tab ─────────────────────────────────────
                page = _get_or_create_tab(context, model, provider)

                # ── Ensure page is loaded + user is logged in ─────────────
                provider.ensure_loaded(page)

                # ── Inject system context once per provider per session ───
                if not _system_context_sent.get(model, False):
                    system_ctx = get_browser_system_prompt(cfg.mode)
                    prev_init  = provider.get_response_count(page)
                    print(
                        f"📨 Injecting SYSTEM_CONTEXT for {model} "
                        f"[{cfg.mode} mode]…"
                    )
                    provider.send_message(page, system_ctx)
                    # Soft wait — model response to system context is optional
                    try:
                        provider.wait_for_response(page, prev_init, timeout=60)
                    except Exception:
                        pass
                    _system_context_sent[model] = True
                    print(f"✅ {model}: SYSTEM_CONTEXT injected.")

                # ── Preload request: tab + system context only, no chat ───
                if req_type == "preload":
                    _response_queue.put({
                        "ok":          True,
                        "id":          req_id,
                        "response":    "",
                        "tool_result": None,
                    })
                    continue

                # ── Send the actual user message ──────────────────────────
                text       = payload["text"]
                prev_count = provider.get_response_count(page)
                provider.send_message(page, text)
                response   = provider.wait_for_response(page, prev_count, timeout)

                # ── ACTION / tool handling ────────────────────────────────
                action         = try_extract_action(response)
                tool_result    = None
                final_response = response   # default: first response

                if action:
                    tool_result = execute_actions(action)

                    # Send tool output back to model and capture its final reply
                    prev2 = provider.get_response_count(page)
                    provider.send_message(page, f"TOOL_RESULT:\n{tool_result}")
                    try:
                        final_response = provider.wait_for_response(
                            page, prev2, timeout=timeout
                        )
                    except Exception:
                        final_response = response   # fallback to first response

                _response_queue.put({
                    "ok":          True,
                    "id":          req_id,
                    "response":    final_response,
                    "tool_result": tool_result,
                })

            except SelectorAmbiguityError as exc:
                # Print the full HTML-inspection guidance to stdout,
                # then return it as an error response to the caller.
                print(str(exc))
                _response_queue.put({
                    "ok":    False,
                    "id":    req_id,
                    "error": str(exc),
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
        if backend != "camoufox" and context is not None:
            try:
                context.close()
            except Exception:
                pass

        if camoufox_browser is not None:
            try:
                camoufox_browser.__exit__(None, None, None)
            except Exception:
                pass

        if playwright is not None:
            try:
                playwright.stop()
            except Exception:
                pass
