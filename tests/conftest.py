import sys
import types
from pathlib import Path

import pytest

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))


class FakeResponse:
    def __init__(self, text: str):
        self.text = text


class FakeModel:
    """Stand-in for google.generativeai.GenerativeModel."""

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        self.prompts: list[str] = []

    def generate_content(self, prompt):
        self.prompts.append(prompt)
        behaviour = self._registry
        if isinstance(behaviour, Exception):
            raise behaviour
        return FakeResponse(behaviour)


class FakeGenai(types.ModuleType):
    """Minimal google.generativeai replacement with scripted responses."""

    def __init__(self):
        super().__init__("google.generativeai")
        self.configured_keys: list[str] = []
        self.models: list[FakeModel] = []
        self.response = "{}"

    def configure(self, api_key=None, **kwargs):
        self.configured_keys.append(api_key)

    def GenerativeModel(self, *args, **kwargs):  # noqa: N802 - mimics upstream API
        model = FakeModel(*args, **kwargs)
        model._registry = self.response
        self.models.append(model)
        return model


@pytest.fixture
def fake_genai(monkeypatch):
    """Installs a fake ``google.generativeai`` module for the duration of a test."""
    fake = FakeGenai()
    google_pkg = sys.modules.get("google")
    if google_pkg is None:
        google_pkg = types.ModuleType("google")
        google_pkg.__path__ = []
        monkeypatch.setitem(sys.modules, "google", google_pkg)
    monkeypatch.setitem(sys.modules, "google.generativeai", fake)
    monkeypatch.setattr(google_pkg, "generativeai", fake, raising=False)
    return fake


class FakeORClient:
    """Stand-in for ``or_client.client``."""

    def __init__(self, reply="OK", error=None):
        self.reply = reply
        self.error = error
        self.calls: list[dict] = []

    def chat(self, prompt, system=None, model=None, max_tokens=None, temperature=None):
        self.calls.append(
            {
                "prompt": prompt,
                "system": system,
                "model": model,
                "max_tokens": max_tokens,
                "temperature": temperature,
            }
        )
        if self.error:
            raise self.error
        return self.reply


@pytest.fixture
def fake_or_client(monkeypatch):
    """Installs a fake ``or_client`` module; returns a factory for the client."""

    def _install(reply="OK", error=None):
        client = FakeORClient(reply=reply, error=error)
        module = types.ModuleType("or_client")
        module.client = client
        monkeypatch.setitem(sys.modules, "or_client", module)
        return client

    return _install
