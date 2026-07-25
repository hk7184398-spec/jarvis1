import json

import pytest

from memory import config_manager


@pytest.fixture
def config_dir(tmp_path, monkeypatch):
    config_dir = tmp_path / "config"
    monkeypatch.setattr(config_manager, "BASE_DIR", tmp_path)
    monkeypatch.setattr(config_manager, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(config_manager, "CONFIG_FILE", config_dir / "api_keys.json")
    return config_dir


def test_get_base_dir_returns_repo_root():
    assert (config_manager.get_base_dir() / "memory").is_dir()


def test_get_base_dir_when_frozen(monkeypatch, tmp_path):
    monkeypatch.setattr(config_manager.sys, "frozen", True, raising=False)
    monkeypatch.setattr(config_manager.sys, "executable", str(tmp_path / "jarvis.exe"))
    assert config_manager.get_base_dir() == tmp_path


def test_ensure_config_dir_is_idempotent(config_dir):
    config_manager.ensure_config_dir()
    config_manager.ensure_config_dir()
    assert config_dir.is_dir()


def test_config_exists(config_dir):
    assert config_manager.config_exists() is False
    config_dir.mkdir()
    (config_dir / "api_keys.json").write_text("{}", encoding="utf-8")
    assert config_manager.config_exists() is True


def test_save_api_keys_creates_file_and_strips_whitespace(config_dir):
    config_manager.save_api_keys("  my-secret-key  ")
    data = json.loads((config_dir / "api_keys.json").read_text(encoding="utf-8"))
    assert data == {"gemini_api_key": "my-secret-key"}


def test_save_api_keys_preserves_other_keys(config_dir):
    config_dir.mkdir()
    (config_dir / "api_keys.json").write_text(
        json.dumps({"openrouter_api_key": "or-key"}), encoding="utf-8"
    )
    config_manager.save_api_keys("gem-key")
    data = json.loads((config_dir / "api_keys.json").read_text(encoding="utf-8"))
    assert data == {"openrouter_api_key": "or-key", "gemini_api_key": "gem-key"}


def test_save_api_keys_overwrites_corrupt_file(config_dir):
    config_dir.mkdir()
    (config_dir / "api_keys.json").write_text("not json", encoding="utf-8")
    config_manager.save_api_keys("gem-key")
    data = json.loads((config_dir / "api_keys.json").read_text(encoding="utf-8"))
    assert data == {"gemini_api_key": "gem-key"}


def test_load_api_keys_missing_file(config_dir):
    assert config_manager.load_api_keys() == {}


def test_load_api_keys_corrupt_file(config_dir, capsys):
    config_dir.mkdir()
    (config_dir / "api_keys.json").write_text("{invalid", encoding="utf-8")
    assert config_manager.load_api_keys() == {}
    assert "Failed to load api_keys.json" in capsys.readouterr().out


def test_get_gemini_key(config_dir):
    assert config_manager.get_gemini_key() is None
    config_manager.save_api_keys("gem-key")
    assert config_manager.get_gemini_key() == "gem-key"


@pytest.mark.parametrize(
    "key, expected",
    [
        ("", False),
        ("short", False),
        ("x" * 16, True),
    ],
)
def test_is_configured_requires_key_longer_than_15_chars(config_dir, key, expected):
    config_manager.save_api_keys(key)
    assert config_manager.is_configured() is expected


def test_is_configured_without_config_file(config_dir):
    assert config_manager.is_configured() is False
