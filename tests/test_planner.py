import json

import pytest

from agent import planner


_REAL_GET_API_KEY = planner._get_api_key


@pytest.fixture(autouse=True)
def api_key(monkeypatch):
    monkeypatch.setattr(planner, "_get_api_key", lambda: "test-key")


VALID_PLAN = {
    "goal": "find the bitcoin price",
    "steps": [
        {
            "step": 1,
            "tool": "web_search",
            "description": "Search bitcoin price",
            "parameters": {"query": "bitcoin price"},
            "critical": True,
        }
    ],
}


def test_get_api_key_reads_config(tmp_path, monkeypatch):
    config = tmp_path / "api_keys.json"
    config.write_text(json.dumps({"gemini_api_key": "abc"}), encoding="utf-8")
    monkeypatch.setattr(planner, "API_CONFIG_PATH", config)
    assert _REAL_GET_API_KEY() == "abc"


def test_create_plan_returns_parsed_plan(fake_genai):
    fake_genai.response = json.dumps(VALID_PLAN)
    plan = planner.create_plan("find the bitcoin price")
    assert plan == VALID_PLAN
    assert fake_genai.configured_keys == ["test-key"]
    assert fake_genai.models[0].kwargs["model_name"] == "gemini-2.5-flash-lite"


def test_create_plan_strips_markdown_fences(fake_genai):
    fake_genai.response = f"```json\n{json.dumps(VALID_PLAN)}\n```"
    assert planner.create_plan("find the bitcoin price") == VALID_PLAN


def test_create_plan_includes_context_in_prompt(fake_genai):
    fake_genai.response = json.dumps(VALID_PLAN)
    planner.create_plan("do the thing", context="user is Turkish")
    prompt = fake_genai.models[0].prompts[0]
    assert "Goal: do the thing" in prompt
    assert "Context: user is Turkish" in prompt


def test_create_plan_omits_context_when_empty(fake_genai):
    fake_genai.response = json.dumps(VALID_PLAN)
    planner.create_plan("do the thing")
    assert "Context:" not in fake_genai.models[0].prompts[0]


def test_create_plan_rewrites_generated_code_steps(fake_genai):
    fake_genai.response = json.dumps(
        {
            "goal": "g",
            "steps": [
                {
                    "step": 1,
                    "tool": "generated_code",
                    "description": "d" * 250,
                    "parameters": {"description": "x"},
                }
            ],
        }
    )
    step = planner.create_plan("g")["steps"][0]
    assert step["tool"] == "web_search"
    assert step["parameters"] == {"query": "d" * 200}


def test_create_plan_falls_back_on_invalid_json(fake_genai):
    fake_genai.response = "definitely not json"
    assert planner.create_plan("my goal") == planner._fallback_plan("my goal")


def test_create_plan_falls_back_on_invalid_structure(fake_genai):
    fake_genai.response = json.dumps({"goal": "g", "steps": "not a list"})
    assert planner.create_plan("my goal") == planner._fallback_plan("my goal")


def test_create_plan_falls_back_when_model_raises(fake_genai):
    fake_genai.response = RuntimeError("api down")
    assert planner.create_plan("my goal") == planner._fallback_plan("my goal")


def test_fallback_plan_shape():
    plan = planner._fallback_plan("my goal")
    assert plan["goal"] == "my goal"
    assert plan["steps"][0]["tool"] == "web_search"
    assert plan["steps"][0]["parameters"] == {"query": "my goal"}
    assert plan["steps"][0]["critical"] is True


def test_replan_summarizes_completed_steps(fake_genai):
    fake_genai.response = json.dumps(VALID_PLAN)
    plan = planner.replan(
        goal="research and save",
        completed_steps=[{"step": 1, "tool": "web_search"}],
        failed_step={"tool": "file_controller", "description": "save file"},
        error="permission denied",
    )
    assert plan == VALID_PLAN
    prompt = fake_genai.models[0].prompts[0]
    assert "Step 1 (web_search): DONE" in prompt
    assert "Failed step: [file_controller] save file" in prompt
    assert "permission denied" in prompt


def test_replan_marks_no_completed_steps(fake_genai):
    fake_genai.response = json.dumps(VALID_PLAN)
    planner.replan("goal", [], {"tool": "t", "description": "d"}, "err")
    assert "(none)" in fake_genai.models[0].prompts[0]


def test_replan_rewrites_generated_code_steps(fake_genai):
    fake_genai.response = json.dumps(
        {
            "goal": "g",
            "steps": [
                {"step": 1, "tool": "generated_code", "description": "write a script"}
            ],
        }
    )
    step = planner.replan("g", [], {"tool": "t", "description": "d"}, "err")["steps"][0]
    assert step["tool"] == "web_search"
    assert step["parameters"] == {"query": "write a script"}


def test_replan_falls_back_on_error(fake_genai):
    fake_genai.response = RuntimeError("api down")
    plan = planner.replan("g", [], {"tool": "t", "description": "d"}, "err")
    assert plan == planner._fallback_plan("g")
