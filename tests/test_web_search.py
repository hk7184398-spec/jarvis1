import sys
import types

import pytest

from actions import web_search as ws
from core.paths import get_base_dir


class FakePlayer:
    def __init__(self):
        self.logs: list[str] = []

    def write_log(self, message):
        self.logs.append(message)


def test_get_base_dir_points_at_repo_root():
    assert (get_base_dir() / "actions").is_dir()


def test_format_ddg_without_results():
    assert ws._format_ddg("bitcoin", []) == "No results found for: bitcoin"


def test_format_ddg_renders_title_snippet_and_url():
    results = [
        {"title": "T1", "snippet": "S1", "url": "u1"},
        {"title": "", "snippet": "", "url": "u2"},
    ]
    text = ws._format_ddg("bitcoin", results)
    assert text.splitlines()[0] == "Search results for: bitcoin"
    assert "1. T1" in text
    assert "   S1" in text
    assert "   u1" in text
    assert "2." not in text
    assert text.endswith("u2")


def test_web_search_requires_query_or_items():
    assert ws.web_search({}) == "Please provide a search query, sir."
    assert ws.web_search(None) == "Please provide a search query, sir."


def test_web_search_uses_openrouter(fake_or_client):
    client = fake_or_client(reply="Bitcoin costs a lot.")
    assert ws.web_search({"query": " bitcoin price "}) == "Bitcoin costs a lot."
    assert client.calls[0]["prompt"] == "bitcoin price"


def test_web_search_logs_to_player(fake_or_client):
    fake_or_client(reply="answer")
    player = FakePlayer()
    ws.web_search({"query": "bitcoin"}, player=player)
    assert player.logs == ["[Search] bitcoin"]


def test_web_search_logs_items_when_query_missing(fake_or_client, monkeypatch):
    fake_or_client(reply="answer")
    player = FakePlayer()
    ws.web_search({"items": ["a", "b"]}, player=player)
    assert player.logs == ["[Search] a, b"]


def test_web_search_falls_back_to_ddg(fake_or_client, monkeypatch):
    fake_or_client(error=RuntimeError("rate limited"))
    monkeypatch.setattr(
        ws, "_ddg_search", lambda query, **kwargs: [{"title": "T", "snippet": "S", "url": "u"}]
    )
    result = ws.web_search({"query": "bitcoin"})
    assert "1. T" in result


def test_web_search_without_or_client_module(monkeypatch):
    monkeypatch.setitem(sys.modules, "or_client", None)
    monkeypatch.setattr(ws, "_ddg_search", lambda query, **kwargs: [])
    assert ws.web_search({"query": "bitcoin"}) == "No results found for: bitcoin"


def test_ddg_search_maps_result_fields(monkeypatch):
    class FakeDDGS:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def text(self, query, max_results=None):
            assert query == "bitcoin"
            assert max_results == 2
            return [{"title": "T", "body": "B", "href": "H"}, {}]

    module = types.ModuleType("ddgs")
    module.DDGS = FakeDDGS
    monkeypatch.setitem(sys.modules, "ddgs", module)

    assert ws._ddg_search("bitcoin", max_results=2) == [
        {"title": "T", "snippet": "B", "url": "H"},
        {"title": "", "snippet": "", "url": ""},
    ]


def test_gemini_search_concatenates_text_parts(monkeypatch, api_keys_file):
    class FakePart:
        def __init__(self, text):
            self.text = text

    class FakeModels:
        def generate_content(self, model, contents, config):
            assert config == {"tools": [{"google_search": {}}]}
            content = types.SimpleNamespace(parts=[FakePart("Hello "), FakePart(""), FakePart("world")])
            return types.SimpleNamespace(candidates=[types.SimpleNamespace(content=content)])

    class FakeClient:
        def __init__(self, api_key=None):
            self.models = FakeModels()

    genai = types.ModuleType("google.genai")
    genai.Client = FakeClient
    google_pkg = sys.modules.get("google") or types.ModuleType("google")
    monkeypatch.setitem(sys.modules, "google", google_pkg)
    monkeypatch.setitem(sys.modules, "google.genai", genai)
    monkeypatch.setattr(google_pkg, "genai", genai, raising=False)

    assert ws._gemini_search("hi") == "Hello world"


def test_gemini_search_rejects_empty_response(monkeypatch, api_keys_file):

    class FakeModels:
        def generate_content(self, **kwargs):
            content = types.SimpleNamespace(parts=[])
            return types.SimpleNamespace(candidates=[types.SimpleNamespace(content=content)])

    genai = types.ModuleType("google.genai")
    genai.Client = lambda api_key=None: types.SimpleNamespace(models=FakeModels())
    google_pkg = sys.modules.get("google") or types.ModuleType("google")
    monkeypatch.setitem(sys.modules, "google", google_pkg)
    monkeypatch.setitem(sys.modules, "google.genai", genai)
    monkeypatch.setattr(google_pkg, "genai", genai, raising=False)

    with pytest.raises(ValueError, match="empty response"):
        ws._gemini_search("hi")


def test_compare_prefers_gemini(monkeypatch):
    captured = {}

    def fake_gemini(query):
        captured["query"] = query
        return "gemini comparison"

    monkeypatch.setattr(ws, "_gemini_search", fake_gemini)
    assert ws._compare(["a", "b"], "price") == "gemini comparison"
    assert captured["query"].startswith("Compare a, b in terms of price.")


def test_compare_falls_back_to_ddg_per_item(monkeypatch):
    monkeypatch.setattr(ws, "_gemini_search", lambda query: (_ for _ in ()).throw(RuntimeError("no")))

    def fake_ddg(query, max_results=6):
        if query.startswith("b"):
            raise RuntimeError("ddg down")
        return [{"snippet": "cheap"}, {"snippet": "fast"}, {"snippet": "ignored"}]

    monkeypatch.setattr(ws, "_ddg_search", fake_ddg)
    text = ws._compare(["a", "b"], "price")
    assert "Comparison — PRICE" in text
    assert "▸ a" in text and "▸ b" in text
    assert "  • cheap" in text and "  • fast" in text
    assert "ignored" not in text
