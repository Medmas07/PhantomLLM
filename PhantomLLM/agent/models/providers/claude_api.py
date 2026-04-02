# claude_api.py – REFACTORED
#
# The Anthropic API integration has been replaced by browser automation.
# This file is kept as a backward-compatibility shim so any code that still
# does `from agent.models.providers.claude_api import generate` continues to work.
#
# All calls are transparently forwarded to claude_ui.py (Playwright driver).

from agent.models.providers.claude_ui import generate, ClaudeUIBrowser

__all__ = ["generate", "ClaudeUIBrowser"]