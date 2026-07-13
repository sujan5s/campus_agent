"""Provider-agnostic LLM factory (docs/03-TECH-STACK.md).

HARD RULE: every agent gets its LLM from get_llm(). No module in this codebase
may import a provider SDK (google-genai, anthropic, openai, ...) directly.
Switching providers is only ever an .env change:

    LLM_PROVIDER=google_genai  LLM_MODEL=gemini-2.5-flash   GOOGLE_API_KEY=...
    LLM_PROVIDER=anthropic     LLM_MODEL=claude-sonnet-5    ANTHROPIC_API_KEY=...
    LLM_PROVIDER=openai        LLM_MODEL=gpt-4o-mini        OPENAI_API_KEY=...
    LLM_PROVIDER=ollama        LLM_MODEL=llama3.1           (no key, local)
"""
import os
from functools import lru_cache

from app.core.config import settings

# Env var each provider needs; None means no key required.
_PROVIDER_KEY_ENV = {
    "google_genai": "GOOGLE_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "ollama": None,
}


def _provider_api_key() -> str | None:
    """Resolve the API key for the configured provider from settings/env."""
    if settings.LLM_PROVIDER == "google_genai":
        # Accept the legacy GEMINI_API_KEY alias.
        return settings.GOOGLE_API_KEY or settings.GEMINI_API_KEY or None
    env_name = _PROVIDER_KEY_ENV.get(settings.LLM_PROVIDER)
    if env_name is None:
        return None
    return getattr(settings, env_name, "") or os.environ.get(env_name) or None


def is_llm_configured() -> bool:
    """True when the configured provider is usable (has a key, or needs none).

    Agents use this to fall back to deterministic behaviour instead of crashing,
    so the demo still runs on a machine with no API key at all.
    """
    if settings.LLM_PROVIDER not in _PROVIDER_KEY_ENV:
        return False
    if _PROVIDER_KEY_ENV[settings.LLM_PROVIDER] is None:  # e.g. ollama
        return True
    return _provider_api_key() is not None


@lru_cache(maxsize=4)
def get_llm(temperature: float = 0.1):
    """Return the chat model for the configured provider. Cached per temperature."""
    from langchain.chat_models import init_chat_model

    key = _provider_api_key()
    env_name = _PROVIDER_KEY_ENV.get(settings.LLM_PROVIDER)
    if key and env_name and not os.environ.get(env_name):
        # init_chat_model reads the key from the environment.
        os.environ[env_name] = key

    return init_chat_model(
        model=settings.LLM_MODEL,
        model_provider=settings.LLM_PROVIDER,
        temperature=temperature,
    )
