# agent/utils/__init__.py
# Utility stubs for future browser extension support.


def detect_active_textarea():
    """
    [FUTURE INTERFACE] Detect the active textarea in the current browser context.

    This function is an intentional stub, reserved for a future browser-extension
    layer that will allow this agent to work with any LLM chat interface — not just
    the ChatGPT web UI.

    When implemented it should:
      1. Detect which browser tab / frame is active.
      2. Identify the chat input element (textarea, contenteditable div, etc.)
      3. Return an abstraction that worker.py can type into.

    Currently: worker.py uses a hardcoded CSS selector for ChatGPT's composer.
    Future:    worker.py calls detect_active_textarea() instead.
    """
    raise NotImplementedError(
        "detect_active_textarea() is reserved for future browser extension support. "
        "worker.py currently uses a hardcoded selector for ChatGPT."
    )