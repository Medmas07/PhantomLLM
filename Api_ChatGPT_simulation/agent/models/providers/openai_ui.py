"""
openai_ui.py – Provider: ChatGPT via Playwright browser automation.

This provider delegates all browser interaction to agent/worker.py.
It never calls Playwright directly — that would break the single-thread rule.

Contract:
    generate(messages, model, **kwargs) -> str

The worker handles the full agentic loop internally:
    user message → ChatGPT response → ACTION detection → tool execution
    → TOOL_RESULT → final response

Because ChatGPT maintains conversation history in the browser session,
only the LAST user message is forwarded.  Previous turns are already
visible to the model in the browser.
"""

from agent import worker as _worker


def generate(messages: list[dict], model: str = "gpt-4", **kwargs) -> str:
    """
    Forward the last user message to the ChatGPT browser session.

    Args:
        messages: OpenAI-style message list [{"role": ..., "content": ...}].
                  Only the last user-role message is sent (browser keeps context).
        model:    Ignored – the model is whatever is active in the browser tab.
        **kwargs:
            timeout (int): Max seconds to wait for a response. Default 180.

    Returns:
        The assistant's final text response (after any tool calls are resolved).

    Raises:
        RuntimeError: If the browser worker has crashed or is not ready.
        TimeoutError: If no response arrives within the timeout window.
        ValueError:   If messages contains no user-role message.
    """
    # Extract the last user message from the conversation
    user_turns = [m for m in messages if m.get("role") == "user"]
    if not user_turns:
        raise ValueError(
            "openai_ui provider requires at least one user-role message."
        )

    text: str = user_turns[-1].get("content", "")
    timeout: int = int(kwargs.get("timeout", 180))

    # Delegate to the worker thread (blocking until response)
    return _worker.send(text, timeout=timeout)
