"""Settings: environment-driven, with safe local defaults."""

from backend.app.config import get_settings

ALL_VARS = ("LLM_PROVIDER", "MISTRAL_API_KEY", "GEMINI_API_KEY", "DATABASE_URL", "CHROMA_DIR")


def test_defaults_apply_when_env_is_empty(monkeypatch):
    """With no environment at all, Scranton still boots on Mistral and local paths."""
    for var in ALL_VARS:
        monkeypatch.delenv(var, raising=False)
    settings = get_settings()
    assert settings.llm_provider == "mistral"
    assert settings.database_url.startswith("sqlite:///")
    assert settings.database_url.endswith("scranton.db")
    assert settings.chroma_dir.endswith("chroma")


def test_environment_overrides_defaults(monkeypatch):
    """Configuration over code: the environment always wins over defaults."""
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///elsewhere.db")
    settings = get_settings()
    assert settings.llm_provider == "gemini"
    assert settings.database_url == "sqlite:///elsewhere.db"
