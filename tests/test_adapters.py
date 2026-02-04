import sys
import types
import pytest

from src.services import llm_client


class DummyModule(types.ModuleType):
    pass


def make_dummy_openai(monkeypatch):
    mod = DummyModule("openai")
    # create minimal Model.list and ChatCompletion.create
    mod.Model = types.SimpleNamespace(
        list=lambda: types.SimpleNamespace(data=[{"id": "gpt-4o-mini"}])
    )
    mod.ChatCompletion = types.SimpleNamespace(
        create=lambda **kw: types.SimpleNamespace(
            choices=[types.SimpleNamespace(message=types.SimpleNamespace(content="ok"))]
        )
    )
    monkeypatch.setitem(sys.modules, "openai", mod)


def test_create_openai_adapter(monkeypatch):
    make_dummy_openai(monkeypatch)
    adapter = llm_client.create_adapter("openai", "fake-key", "gpt-4o-mini")
    assert adapter.type == "openai"
    out = adapter.call("hi", "value")
    assert isinstance(out, str)


def test_create_google_adapter_raises_when_missing(monkeypatch):
    # ensure google modules not present
    monkeypatch.setitem(sys.modules, "google.genai", None)
    with pytest.raises(Exception):
        llm_client.create_adapter("google", "key", "gemini-1.5-flash")
        llm_client.create_adapter("google", "key", "gemini-1.5-flash")
