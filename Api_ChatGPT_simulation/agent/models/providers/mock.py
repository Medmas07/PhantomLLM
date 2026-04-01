"""
mock.py – Provider: No-op mock (for testing and CI/CD).

Returns a deterministic echo response without making any network calls.
No API keys or external dependencies required.

Use cases:
    - Unit testing the pipeline (routing, protocol, tools) in isolation
    - CI environments where real credentials are unavailable
    - Debugging request/response formatting issues
    - Demonstrating the system without incurring API costs
"""


def generate(messages: list[dict], model: str = "mock", **kwargs) -> str:
    """
    Return a synthetic echo response based on the last user message.

    Args:
        messages: OpenAI-style message list.
        model:    Ignored.
        **kwargs: Ignored.

    Returns:
        A plain string echoing the last user message.
    """
    user_turns = [m for m in messages if m.get("role") == "user"]

    if not user_turns:
        return "[MOCK] No user message received."

    last_content = user_turns[-1].get("content", "")
    return f"[MOCK] You said: {last_content!r}"