import subprocess
import sys
import threading
import types

import pytest

from agent import executor as ex
from agent.error_handler import ErrorDecision


@pytest.fixture(autouse=True)
def api_key(monkeypatch):
    monkeypatch.setattr(ex, "_get_api_key", lambda: "test-key")


def _recovery(decision, **extra):
    payload = {
        "decision": decision,
        "reason": "why",
        "fix_suggestion": "",
        "max_retries": 1,
        "user_message": "working on it, sir",
    }
    payload.update(extra)
    return payload


def _plan(*tools):
    return {
        "goal": "g",
        "steps": [
            {"step": i, "tool": tool, "description": f"do {tool}", "parameters": {}}
            for i, tool in enumerate(tools, 1)
        ],
    }


def test_inject_context_without_results():
    params = {"action": "write"}
    assert ex._inject_context(params, "file_controller", {}, goal="g") is params


def test_inject_context_ignores_other_tools():
    params = {"action": "write"}
    assert ex._inject_context(params, "web_search", {1: "x" * 200}, goal="g") == params


def test_inject_context_fills_empty_file_content(monkeypatch):
    monkeypatch.setattr(ex, "_translate_to_goal_language", lambda content, goal: f"TR:{content}")
    step_results = {1: "a" * 150, 2: "b" * 150, 3: "Done.", 4: "short"}
    params = ex._inject_context({"action": "write"}, "file_controller", step_results, goal="g")
    assert params["content"] == f"TR:{'a' * 150}\n\n---\n\n{'b' * 150}"


def test_inject_context_keeps_substantial_content(monkeypatch):
    monkeypatch.setattr(ex, "_translate_to_goal_language", lambda content, goal: "should not run")
    params = {"action": "write", "content": "c" * 60}
    assert ex._inject_context(params, "file_controller", {1: "x" * 200}, goal="g") == params


def test_inject_context_without_usable_results(monkeypatch):
    params = ex._inject_context({"action": "write"}, "file_controller", {1: "Done."}, goal="g")
    assert "content" not in params


def test_detect_language_returns_model_answer(fake_genai):
    fake_genai.response = " Turkish "
    assert ex._detect_language("merhaba") == "Turkish"


def test_detect_language_defaults_to_english(fake_genai):
    fake_genai.response = RuntimeError("api down")
    assert ex._detect_language("merhaba") == "English"


def test_translate_to_goal_language(fake_genai, monkeypatch):
    monkeypatch.setattr(ex, "_detect_language", lambda goal: "Turkish")
    fake_genai.response = " merhaba "
    assert ex._translate_to_goal_language("hello", "selam ver") == "merhaba"
    assert "Translate the following text into Turkish" in fake_genai.models[0].prompts[0]


def test_translate_without_goal_is_a_noop():
    assert ex._translate_to_goal_language("hello", "") == "hello"


def test_translate_returns_original_on_error(fake_genai, monkeypatch):
    monkeypatch.setattr(ex, "_detect_language", lambda goal: "Turkish")
    fake_genai.response = RuntimeError("api down")
    assert ex._translate_to_goal_language("hello", "goal") == "hello"


def test_run_generated_code_returns_stdout(fake_genai, monkeypatch):
    fake_genai.response = "```python\nprint('hi')\n```"
    spoken = []
    monkeypatch.setattr(
        ex.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args, 0, stdout=" hi \n", stderr=""),
    )
    assert ex._run_generated_code("say hi", speak=spoken.append) == "hi"
    assert spoken == ["Writing custom code for this task, sir."]


def test_run_generated_code_without_output(fake_genai, monkeypatch):
    fake_genai.response = "pass"
    monkeypatch.setattr(
        ex.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args, 0, stdout="", stderr=""),
    )
    assert ex._run_generated_code("do nothing") == "Task completed successfully."


def test_run_generated_code_raises_on_stderr(fake_genai, monkeypatch):
    fake_genai.response = "raise SystemExit(1)"
    monkeypatch.setattr(
        ex.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args, 1, stdout="", stderr="Traceback"),
    )
    with pytest.raises(RuntimeError, match="Code error: Traceback"):
        ex._run_generated_code("break things")


def test_run_generated_code_handles_timeout(fake_genai, monkeypatch):
    fake_genai.response = "while True: pass"
    def boom(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="python", timeout=120)

    monkeypatch.setattr(ex.subprocess, "run", boom)
    with pytest.raises(RuntimeError, match="timed out after 120 seconds"):
        ex._run_generated_code("loop forever")


def test_run_generated_code_wraps_model_failure(fake_genai):
    fake_genai.response = ValueError("api down")
    with pytest.raises(RuntimeError, match="Generated code failed: api down"):
        ex._run_generated_code("anything")


def test_run_generated_code_propagates_runtime_errors(fake_genai):
    fake_genai.response = RuntimeError("api down")
    with pytest.raises(RuntimeError, match="^api down$"):
        ex._run_generated_code("anything")


def test_call_tool_dispatches_to_action(monkeypatch):
    module = types.ModuleType("actions.open_app")
    calls = []

    def open_app(parameters, player=None):
        calls.append(parameters)
        return "opened"

    module.open_app = open_app
    monkeypatch.setitem(sys.modules, "actions.open_app", module)

    assert ex._call_tool("open_app", {"app_name": "notepad"}, None) == "opened"
    assert calls == [{"app_name": "notepad"}]


def test_call_tool_defaults_falsy_action_result(monkeypatch):
    module = types.ModuleType("actions.open_app")
    module.open_app = lambda parameters, player=None: ""
    monkeypatch.setitem(sys.modules, "actions.open_app", module)
    assert ex._call_tool("open_app", {}, None) == "Done."


def test_call_tool_screen_process_returns_fixed_message(monkeypatch):
    module = types.ModuleType("actions.screen_processor")
    module.screen_process = lambda parameters, player=None: None
    monkeypatch.setitem(sys.modules, "actions.screen_processor", module)
    assert ex._call_tool("screen_process", {"text": "what is this"}, None) == (
        "Screen captured and analyzed."
    )


def test_call_tool_generated_code_requires_description():
    with pytest.raises(ValueError, match="requires a 'description'"):
        ex._call_tool("generated_code", {}, None)


def test_call_tool_generated_code_runs_code(monkeypatch):
    monkeypatch.setattr(ex, "_run_generated_code", lambda description, speak=None: f"ran:{description}")
    assert ex._call_tool("generated_code", {"description": "sum 2+2"}, None) == "ran:sum 2+2"


def test_call_tool_unknown_tool_falls_back_to_generated_code(monkeypatch, capsys):
    monkeypatch.setattr(ex, "_run_generated_code", lambda description, speak=None: "fallback")
    assert ex._call_tool("does_not_exist", {"a": 1}, None) == "fallback"
    assert "Unknown tool" in capsys.readouterr().out


def test_execute_happy_path(monkeypatch):
    monkeypatch.setattr(ex, "create_plan", lambda goal: _plan("web_search"))
    monkeypatch.setattr(ex, "_call_tool", lambda tool, params, speak: "result")
    monkeypatch.setattr(ex.AgentExecutor, "_summarize", lambda self, goal, steps, speak: "summary")
    assert ex.AgentExecutor().execute("do it") == "summary"


def test_execute_without_steps(monkeypatch):
    monkeypatch.setattr(ex, "create_plan", lambda goal: {"goal": "g", "steps": []})
    spoken = []
    result = ex.AgentExecutor().execute("do it", speak=spoken.append)
    assert result == "I couldn't create a valid plan for this task, sir."
    assert spoken == [result]


def test_execute_honours_cancel_flag(monkeypatch):
    monkeypatch.setattr(ex, "create_plan", lambda goal: _plan("web_search"))
    flag = threading.Event()
    flag.set()
    spoken = []
    assert ex.AgentExecutor().execute("do it", speak=spoken.append, cancel_flag=flag) == (
        "Task cancelled."
    )
    assert spoken == ["Task cancelled, sir."]


def test_execute_retries_then_succeeds(monkeypatch):
    monkeypatch.setattr(ex, "create_plan", lambda goal: _plan("web_search"))
    monkeypatch.setattr(ex, "analyze_error", lambda step, error, attempt=1: _recovery(ErrorDecision.RETRY))
    monkeypatch.setattr("time.sleep", lambda seconds: None)

    attempts = {"n": 0}

    def flaky(tool, params, speak):
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise RuntimeError("transient")
        return "ok"

    monkeypatch.setattr(ex, "_call_tool", flaky)
    monkeypatch.setattr(ex.AgentExecutor, "_summarize", lambda self, goal, steps, speak: "summary")

    assert ex.AgentExecutor().execute("do it") == "summary"
    assert attempts["n"] == 2


def test_execute_skips_non_critical_failure(monkeypatch):
    monkeypatch.setattr(ex, "create_plan", lambda goal: _plan("web_search"))
    monkeypatch.setattr(ex, "analyze_error", lambda step, error, attempt=1: _recovery(ErrorDecision.SKIP))
    monkeypatch.setattr(
        ex, "_call_tool", lambda tool, params, speak: (_ for _ in ()).throw(RuntimeError("nope"))
    )
    captured = {}

    def summarize(self, goal, completed_steps, speak):
        captured["completed"] = completed_steps
        return "summary"

    monkeypatch.setattr(ex.AgentExecutor, "_summarize", summarize)

    assert ex.AgentExecutor().execute("do it") == "summary"
    assert len(captured["completed"]) == 1


def test_execute_aborts(monkeypatch):
    monkeypatch.setattr(ex, "create_plan", lambda goal: _plan("web_search"))
    monkeypatch.setattr(
        ex,
        "analyze_error",
        lambda step, error, attempt=1: _recovery(ErrorDecision.ABORT, reason="impossible"),
    )
    monkeypatch.setattr(
        ex, "_call_tool", lambda tool, params, speak: (_ for _ in ()).throw(RuntimeError("nope"))
    )
    spoken = []
    assert ex.AgentExecutor().execute("do it", speak=spoken.append) == "Task aborted, sir. impossible"
    assert "working on it, sir" in spoken


def test_execute_uses_generated_fix(monkeypatch):
    monkeypatch.setattr(ex, "create_plan", lambda goal: _plan("web_search"))
    monkeypatch.setattr(
        ex,
        "analyze_error",
        lambda step, error, attempt=1: _recovery(ErrorDecision.REPLAN, fix_suggestion="use code"),
    )
    monkeypatch.setattr(
        ex,
        "generate_fix",
        lambda step, error, suggestion: {"tool": "code_helper", "parameters": {"code": "print(1)"}},
    )

    def call_tool(tool, params, speak):
        if tool == "code_helper":
            return "fixed"
        raise RuntimeError("nope")

    monkeypatch.setattr(ex, "_call_tool", call_tool)
    monkeypatch.setattr(ex.AgentExecutor, "_summarize", lambda self, goal, steps, speak: "summary")

    assert ex.AgentExecutor().execute("do it") == "summary"


def test_execute_replans_until_limit(monkeypatch):
    replans = []
    monkeypatch.setattr(ex, "create_plan", lambda goal: _plan("web_search"))
    monkeypatch.setattr(
        ex, "replan", lambda goal, completed, failed, error: replans.append(failed) or _plan("web_search")
    )
    monkeypatch.setattr(ex, "analyze_error", lambda step, error, attempt=1: _recovery(ErrorDecision.REPLAN))
    monkeypatch.setattr(
        ex, "_call_tool", lambda tool, params, speak: (_ for _ in ()).throw(RuntimeError("nope"))
    )

    result = ex.AgentExecutor().execute("do it")
    assert result == "Task failed after 2 replan attempts, sir."
    assert len(replans) == ex.AgentExecutor.MAX_REPLAN_ATTEMPTS


def test_summarize_uses_model(fake_genai):
    fake_genai.response = " All done, sir. "
    spoken = []
    summary = ex.AgentExecutor()._summarize(
        "goal", [{"description": "searched the web"}], spoken.append
    )
    assert summary == "All done, sir."
    assert spoken == [summary]
    assert "searched the web" in fake_genai.models[0].prompts[0]


def test_summarize_falls_back_when_model_fails(fake_genai):
    fake_genai.response = RuntimeError("api down")
    spoken = []
    summary = ex.AgentExecutor()._summarize("goal", [{"description": "x"}], spoken.append)
    assert summary == "All done, sir. Completed 1 steps for: goal."
    assert spoken == [summary]
