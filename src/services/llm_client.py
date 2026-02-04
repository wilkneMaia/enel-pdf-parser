"""LLM client abstraction supporting multiple providers (Google GenAI, OpenAI, Anthropic).

Provides:
- detection of available SDKs
- listing models per provider
- adapters implementing pandasai.llm.LLM interface for use with PandasAI
"""
from typing import List, Tuple, Optional

try:
    from pandasai.llm import LLM
except Exception:  # pragma: no cover - pandasai not available in some test environments
    class LLM:  # type: ignore
        pass


class ProviderUnavailable(Exception):
    pass


class GoogleGenaiAdapter(LLM):
    def __init__(self, api_key: str, model: str = "gemini-1.5-flash"):
        try:
            import google.genai as genai
        except Exception:
            try:
                import google.generativeai as genai  # type: ignore
            except Exception as e:  # pragma: no cover
                raise ProviderUnavailable("google.genai/google.generativeai package not found")
        self.genai = genai
        self.api_key = api_key
        self.model = model
        try:
            self.client = genai.Client(api_key=api_key)
        except Exception:
            self.client = None

    @property
    def type(self) -> str:
        return "google-genai"

    def call(self, instruction, value, suffix="") -> str:
        safety_prompt = (
            "\n\n[SYSTEM INSTRUCTION]\n"
            "You are an assistant specialized in energy bill analysis (Enel PDF Parser). "
            "Only answer questions related to the provided dataset."
        )
        prompt = f"{instruction}\n{safety_prompt}\n{value}\n{suffix}"

        if self.client is None:
            raise ProviderUnavailable("Google GenAI client not initialized")

        resp = self.client.models.generate_content(model=self.model, contents=prompt)
        # The response shape may vary; try to extract textual content
        try:
            return getattr(resp, "text", str(resp))
        except Exception:
            return str(resp)


class OpenAIAdapter(LLM):
    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        try:
            import openai
        except Exception:
            raise ProviderUnavailable("openai package not found")
        self.openai = openai
        self.api_key = api_key
        self.model = model
        self.openai.api_key = api_key

    @property
    def type(self) -> str:
        return "openai"

    def call(self, instruction, value, suffix="") -> str:
        safety_prompt = (
            "\n\n[SYSTEM INSTRUCTION]\n"
            "You are an assistant specialized in energy bill analysis (Enel PDF Parser). "
            "Only answer questions related to the provided dataset."
        )
        prompt = f"{instruction}\n{safety_prompt}\n{value}\n{suffix}"

        resp = self.openai.ChatCompletion.create(
            model=self.model, messages=[{"role": "user", "content": prompt}]
        )
        return resp.choices[0].message.content


class AnthropicAdapter(LLM):
    def __init__(self, api_key: str, model: str = "claude-2.1"):
        try:
            from anthropic import Anthropic
        except Exception:
            raise ProviderUnavailable("anthropic package not found")
        self.anthropic = Anthropic(api_key=api_key)
        self.api_key = api_key
        self.model = model

    @property
    def type(self) -> str:
        return "anthropic"

    def call(self, instruction, value, suffix="") -> str:
        safety_prompt = (
            "\n\n[SYSTEM INSTRUCTION]\n"
            "You are an assistant specialized in energy bill analysis (Enel PDF Parser). "
            "Only answer questions related to the provided dataset."
        )
        prompt = f"{instruction}\n{safety_prompt}\n{value}\n{suffix}"

        resp = self.anthropic.completions.create(model=self.model, prompt=prompt)
        # Depending on version, response text may be in different fields
        try:
            return resp.completion
        except Exception:
            return str(resp)


def available_providers() -> List[str]:
    providers = []
    import sys
    import importlib.util

    # Deterministic detection (preferred): check sys.modules so tests can monkeypatch.
    mod_keys = set(sys.modules.keys())

    # Google: either already imported or available via installed package
    google_present = any(
        k == "google.genai" or k == "google.generativeai" or k.startswith("google.gen")
        for k in mod_keys
    )
    if not google_present:
        try:
            if importlib.util.find_spec("google.genai") or importlib.util.find_spec("google.generativeai"):
                google_present = True
        except Exception:
            # find_spec can raise if parent package missing; ignore and treat as not present
            google_present = False
    if google_present:
        providers.append("google")

    # OpenAI
    try:
        openai_present = "openai" in mod_keys or importlib.util.find_spec("openai") is not None
    except Exception:
        openai_present = "openai" in mod_keys
    if openai_present:
        providers.append("openai")

    # Anthropic
    try:
        anthropic_present = "anthropic" in mod_keys or importlib.util.find_spec("anthropic") is not None
    except Exception:
        anthropic_present = "anthropic" in mod_keys
    if anthropic_present:
        providers.append("anthropic")

    return providers


def list_models(provider: str, api_key: str) -> Tuple[List[str], Optional[str]]:
    provider = provider.lower()
    try:
        if provider == "google":
            try:
                import google.genai as genai  # type: ignore
            except Exception:
                import google.generativeai as genai  # type: ignore
            client = genai.Client(api_key=api_key)
            resp = list(client.models.list())
            model_names = [getattr(m, "name", str(m)) for m in resp]
            return model_names, None

        if provider == "openai":
            import openai

            openai.api_key = api_key
            resp = openai.Model.list()
            model_names = [m["id"] for m in resp.data]
            return model_names, None

        if provider == "anthropic":
            try:
                from anthropic import Anthropic
            except Exception:
                return [], "anthropic package not found"
            client = Anthropic(api_key=api_key)
            # Some versions may not have a models.list API; best effort
            try:
                resp = client.models.list()
                model_names = [m["id"] for m in resp["data"]]
                return model_names, None
            except Exception:
                return [], "could not list Anthropic models via SDK"

        return [], f"Provider '{provider}' not supported"
    except Exception as e:
        return [], str(e)


def create_adapter(provider: str, api_key: str, model: str) -> LLM:
    provider = provider.lower()
    if provider == "google":
        return GoogleGenaiAdapter(api_key=api_key, model=model)
    if provider == "openai":
        return OpenAIAdapter(api_key=api_key, model=model)
    if provider == "anthropic":
        return AnthropicAdapter(api_key=api_key, model=model)
    raise ProviderUnavailable(f"Provider '{provider}' not supported")
