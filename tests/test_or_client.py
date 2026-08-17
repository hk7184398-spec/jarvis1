import base64
import importlib
import json
import sys
from unittest import mock

import pytest

from core import config as core_config


def _load_or_client(tmp_path, monkeypatch, api_keys: dict | None = None, write=True):
    """Imports ``or_client`` with a stubbed api_keys.json (a client is built at import)."""
    path = tmp_path / "api_keys.json"
    if write:
        payload = {"openrouter_api_key": "test-key"} if api_keys is None else api_keys
        path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(core_config, "API_CONFIG_PATH", path)
    monkeypatch.setattr(core_config, "CONFIG_DIR", tmp_path)
    sys.modules.pop("or_client", None)
    return importlib.import_module("or_client")


@pytest.fixture
def or_client(tmp_path, monkeypatch):
    module = _load_or_client(tmp_path, monkeypatch)
    module._rate_limited.clear()
    yield module
    module._rate_limited.clear()
    sys.modules.pop("or_client", None)


class FakeHTTPResponse:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.text = text

    def json(self):
        return self._payload


def _content(text):
    return {"choices": [{"message": {"content": text}}]}


def test_load_api_key_missing_file(tmp_path, monkeypatch):
    with pytest.raises(RuntimeError, match="api_keys.json not found"):
        _load_or_client(tmp_path, monkeypatch, write=False)


def test_load_api_key_empty_key(tmp_path, monkeypatch):
    with pytest.raises(RuntimeError, match="'openrouter_api_key' is missing or empty"):
        _load_or_client(tmp_path, monkeypatch, {"openrouter_api_key": "  "})


def test_module_level_client_is_built_from_config_file(or_client):
    assert or_client.client.api_key == "test-key"


def test_client_sets_auth_headers(or_client):
    client = or_client.OpenRouterClient()
    assert client._headers["Authorization"] == "Bearer test-key"
    assert client._headers["X-Title"] == "MARK XXV"


def test_call_returns_stripped_content(or_client):
    client = or_client.OpenRouterClient()
    with mock.patch.object(
        or_client.requests, "post", return_value=FakeHTTPResponse(200, _content("  hi  "))
    ) as post:
        assert client._call("m", [{"role": "user", "content": "q"}]) == ("hi", "")
    assert post.call_args.kwargs["json"]["model"] == "m"
    assert "response_format" not in post.call_args.kwargs["json"]


def test_call_passes_response_format(or_client):
    client = or_client.OpenRouterClient()
    with mock.patch.object(
        or_client.requests, "post", return_value=FakeHTTPResponse(200, _content("hi"))
    ) as post:
        client._call("m", [], response_format={"type": "json_object"})
    assert post.call_args.kwargs["json"]["response_format"] == {"type": "json_object"}


def test_call_returns_none_for_empty_content(or_client):
    client = or_client.OpenRouterClient()
    with mock.patch.object(
        or_client.requests, "post", return_value=FakeHTTPResponse(200, _content(""))
    ):
        result, error = client._call("m", [])
        assert result is None
        assert "empty completion" in error


def test_call_marks_rate_limited_on_429(or_client):
    client = or_client.OpenRouterClient()
    with mock.patch.object(or_client.requests, "post", return_value=FakeHTTPResponse(429)):
        result, error = client._call("m", [])
        assert result is None
        assert "rate limited" in error
    assert client._is_rate_limited("m") is True


def test_call_retries_on_http_error_then_gives_up(or_client):
    client = or_client.OpenRouterClient()
    with mock.patch.object(
        or_client.requests, "post", return_value=FakeHTTPResponse(500, text="server exploded")
    ) as post, mock.patch.object(or_client.time, "sleep"):
        result, error = client._call("m", [])
        assert result is None
        assert "HTTP 500" in error
    assert post.call_count == or_client.MAX_RETRIES_PER_MODEL


def test_call_retries_on_timeout(or_client):
    client = or_client.OpenRouterClient()
    responses = [or_client.requests.exceptions.Timeout(), FakeHTTPResponse(200, _content("late"))]
    with mock.patch.object(or_client.requests, "post", side_effect=responses), \
            mock.patch.object(or_client.time, "sleep"):
        assert client._call("m", []) == ("late", "")


def test_call_handles_unexpected_exception(or_client):
    client = or_client.OpenRouterClient()
    with mock.patch.object(or_client.requests, "post", side_effect=ValueError("boom")), \
            mock.patch.object(or_client.time, "sleep"):
        result, error = client._call("m", [])
        assert result is None
        assert "boom" in error


def test_rate_limit_expires_after_cooldown(or_client):
    client = or_client.OpenRouterClient()
    client._mark_rate_limited("m")
    with mock.patch.object(
        or_client.time, "time", return_value=or_client.time.time() + or_client.RATE_LIMIT_COOLDOWN + 1
    ):
        assert client._is_rate_limited("m") is False
    assert "m" not in or_client._rate_limited


def test_call_with_fallback_uses_requested_model_first(or_client):
    client = or_client.OpenRouterClient()
    with mock.patch.object(client, "_call", return_value=("answer", "")) as call:
        assert client._call_with_fallback(["pool-a"], [], model="chosen") == "answer"
    assert call.call_args.args[0] == "chosen"


def test_call_with_fallback_skips_rate_limited_models(or_client):
    client = or_client.OpenRouterClient()
    client._mark_rate_limited("busy")
    tried = []

    def fake_call(model, *args, **kwargs):
        tried.append(model)
        return ("answer", "") if model == "free" else (None, f"{model}: failed")

    with mock.patch.object(client, "_call", side_effect=fake_call):
        assert client._call_with_fallback(["busy", "free"], [], model="busy") == "answer"
    assert tried == ["free"]


def test_call_with_fallback_raises_when_all_models_fail(or_client):
    client = or_client.OpenRouterClient()
    with mock.patch.object(client, "_call", return_value=(None, "boom")):
        with pytest.raises(RuntimeError, match="All models failed"):
            client._call_with_fallback(["a", "b"], [])


def test_chat_builds_system_and_user_messages(or_client):
    client = or_client.OpenRouterClient()
    with mock.patch.object(client, "_call_with_fallback", return_value="hello") as call:
        assert client.chat("hi", system="be terse") == "hello"
    messages = call.call_args.args[1]
    assert messages == [
        {"role": "system", "content": "be terse"},
        {"role": "user", "content": "hi"},
    ]
    assert call.call_args.args[0] is or_client.TEXT_MODELS


@pytest.mark.parametrize(
    "raw",
    [
        '{"a": 1}',
        '```json\n{"a": 1}\n```',
        '```\n{"a": 1}\n```',
    ],
)
def test_chat_json_parses_fenced_and_plain_json(or_client, raw):
    client = or_client.OpenRouterClient()
    with mock.patch.object(client, "_call_with_fallback", return_value=raw):
        assert client.chat_json("prompt") == {"a": 1}


def test_chat_json_raises_on_unparseable_output(or_client):
    client = or_client.OpenRouterClient()
    with mock.patch.object(client, "_call_with_fallback", return_value="nope"):
        with pytest.raises(ValueError, match="unparseable JSON"):
            client.chat_json("prompt")


def test_vision_embeds_data_url(or_client):
    client = or_client.OpenRouterClient()
    with mock.patch.object(client, "_call_with_fallback", return_value="a cat") as call:
        assert client.vision("what is this?", "Ymtz", mime="image/jpeg") == "a cat"
    content = call.call_args.args[1][1]["content"]
    assert content[0]["image_url"]["url"] == "data:image/jpeg;base64,Ymtz"
    assert content[1] == {"type": "text", "text": "what is this?"}
    assert call.call_args.args[0] is or_client.VISION_MODELS


@pytest.mark.parametrize(
    "suffix, mime",
    [(".png", "image/png"), (".JPG", "image/jpeg"), (".webp", "image/webp"), (".bmp", "image/png")],
)
def test_vision_from_file_maps_mime_types(or_client, tmp_path, suffix, mime):
    image = tmp_path / f"shot{suffix}"
    image.write_bytes(b"bytes")
    client = or_client.OpenRouterClient()
    with mock.patch.object(client, "vision", return_value="described") as vision:
        assert client.vision_from_file("describe", str(image)) == "described"
    assert vision.call_args.args[1] == base64.b64encode(b"bytes").decode()
    assert vision.call_args.args[2] == mime


def test_multi_turn_passes_history_through(or_client):
    client = or_client.OpenRouterClient()
    history = [{"role": "user", "content": "hi"}]
    with mock.patch.object(client, "_call_with_fallback", return_value="hello") as call:
        assert client.multi_turn(history) == "hello"
    assert call.call_args.args[1] is history


def test_available_models_reports_pools_and_cooldowns(or_client):
    client = or_client.OpenRouterClient()
    client._mark_rate_limited("busy")
    info = client.available_models()
    assert info["total_text"] == len(or_client.TEXT_MODELS)
    assert info["total_vision"] == len(or_client.VISION_MODELS)
    assert info["rate_limited"] == ["busy"]
