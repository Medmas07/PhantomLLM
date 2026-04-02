# gemini_api.py – REFACTORED
#
# The Google Generative AI SDK integration has been replaced by browser automation.
# Kept as a backward-compatibility shim; forwards to gemini_ui.py.

from agent.models.providers.gemini_ui import generate, GeminiUIBrowser

__all__ = ["generate", "GeminiUIBrowser"]