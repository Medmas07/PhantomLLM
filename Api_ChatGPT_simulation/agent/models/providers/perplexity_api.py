# perplexity_api.py – REFACTORED
#
# The Perplexity REST API integration has been replaced by browser automation.
# Kept as a backward-compatibility shim; forwards to perplexity_ui.py.

from agent.models.providers.perplexity_ui import generate, PerplexityUIBrowser

__all__ = ["generate", "PerplexityUIBrowser"]