import sys
import types
import pytest

from src.services import llm_client


class DummyModule(types.ModuleType):
    pass


def test_available_providers_with_mocked_modules(monkeypatch):
    # Simulate that openai and anthropic are installed, google not
    monkeypatch.setitem(sys.modules, "openai", DummyModule("openai"))
    monkeypatch.setitem(sys.modules, "anthropic", DummyModule("anthropic"))
    # Ensure google.* is not present
    sys.modules.pop("google.genai", None)
    sys.modules.pop("google.generativeai", None)

    providers = llm_client.available_providers()
    assert "openai" in providers
    assert "anthropic" in providers
    assert "google" not in providers


def test_create_adapter_openai_raises_when_missing_package(monkeypatch):
    # Ensure openai not available
    monkeypatch.setitem(sys.modules, "openai", None)
    with pytest.raises(Exception):
        llm_client.create_adapter("openai", "key", "gpt-4o")


def test_list_models_anthropic_when_missing_returns_error(monkeypatch):
    # Remove anthropic module to trigger error path
    monkeypatch.setitem(sys.modules, "anthropic", None)
    models, err = llm_client.list_models("anthropic", "key")
    assert models == []
    assert "anthropic" in (err or "").lower()
