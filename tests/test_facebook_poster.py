import json
from unittest import mock

import pytest

from actions import facebook_poster as fp


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload


@pytest.fixture(autouse=True)
def isolated_posts_log(tmp_path, monkeypatch):
    """Every test gets its own posts-log file instead of touching the repo's."""
    monkeypatch.setattr(fp, "POSTS_LOG_PATH", tmp_path / "facebook_posts.json")
    yield


@pytest.fixture(autouse=True)
def configured_page(monkeypatch):
    """Stub out config lookups so tests never touch the real api_keys.json."""
    monkeypatch.setattr(fp, "get_facebook_page_id", lambda: "12345")
    monkeypatch.setattr(fp, "get_facebook_page_access_token", lambda: "test-token")
    yield


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    """Retry backoff sleeps up to 300s — never let a test actually wait."""
    monkeypatch.setattr(fp.time, "sleep", lambda *a, **k: None)


# --------------------------------------------------------------------------- #
# Missing-info guards (regression tests for the hallucinated-success bug)
# --------------------------------------------------------------------------- #

def test_missing_post_type_is_reported_not_hallucinated():
    """post_type omitted and no interactive terminal available: must return
    a clear failure, never silently proceed or hang."""
    result = fp.facebook_post({})
    assert "text, photo" in result.lower() or "post, یا video" in result


def test_text_post_without_text_content_is_reported_not_silently_posted():
    """Regression test: previously, an empty text_content would still fall
    through to _generate_caption() and could post an empty/placeholder
    caption without telling the user anything went wrong."""
    with mock.patch.object(fp.requests, "post") as post:
        result = fp.facebook_post({"post_type": "text"})
    post.assert_not_called()
    assert "didn't get the text" in result.lower() or "متن نہیں ملا" in result


def test_photo_post_without_media_path_is_reported_not_a_crash():
    """Regression test: previously, a missing media_path fell through to
    Path(None), which raises TypeError instead of a clean user-facing error."""
    result = fp.facebook_post({"post_type": "photo"})
    assert "file path" in result.lower() or "path نہیں ملا" in result


def test_ask_helpers_never_block_on_stdin():
    """The _ask_* fallbacks must not call input() — there's no terminal
    attached in the real async voice/GUI flow."""
    with mock.patch("builtins.input", side_effect=AssertionError("must not block on stdin")):
        assert fp._ask_post_type() == ""
        assert fp._ask_text_content() == ""
        assert fp._ask_media_path("photo") is None


# --------------------------------------------------------------------------- #
# Verified-execution: success/failure must come from a real API response
# --------------------------------------------------------------------------- #

def test_text_post_success_reports_real_post_id():
    with mock.patch.object(
        fp.requests, "post", return_value=FakeResponse({"id": "999_888"})
    ) as post:
        result = fp.facebook_post({"post_type": "text", "text_content": "welcome to velmora"})

    assert "999_888" in result
    assert post.call_args.kwargs["data"]["message"].startswith("welcome to velmora")

    logged = json.loads(fp.POSTS_LOG_PATH.read_text(encoding="utf-8"))
    assert logged[-1]["status"] == "success"
    assert logged[-1]["post_id"] == "999_888"


def test_text_post_never_reports_success_without_a_post_id():
    """Graph API can return HTTP 200 with no post id (e.g. some error
    payloads) — that must NOT be treated as success."""
    with mock.patch.object(fp.requests, "post", return_value=FakeResponse({})):
        with mock.patch.object(fp, "_post_via_browser", return_value=(False, None)):
            result = fp.facebook_post({"post_type": "text", "text_content": "hello"})

    assert "publish ہو گئی" not in result
    assert "published successfully" not in result.lower()

    logged = json.loads(fp.POSTS_LOG_PATH.read_text(encoding="utf-8")) if fp.POSTS_LOG_PATH.exists() else []
    assert not any(e["status"] == "success" for e in logged)


def test_text_post_api_failure_falls_back_to_browser_and_reports_that_failure_too():
    with mock.patch.object(fp.requests, "post", return_value=FakeResponse({"error": {"message": "boom"}}, 400)):
        with mock.patch.object(fp, "_post_via_browser", return_value=(False, None)) as browser_fallback:
            result = fp.facebook_post({"post_type": "text", "text_content": "hello"})

    browser_fallback.assert_called_once()
    assert "boom" in result or "not" in result.lower() or "نہیں" in result


# --------------------------------------------------------------------------- #
# Duplicate detection (photo/video)
# --------------------------------------------------------------------------- #

def test_duplicate_media_post_is_blocked_within_window(tmp_path):
    media = tmp_path / "clip.mp4"
    media.write_bytes(b"fake video bytes")
    file_hash = fp._file_hash(media)

    fp._log_post(
        status="success",
        page_id="12345",
        media_path=str(media),
        file_hash=file_hash,
        caption="old caption",
        post_type="video",
        post_id="already_posted_1",
    )

    result = fp.facebook_post({"post_type": "video", "media_path": str(media)})
    assert "already_posted_1" in result


def test_force_flag_bypasses_duplicate_check(tmp_path):
    media = tmp_path / "clip.mp4"
    media.write_bytes(b"fake video bytes")
    file_hash = fp._file_hash(media)

    fp._log_post(
        status="success",
        page_id="12345",
        media_path=str(media),
        file_hash=file_hash,
        caption="old caption",
        post_type="video",
        post_id="already_posted_1",
    )

    with mock.patch.object(
        fp.requests, "post", return_value=FakeResponse({"id": "new_post_2"})
    ):
        result = fp.facebook_post({
            "post_type": "video",
            "media_path": str(media),
            "force": True,
        })

    assert "new_post_2" in result


def test_missing_media_file_is_reported():
    result = fp.facebook_post({"post_type": "photo", "media_path": "/does/not/exist.jpg"})
    assert "not found" in result.lower() or "نہیں ملی" in result


def test_facebook_not_configured_is_reported(monkeypatch):
    def _raise():
        raise RuntimeError("'fb_page_access_token' is missing or empty")

    monkeypatch.setattr(fp, "get_facebook_page_access_token", _raise)
    result = fp.facebook_post({"post_type": "text", "text_content": "hi"})
    assert "not configured" in result.lower() or "کنفیگر نہیں" in result
