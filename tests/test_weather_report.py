import pytest

from actions import weather_report


class FakePlayer:
    def __init__(self, fail=False):
        self.fail = fail
        self.logs: list[str] = []

    def write_log(self, message):
        if self.fail:
            raise RuntimeError("log broke")
        self.logs.append(message)


class FakeSessionMemory:
    def __init__(self, fail=False):
        self.fail = fail
        self.searches: list[dict] = []

    def set_last_search(self, query, response):
        if self.fail:
            raise RuntimeError("memory broke")
        self.searches.append({"query": query, "response": response})


@pytest.fixture
def opened(monkeypatch):
    urls = []
    monkeypatch.setattr(weather_report.webbrowser, "open", urls.append)
    return urls


@pytest.mark.parametrize("city", [None, "", 42])
def test_missing_city_returns_error(opened, city):
    player = FakePlayer()
    msg = weather_report.weather_action({"city": city}, player=player)
    assert msg == "Sir, the city is missing for the weather report."
    assert opened == []
    assert player.logs == ["JARVIS: " + msg]


def test_defaults_time_to_today(opened):
    msg = weather_report.weather_action({"city": " Ankara "})
    assert msg == "Showing the weather for Ankara, today, sir."
    assert opened == ["https://www.google.com/search?q=weather+in+Ankara+today"]


@pytest.mark.parametrize("time_value", [None, "", 7])
def test_invalid_time_falls_back_to_today(opened, time_value):
    weather_report.weather_action({"city": "Ankara", "time": time_value})
    assert opened == ["https://www.google.com/search?q=weather+in+Ankara+today"]


def test_uses_provided_time(opened):
    msg = weather_report.weather_action({"city": "Ankara", "time": " tomorrow "})
    assert msg == "Showing the weather for Ankara, tomorrow, sir."
    assert opened == ["https://www.google.com/search?q=weather+in+Ankara+tomorrow"]


def test_browser_failure_is_reported(monkeypatch):
    def boom(url):
        raise RuntimeError("no browser")

    monkeypatch.setattr(weather_report.webbrowser, "open", boom)
    msg = weather_report.weather_action({"city": "Ankara"})
    assert msg == "Sir, I couldn't open the browser for the weather report."


def test_session_memory_records_search(opened):
    memory = FakeSessionMemory()
    msg = weather_report.weather_action({"city": "Ankara"}, session_memory=memory)
    assert memory.searches == [{"query": "weather in Ankara today", "response": msg}]


def test_session_memory_errors_are_swallowed(opened):
    memory = FakeSessionMemory(fail=True)
    assert weather_report.weather_action({"city": "Ankara"}, session_memory=memory).startswith(
        "Showing the weather"
    )


def test_player_log_errors_are_swallowed(opened):
    player = FakePlayer(fail=True)
    assert weather_report.weather_action({"city": "Ankara"}, player=player).startswith(
        "Showing the weather"
    )


def test_speak_and_log_without_player():
    assert weather_report._speak_and_log("message") is None
