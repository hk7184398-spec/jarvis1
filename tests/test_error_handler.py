import json

import pytest

from agent import error_handler
from agent.error_handler import ErrorDecision


@pytest.fixture(autouse=True)
def api_key(api_keys_file):
    return api_keys_file


STEP = {
    "step": 2,
    "tool": "file_controller",
    "description": "save results to desktop",
    "parameters": {"action": "write", "path": "desktop"},
    "critical": False,
}


def _analysis(decision="retry", **extra):
    payload = {
        "decision": decision,
        "reason": "network blip",
        "fix_suggestion": "use another tool",
        "max_retries": 1,
        "user_message": "One moment, sir.",
    }
    payload.update(extra)
    return json.dumps(payload)


def test_analyze_error_forces_replan_at_max_attempts(fake_genai):
    result = error_handler.analyze_error(STEP, "boom", attempt=2, max_attempts=2)
    assert result["decision"] is ErrorDecision.REPLAN
    assert result["max_retries"] == 0
    assert "Failed 2 times" in result["reason"]
    assert fake_genai.models == []


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("retry", ErrorDecision.RETRY),
        ("SKIP", ErrorDecision.SKIP),
        ("replan", ErrorDecision.REPLAN),
        ("abort", ErrorDecision.ABORT),
        ("nonsense", ErrorDecision.REPLAN),
    ],
)
def test_analyze_error_maps_decisions(fake_genai, raw, expected):
    fake_genai.response = _analysis(raw)
    result = error_handler.analyze_error(STEP, "boom")
    assert result["decision"] is expected


def test_analyze_error_strips_markdown_fences(fake_genai):
    fake_genai.response = f"```json\n{_analysis('skip')}\n```"
    assert error_handler.analyze_error(STEP, "boom")["decision"] is ErrorDecision.SKIP


def test_analyze_error_prompt_contains_step_details(fake_genai):
    fake_genai.response = _analysis()
    error_handler.analyze_error(STEP, "E" * 900, attempt=1, max_attempts=3)
    prompt = fake_genai.models[0].prompts[0]
    assert "Tool: file_controller" in prompt
    assert "save results to desktop" in prompt
    assert "Attempt number: 1" in prompt
    assert "E" * 500 in prompt and "E" * 501 not in prompt


def test_analyze_error_upgrades_skip_to_replan_for_critical_step(fake_genai):
    fake_genai.response = _analysis("skip")
    critical_step = {**STEP, "critical": True}
    result = error_handler.analyze_error(critical_step, "boom")
    assert result["decision"] is ErrorDecision.REPLAN
    assert "critical" in result["user_message"]


def test_analyze_error_defaults_to_replan_on_bad_json(fake_genai, capsys):
    fake_genai.response = "not json"
    result = error_handler.analyze_error(STEP, "boom")
    assert result["decision"] is ErrorDecision.REPLAN
    assert result["max_retries"] == 1
    assert "Analysis failed" in capsys.readouterr().out


def test_analyze_error_defaults_to_replan_when_model_raises(fake_genai):
    fake_genai.response = RuntimeError("api down")
    result = error_handler.analyze_error(STEP, "boom")
    assert result["decision"] is ErrorDecision.REPLAN
    assert result["reason"] == "api down"


def test_generate_fix_builds_code_helper_step(fake_genai):
    fake_genai.response = "```python\nprint('hi')\n```"
    fixed = error_handler.generate_fix(STEP, "boom", "use python")
    assert fixed["tool"] == "code_helper"
    assert fixed["step"] == STEP["step"]
    assert fixed["parameters"]["code"] == "print('hi')"
    assert fixed["parameters"]["action"] == "run"
    assert fixed["parameters"]["language"] == "python"
    assert fixed["critical"] is False
    assert fixed["depends_on"] == []


def test_generate_fix_preserves_dependencies(fake_genai):
    fake_genai.response = "print(1)"
    step = {**STEP, "depends_on": [1], "critical": True}
    fixed = error_handler.generate_fix(step, "boom", "try again")
    assert fixed["depends_on"] == [1]
    assert fixed["critical"] is True


def test_generate_fix_falls_back_when_model_raises(fake_genai, capsys):
    fake_genai.response = RuntimeError("api down")
    fixed = error_handler.generate_fix(STEP, "boom", "use python")
    assert fixed["tool"] == "generated_code"
    assert fixed["parameters"] == {"description": STEP["description"]}
    assert "Fix generation failed" in capsys.readouterr().out
