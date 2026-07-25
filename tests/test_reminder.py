import subprocess
from datetime import datetime, timedelta

import pytest

from actions import reminder as reminder_module
from actions.reminder import reminder


class FakePlayer:
    def __init__(self):
        self.logs: list[str] = []

    def write_log(self, message):
        self.logs.append(message)


@pytest.fixture
def temp_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("TEMP", str(tmp_path))
    return tmp_path


@pytest.fixture
def schtasks(monkeypatch):
    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, stdout="SUCCESS", stderr="")

    monkeypatch.setattr(reminder_module.subprocess, "run", fake_run)
    return calls


def _future(minutes=60):
    target = datetime.now() + timedelta(minutes=minutes)
    return {"date": target.strftime("%Y-%m-%d"), "time": target.strftime("%H:%M")}


@pytest.mark.parametrize(
    "params",
    [
        {},
        {"date": "2099-01-01"},
        {"time": "10:00"},
    ],
)
def test_requires_date_and_time(params):
    assert reminder(params) == "I need both a date and a time to set a reminder."


def test_rejects_past_datetime():
    past = datetime.now() - timedelta(days=1)
    params = {"date": past.strftime("%Y-%m-%d"), "time": past.strftime("%H:%M")}
    assert reminder(params) == "That time is already in the past."


def test_rejects_unparseable_datetime():
    assert reminder({"date": "tomorrow", "time": "noon"}) == (
        "I couldn't understand that date or time format."
    )


def test_creates_scheduled_task(temp_dir, schtasks):
    params = {**_future(), "message": 'Take "meds" now'}
    result = reminder(params)

    assert result.startswith("Reminder set for ")
    assert len(schtasks) == 1
    command = schtasks[0]
    assert command.startswith("schtasks /Create /TN ")
    assert "MARKReminder_" in command

    notify_scripts = list(temp_dir.glob("*.pyw"))
    assert len(notify_scripts) == 1
    script = notify_scripts[0].read_text(encoding="utf-8")
    assert "Take meds now" in script  # quotes stripped from the message
    assert not list(temp_dir.glob("*.xml"))  # xml is cleaned up after scheduling


def test_truncates_long_message(temp_dir, schtasks):
    reminder({**_future(), "message": "m" * 500})
    script = next(temp_dir.glob("*.pyw")).read_text(encoding="utf-8")
    assert "m" * 200 in script
    assert "m" * 201 not in script


def test_default_message(temp_dir, schtasks):
    reminder(_future())
    assert "Reminder" in next(temp_dir.glob("*.pyw")).read_text(encoding="utf-8")


def test_logs_to_player(temp_dir, schtasks):
    player = FakePlayer()
    params = _future()
    reminder(params, player=player)
    assert player.logs == [f"[reminder] set for {params['date']} {params['time']}"]


def test_reports_schtasks_failure(temp_dir, monkeypatch, capsys):
    def fake_run(command, **kwargs):
        return subprocess.CompletedProcess(command, 1, stdout="", stderr="Access denied")

    monkeypatch.setattr(reminder_module.subprocess, "run", fake_run)

    assert reminder(_future()) == "I couldn't schedule the reminder due to a system error."
    assert "schtasks failed: Access denied" in capsys.readouterr().out
    assert not list(temp_dir.glob("*.pyw"))  # notify script is cleaned up


def test_unexpected_error_is_wrapped(monkeypatch, temp_dir):
    monkeypatch.setattr(
        reminder_module.subprocess,
        "run",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("scheduler exploded")),
    )
    assert reminder(_future()).startswith("Something went wrong while scheduling the reminder:")


def test_prefers_pythonw_on_windows(temp_dir, schtasks, monkeypatch):
    monkeypatch.setattr(reminder_module.sys, "executable", r"C:\Python\python.exe")
    monkeypatch.setattr(reminder_module.os.path, "exists", lambda path: True)
    reminder(_future())
    assert schtasks  # scheduling still succeeds with the windowless interpreter
