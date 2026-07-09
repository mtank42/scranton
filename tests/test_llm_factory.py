"""Provider selection: configuration decides, unknown values fail loudly."""

import pytest

from backend.app.adapters.llm.factory import build_llm
from backend.app.adapters.llm.gemini import GeminiProvider
from backend.app.adapters.llm.mistral import MistralProvider
from backend.app.config import Settings


def make_settings(provider: str, llm_model: str = "") -> Settings:
    """Minimal settings object for factory tests."""
    return Settings(
        llm_provider=provider,
        mistral_api_key="test-key",
        gemini_api_key="test-key",
        database_url="sqlite:///:memory:",
        chroma_dir="unused",
        google_client_secrets="unused",
        google_token_file="unused",
        gdrive_folder_id="",
        llm_model=llm_model,
    )


def test_mistral_is_selected_from_config():
    """LLM_PROVIDER=mistral yields the Mistral implementation."""
    assert isinstance(build_llm(make_settings("mistral")), MistralProvider)


def test_gemini_is_selected_from_config():
    """LLM_PROVIDER=gemini yields the Gemini fallback implementation."""
    assert isinstance(build_llm(make_settings("gemini")), GeminiProvider)


def test_model_override_reaches_the_provider():
    """LLM_MODEL swaps the chat model from .env: the tuning A/B lever."""
    provider = build_llm(make_settings("mistral", llm_model="mistral-medium-latest"))
    assert provider.default_model == "mistral-medium-latest"
    # Empty override keeps the provider's own default.
    assert build_llm(make_settings("mistral")).default_model == "mistral-small-latest"


def test_unknown_provider_fails_loudly():
    """A typo in .env must be caught at startup, not at the first model call."""
    with pytest.raises(ValueError, match="Unknown LLM_PROVIDER"):
        build_llm(make_settings("chatgpt"))


def test_gemini_fallback_stays_an_explicit_stub():
    """The unimplemented fallback must fail loudly, never silently."""
    provider = build_llm(make_settings("gemini"))
    with pytest.raises(NotImplementedError):
        provider.complete([{"role": "user", "content": "hello"}])


def test_mistral_client_is_lazy():
    """Building the provider must not require a valid key or the network."""
    provider = build_llm(make_settings("mistral"))
    assert provider._client is None
