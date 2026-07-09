"""Provider selection: configuration decides, code never does."""

from backend.app.adapters.llm.base import LLMProvider
from backend.app.adapters.llm.gemini import GeminiProvider
from backend.app.adapters.llm.mistral import MistralProvider
from backend.app.config import Settings


def build_llm(settings: Settings) -> LLMProvider:
    """Return the LLMProvider matching settings.llm_provider.

    Failing loudly on an unknown value beats silently falling back to a
    default: a typo in .env should be caught at startup, not at the first
    model call in the middle of a capture.
    """
    # LLM_MODEL overrides the provider's default chat model when set:
    # the A/B lever of the tuning pass lives in .env, not in code.
    extra = {"default_model": settings.llm_model} if settings.llm_model else {}
    if settings.llm_provider == "mistral":
        return MistralProvider(api_key=settings.mistral_api_key, **extra)
    if settings.llm_provider == "gemini":
        return GeminiProvider(api_key=settings.gemini_api_key, **extra)
    raise ValueError(
        f"Unknown LLM_PROVIDER {settings.llm_provider!r}: expected 'mistral' or 'gemini'."
    )
