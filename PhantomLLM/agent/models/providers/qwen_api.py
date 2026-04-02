# qwen_api.py – REFACTORED
#
# The Alibaba DashScope API integration has been replaced by browser automation.
# Kept as a backward-compatibility shim; forwards to qwen_ui.py.

from agent.models.providers.qwen_ui import generate, QwenUIBrowser

__all__ = ["generate", "QwenUIBrowser"]