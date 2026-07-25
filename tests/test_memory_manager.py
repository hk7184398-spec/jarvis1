import json

import pytest

from memory import memory_manager as mm


@pytest.fixture
def memory_path(tmp_path, monkeypatch):
    path = tmp_path / "memory" / "long_term.json"
    monkeypatch.setattr(mm, "MEMORY_PATH", path)
    return path


def _entry(value, updated="2024-01-01"):
    return {"value": value, "updated": updated}


def test_load_memory_returns_empty_skeleton_when_missing(memory_path):
    assert mm.load_memory() == mm._empty_memory()


def test_load_memory_fills_missing_categories(memory_path):
    memory_path.parent.mkdir(parents=True)
    memory_path.write_text(json.dumps({"identity": {"name": _entry("Ali")}}), encoding="utf-8")
    memory = mm.load_memory()
    assert memory["identity"]["name"]["value"] == "Ali"
    assert set(memory) == set(mm._empty_memory())
    assert memory["notes"] == {}


def test_load_memory_rejects_non_dict_payload(memory_path):
    memory_path.parent.mkdir(parents=True)
    memory_path.write_text("[1, 2, 3]", encoding="utf-8")
    assert mm.load_memory() == mm._empty_memory()


def test_load_memory_handles_corrupt_file(memory_path, capsys):
    memory_path.parent.mkdir(parents=True)
    memory_path.write_text("{oops", encoding="utf-8")
    assert mm.load_memory() == mm._empty_memory()
    assert "Load error" in capsys.readouterr().out


def test_save_memory_creates_parent_directory(memory_path):
    mm.save_memory({"identity": {"name": _entry("Ali")}})
    assert json.loads(memory_path.read_text(encoding="utf-8"))["identity"]["name"]["value"] == "Ali"


def test_save_memory_ignores_non_dict(memory_path):
    mm.save_memory("not a dict")
    assert not memory_path.exists()


def test_all_entries_skips_malformed_categories_and_entries():
    memory = {
        "identity": {"name": _entry("Ali"), "broken": "plain string"},
        "preferences": "not a dict",
    }
    assert mm._all_entries(memory) == [("identity", "name", _entry("Ali"))]


def test_trim_to_limit_keeps_small_memory_untouched():
    memory = {"notes": {"a": _entry("short")}}
    assert mm._trim_to_limit(memory) is memory


def test_trim_to_limit_drops_oldest_entries_first(monkeypatch):
    memory = {
        "notes": {
            "old": _entry("x" * 300, updated="2020-01-01"),
            "mid": _entry("y" * 300, updated="2022-01-01"),
            "new": _entry("z" * 300, updated="2024-01-01"),
        }
    }
    monkeypatch.setattr(mm, "MEMORY_MAX_CHARS", 700)

    trimmed = mm._trim_to_limit(memory)

    assert "old" not in trimmed["notes"]
    assert "new" in trimmed["notes"]
    assert len(json.dumps(trimmed, ensure_ascii=False)) <= 700


def test_truncate_value():
    assert mm._truncate_value("short") == "short"
    assert mm._truncate_value(42) == 42
    long_value = "a" * (mm.MAX_VALUE_LENGTH + 50)
    truncated = mm._truncate_value(long_value)
    assert truncated.endswith("…")
    assert len(truncated) == mm.MAX_VALUE_LENGTH + 1


def test_recursive_update_skips_empty_values():
    target = {}
    assert mm._recursive_update(target, {"a": None, "b": "   "}) is False
    assert target == {}


def test_recursive_update_writes_nested_entries():
    target = {}
    assert mm._recursive_update(target, {"identity": {"name": {"value": "Ali"}}}) is True
    assert target["identity"]["name"]["value"] == "Ali"
    assert "updated" in target["identity"]["name"]


def test_recursive_update_accepts_plain_scalar_values():
    target = {}
    assert mm._recursive_update(target, {"preferences": {"color": "blue"}}) is True
    assert target["preferences"]["color"]["value"] == "blue"


def test_recursive_update_replaces_non_dict_branch():
    target = {"identity": "corrupt"}
    assert mm._recursive_update(target, {"identity": {"name": {"value": "Ali"}}}) is True
    assert target["identity"]["name"]["value"] == "Ali"


def test_recursive_update_returns_false_for_unchanged_value():
    target = {"notes": {"a": _entry("same")}}
    assert mm._recursive_update(target, {"notes": {"a": {"value": "same"}}}) is False


def test_update_memory_persists_changes(memory_path):
    memory = mm.update_memory({"identity": {"name": {"value": "Ali"}}})
    assert memory["identity"]["name"]["value"] == "Ali"
    assert json.loads(memory_path.read_text(encoding="utf-8"))["identity"]["name"]["value"] == "Ali"


def test_update_memory_ignores_empty_update(memory_path):
    assert mm.update_memory({}) == mm._empty_memory()
    assert mm.update_memory("nope") == mm._empty_memory()
    assert not memory_path.exists()


def test_should_extract_memory_true(fake_or_client):
    client = fake_or_client(reply="yes")
    assert mm.should_extract_memory("I am Ali", "Nice to meet you") is True
    assert client.calls[0]["max_tokens"] == 5


def test_should_extract_memory_false(fake_or_client):
    fake_or_client(reply="NO")
    assert mm.should_extract_memory("what time is it", "It is noon") is False


def test_should_extract_memory_swallows_errors(fake_or_client, capsys):
    fake_or_client(error=RuntimeError("boom"))
    assert mm.should_extract_memory("a", "b") is False
    assert "Stage1 check failed" in capsys.readouterr().out


def test_extract_memory_parses_fenced_json(fake_or_client):
    fake_or_client(reply='```json\n{"identity": {"name": {"value": "Ali"}}}\n```')
    assert mm.extract_memory("I am Ali", "Hello Ali") == {"identity": {"name": {"value": "Ali"}}}


def test_extract_memory_empty_object(fake_or_client):
    fake_or_client(reply="{}")
    assert mm.extract_memory("hi", "hello") == {}


def test_extract_memory_invalid_json(fake_or_client):
    fake_or_client(reply="not json at all")
    assert mm.extract_memory("hi", "hello") == {}


def test_extract_memory_swallows_rate_limit_quietly(fake_or_client, capsys):
    fake_or_client(error=RuntimeError("429 too many requests"))
    assert mm.extract_memory("hi", "hello") == {}
    assert capsys.readouterr().out == ""


def test_format_memory_for_prompt_empty():
    assert mm.format_memory_for_prompt(None) == ""
    assert mm.format_memory_for_prompt({}) == ""
    assert mm.format_memory_for_prompt(mm._empty_memory()) == ""


def test_format_memory_for_prompt_orders_identity_fields_first():
    memory = {
        "identity": {"custom_field": _entry("extra"), "name": _entry("Ali"), "city": _entry("Ankara")},
        "preferences": {"favorite_color": _entry("blue")},
        "projects": {"mark_xxv": _entry("AI assistant")},
        "relationships": {"friend_yusuf": "close friend"},
        "wishes": {"buy_guitar": _entry("acoustic guitar")},
        "notes": {"works_at_night": _entry("late nights")},
    }
    text = mm.format_memory_for_prompt(memory)
    assert text.startswith("[WHAT YOU KNOW ABOUT THIS PERSON")
    assert text.index("Name: Ali") < text.index("City: Ankara") < text.index("Custom Field: extra")
    for expected in (
        "Preferences:",
        "  - Favorite Color: blue",
        "Active Projects / Goals:",
        "People in their life:",
        "  - Friend Yusuf: close friend",
        "Wishes / Plans / Wants:",
        "Other notes:",
        "  - works_at_night: late nights",
    ):
        assert expected in text
    assert text.endswith("\n")


def test_format_memory_for_prompt_truncates_long_output():
    memory = {"notes": {f"note_{i}": _entry("x" * 300) for i in range(20)}}
    text = mm.format_memory_for_prompt(memory)
    assert len(text) <= 2001
    assert "…" in text


def test_remember_defaults_invalid_category_to_notes(memory_path):
    msg = mm.remember("thing", "value", category="bogus")
    assert msg == "Remembered: notes/thing = value"
    assert mm.load_memory()["notes"]["thing"]["value"] == "value"


def test_remember_uses_valid_category(memory_path):
    mm.remember("favorite_color", "blue", category="preferences")
    assert mm.load_memory()["preferences"]["favorite_color"]["value"] == "blue"


def test_forget_removes_entry(memory_path):
    mm.remember("thing", "value")
    assert mm.forget("thing") == "Forgotten: notes/thing"
    assert "thing" not in mm.load_memory()["notes"]


def test_forget_missing_entry(memory_path):
    assert mm.forget("nope", category="identity") == "Not found: identity/nope"


def test_forget_memory_alias():
    assert mm.forget_memory is mm.forget
