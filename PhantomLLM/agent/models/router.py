"""
router.py - Model dispatcher with fallback support.

ALL models are accessed via browser automation providers.
"""

from importlib import import_module
from typing import Callable

from agent.config.settings import cfg


# Format: "<user-facing name>" -> "<module name under agent/models/providers/>"
PROVIDER_MAP: dict[str, str] = {
    # ChatGPT
    "openai_ui": "openai_ui",
    "chatgpt": "openai_ui",
    "gpt-4": "openai_ui",
    "gpt-4o": "openai_ui",
    "gpt-3.5-turbo": "openai_ui",

    # Claude
    "claude": "claude_ui",
    "claude_ui": "claude_ui",
    "claude-opus-4-6": "claude_ui",
    "claude-sonnet-4-6": "claude_ui",
    "claude-haiku-4-5": "claude_ui",
    "claude-3-5-sonnet": "claude_ui",
    "claude-3-opus": "claude_ui",

    # Gemini
    "gemini": "gemini_ui",
    "gemini_ui": "gemini_ui",
    "gemini-pro": "gemini_ui",
    "gemini-1.5-pro": "gemini_ui",
    "gemini-1.5-flash": "gemini_ui",
    "gemini-2.0-flash": "gemini_ui",

    # Meta AI
    "meta": "meta_ui",
    "meta_ai": "meta_ui",
    "meta_ui": "meta_ui",
    "meta-ai": "meta_ui",

    # DeepSeek
    "deepseek": "deepseek_ui",
    "deepseek_ui": "deepseek_ui",
    "deepseek-chat": "deepseek_ui",
    "deepseek-coder": "deepseek_ui",

    # Grok / xAI
    "grok": "grok_ui",
    "grok_ui": "grok_ui",
    "xai": "grok_ui",

    # Qwen
    "qwen": "qwen_ui",
    "qwen_ui": "qwen_ui",
    "qwen-max": "qwen_ui",
    "qwen-plus": "qwen_ui",
    "qwen-turbo": "qwen_ui",

    # Perplexity
    "perplexity": "perplexity_ui",
    "perplexity_ui": "perplexity_ui",

    # Mock (testing)
    "mock": "mock",
}


def _load_provider(module_name: str) -> Callable:
    """Import provider module and return its generate() function."""
    full_path = f"agent.models.providers.{module_name}"
    try:
        mod = import_module(full_path)
    except ModuleNotFoundError as exc:
        raise ValueError(
            f"No provider module found: {module_name!r}. "
            f"Expected: agent/models/providers/{module_name}.py"
        ) from exc

    if not hasattr(mod, "generate"):
        raise AttributeError(
            f"Provider module {full_path!r} must expose a generate() function."
        )
    return mod.generate


def _unique_keep_order(items: list[str]) -> list[str]:
    """Return unique non-empty strings while preserving input order."""
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        key = str(item).strip()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(key)
    return out


def _build_fallback_chain(requested_model: str) -> list[str]:
    """
    Build ordered attempts:
    requested -> cfg.default_model -> cfg.fallback_models -> openai_ui.
    """
    chain = [requested_model, cfg.default_model]
    if getattr(cfg, "fallback_enabled", True):
        chain.extend(getattr(cfg, "fallback_models", []))
    chain.append("openai_ui")
    return _unique_keep_order(chain)


def generate(model: str, messages: list[dict], **kwargs) -> str:
    """
    Dispatch a generation request to the correct provider with fallback.

    ValueError from provider calls is considered an input error and is re-raised.
    Runtime/provider failures attempt the next fallback model.
    """
    attempt_models = _build_fallback_chain(model)
    attempt_errors: list[str] = []
    unknown_requested = model not in PROVIDER_MAP

    for idx, attempt_model in enumerate(attempt_models, start=1):
        provider_name = PROVIDER_MAP.get(attempt_model)
        if provider_name is None:
            attempt_errors.append(
                f"[{idx}] model={attempt_model!r}: not mapped in PROVIDER_MAP"
            )
            continue

        if idx == 1 and unknown_requested:
            print(
                f"WARNING: Unknown model {model!r}; "
                f"fallback chain starts with {attempt_model!r} -> {provider_name}"
            )
        elif idx > 1:
            print(f"Fallback attempt [{idx}] {attempt_model!r} -> {provider_name}")

        try:
            fn = _load_provider(provider_name)
            return fn(messages=messages, model=attempt_model, **kwargs)
        except ValueError:
            raise
        except Exception as exc:
            attempt_errors.append(
                f"[{idx}] model={attempt_model!r}, provider={provider_name!r}: {exc}"
            )
            continue

    details = "\n".join(attempt_errors) if attempt_errors else "No attempt was made."
    raise RuntimeError(
        "All model/provider attempts failed.\n"
        f"Requested model: {model!r}\n"
        f"Attempt chain: {attempt_models}\n"
        f"Details:\n{details}"
    )
