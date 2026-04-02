"""
router.py – Model dispatcher (browser-only edition).

ALL models are accessed via Playwright browser automation.
No API keys or network SDK calls are made by this router.

Mapping convention
──────────────────
Each entry maps a user-facing model name or alias → provider module name.
The module name must match a file in agent/models/providers/.
That module must expose a generate(messages, model, **kwargs) -> str function.

Provider modules in turn call worker.send(text, model=<key>, ...) where
<key> maps to a BaseUIProvider subclass inside the worker's provider registry.
"""

from importlib import import_module
from typing import Callable

from agent.config.settings import cfg


# ── Provider map ──────────────────────────────────────────────────────────────
# Format:  "<user-facing name>" → "<module name under agent/models/providers/>"

PROVIDER_MAP: dict[str, str] = {

    # ── ChatGPT (chat.openai.com) ─────────────────────────────────────────
    "openai_ui":      "openai_ui",
    "chatgpt":        "openai_ui",
    "gpt-4":          "openai_ui",
    "gpt-4o":         "openai_ui",
    "gpt-3.5-turbo":  "openai_ui",

    # ── Claude (claude.ai) ────────────────────────────────────────────────
    "claude":             "claude_ui",
    "claude_ui":          "claude_ui",
    "claude-opus-4-6":    "claude_ui",
    "claude-sonnet-4-6":  "claude_ui",
    "claude-haiku-4-5":   "claude_ui",
    "claude-3-5-sonnet":  "claude_ui",
    "claude-3-opus":      "claude_ui",

    # ── Gemini (gemini.google.com) ────────────────────────────────────────
    "gemini":           "gemini_ui",
    "gemini_ui":        "gemini_ui",
    "gemini-pro":       "gemini_ui",
    "gemini-1.5-pro":   "gemini_ui",
    "gemini-1.5-flash": "gemini_ui",
    "gemini-2.0-flash": "gemini_ui",

    # ── DeepSeek (chat.deepseek.com) ──────────────────────────────────────
    "deepseek":         "deepseek_ui",
    "deepseek_ui":      "deepseek_ui",
    "deepseek-chat":    "deepseek_ui",
    "deepseek-coder":   "deepseek_ui",

    # ── Grok / xAI (grok.com) ─────────────────────────────────────────────
    # NOTE: "grok" = xAI chatbot.  "groq" (old inference platform) is disabled.
    "grok":     "grok_ui",
    "grok_ui":  "grok_ui",
    "xai":      "grok_ui",

    # ── Qwen (chat.qwen.ai) ───────────────────────────────────────────────
    "qwen":       "qwen_ui",
    "qwen_ui":    "qwen_ui",
    "qwen-max":   "qwen_ui",
    "qwen-plus":  "qwen_ui",
    "qwen-turbo": "qwen_ui",

    # ── Perplexity (perplexity.ai) ────────────────────────────────────────
    "perplexity":    "perplexity_ui",
    "perplexity_ui": "perplexity_ui",

    # ── Mock (testing / CI — no browser needed) ───────────────────────────
    "mock": "mock",
}


# ── Lazy provider loader ──────────────────────────────────────────────────────

def _load_provider(module_name: str) -> Callable:
    """
    Import agent.models.providers.<module_name> and return its generate().

    Raises ValueError if the module does not exist.
    Raises AttributeError if the module does not expose generate().
    """
    full_path = f"agent.models.providers.{module_name}"
    try:
        mod = import_module(full_path)
    except ModuleNotFoundError:
        raise ValueError(
            f"No provider module found: {module_name!r}. "
            f"Expected: agent/models/providers/{module_name}.py"
        )
    if not hasattr(mod, "generate"):
        raise AttributeError(
            f"Provider module {full_path!r} must expose a generate() function."
        )
    return mod.generate


# ── Public dispatch function ──────────────────────────────────────────────────

def generate(model: str, messages: list[dict], **kwargs) -> str:
    """
    Dispatch a generation request to the correct browser UI provider.

    Args:
        model:    Model name or alias (e.g. "claude", "gpt-4", "gemini").
                  Unknown models fall back to cfg.default_model, then "openai_ui".
        messages: OpenAI-style message list [{"role": "user", "content": "..."}].
        **kwargs: Forwarded to the provider (timeout, temperature, …).

    Returns:
        The assistant's text response as a plain string.
    """
    provider_name: str | None = PROVIDER_MAP.get(model)

    if provider_name is None:
        fallback = cfg.default_model
        provider_name = PROVIDER_MAP.get(fallback, "openai_ui")
        print(
            f"⚠️  Unknown model {model!r} – "
            f"falling back to {fallback!r} → {provider_name}"
        )

    fn = _load_provider(provider_name)
    return fn(messages=messages, model=model, **kwargs)