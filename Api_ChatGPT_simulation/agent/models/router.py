"""
router.py – Model dispatcher.

Maps a model name (or alias) to the correct provider module and
calls its generate() function with a unified signature:

    generate(model: str, messages: list[dict], **kwargs) -> str

Resolution order:
    1. Exact match in PROVIDER_MAP
    2. Fallback to cfg.default_model
    3. Hard fallback to "openai_ui" if default_model is also unknown

Provider modules are imported lazily (only when first called) so that
optional SDK packages (anthropic, google-generativeai, groq, etc.) are not
imported at startup unless actually used.
"""

from importlib import import_module
from typing import Callable

from agent.config.settings import cfg


# ── Provider map ──────────────────────────────────────────────────────────────
# Maps every accepted model name / alias → provider module name.
# Module names must match files in agent/models/providers/.

PROVIDER_MAP: dict[str, str] = {

    # ── Browser automation (ChatGPT via Playwright) ───────────────────────
    "openai_ui":      "openai_ui",
    "chatgpt":        "openai_ui",
    "gpt-4":          "openai_ui",
    "gpt-4o":         "openai_ui",
    "gpt-3.5-turbo":  "openai_ui",

    # ── Anthropic Claude ──────────────────────────────────────────────────
    "claude":             "claude_api",
    "claude-opus-4-6":    "claude_api",
    "claude-sonnet-4-6":  "claude_api",
    "claude-haiku-4-5":   "claude_api",
    "claude-3-5-sonnet":  "claude_api",
    "claude-3-opus":      "claude_api",
    "claude-3-sonnet":    "claude_api",
    "claude-3-haiku":     "claude_api",

    # ── Google Gemini ─────────────────────────────────────────────────────
    "gemini":             "gemini_api",
    "gemini-pro":         "gemini_api",
    "gemini-1.5-pro":     "gemini_api",
    "gemini-1.5-flash":   "gemini_api",
    "gemini-2.0-flash":   "gemini_api",

    # ── DeepSeek ──────────────────────────────────────────────────────────
    "deepseek":           "deepseek_api",
    "deepseek-chat":      "deepseek_api",
    "deepseek-coder":     "deepseek_api",
    "deepseek-reasoner":  "deepseek_api",

    # ── Groq (fast open-source inference) ────────────────────────────────
    "groq":                      "groq_api",
    "llama-3.3-70b-versatile":   "groq_api",
    "llama-3.1-8b-instant":      "groq_api",
    "llama-3.1-70b-versatile":   "groq_api",
    "mixtral-8x7b-32768":        "groq_api",
    "gemma2-9b-it":               "groq_api",

    # ── Alibaba Qwen ──────────────────────────────────────────────────────
    "qwen":        "qwen_api",
    "qwen-max":    "qwen_api",
    "qwen-plus":   "qwen_api",
    "qwen-turbo":  "qwen_api",
    "qwen-long":   "qwen_api",

    # ── Perplexity ────────────────────────────────────────────────────────
    "perplexity":                              "perplexity_api",
    "llama-3.1-sonar-large-128k-online":       "perplexity_api",
    "llama-3.1-sonar-small-128k-online":       "perplexity_api",
    "llama-3.1-sonar-huge-128k-online":        "perplexity_api",

    # ── Mock (testing / CI) ───────────────────────────────────────────────
    "mock":  "mock",
}


# ── Provider loader (lazy) ────────────────────────────────────────────────────

def _load_provider(module_name: str) -> Callable:
    """
    Dynamically import agent.models.providers.<module_name> and return
    its generate() callable.

    Args:
        module_name: Short name matching a file in agent/models/providers/.

    Raises:
        ValueError if the module does not exist.
        AttributeError if the module does not expose generate().
    """
    full_path = f"agent.models.providers.{module_name}"
    try:
        mod = import_module(full_path)
    except ModuleNotFoundError:
        raise ValueError(
            f"No provider module found for: {module_name!r}. "
            f"Expected file: agent/models/providers/{module_name}.py"
        )
    if not hasattr(mod, "generate"):
        raise AttributeError(
            f"Provider module {full_path!r} must expose a generate() function."
        )
    return mod.generate


# ── Public API ────────────────────────────────────────────────────────────────

def generate(model: str, messages: list[dict], **kwargs) -> str:
    """
    Dispatch a generation request to the correct provider.

    Args:
        model:    Model identifier or alias (e.g. "claude", "gpt-4", "groq").
                  Must be a key in PROVIDER_MAP, or will fall back to the
                  default_model from config.json.
        messages: OpenAI-style message list:
                  [{"role": "user", "content": "..."}, ...]
        **kwargs: Forwarded to the provider (timeout, temperature, max_tokens…).

    Returns:
        The assistant's text response as a plain string.

    Raises:
        ValueError   if the resolved provider module is missing.
        RuntimeError propagated from the provider on API/browser errors.
    """
    # ── Resolve provider module name ──────────────────────────────────────
    provider_name: str | None = PROVIDER_MAP.get(model)

    if provider_name is None:
        # Unknown model → try default from config
        fallback = cfg.default_model
        provider_name = PROVIDER_MAP.get(fallback)

        if provider_name is None:
            # Last resort: hardwired safe fallback
            provider_name = "openai_ui"

        print(
            f"⚠️  Unknown model {model!r} – "
            f"falling back to {fallback!r} → {provider_name}"
        )

    # ── Lazy-load and call ────────────────────────────────────────────────
    fn = _load_provider(provider_name)
    return fn(messages=messages, model=model, **kwargs)
