# deepseek_api.py – REFACTORED
#
# The DeepSeek REST API integration has been replaced by browser automation.
# Kept as a backward-compatibility shim; forwards to deepseek_ui.py.

from agent.models.providers.deepseek_ui import generate, DeepSeekUIBrowser

__all__ = ["generate", "DeepSeekUIBrowser"]