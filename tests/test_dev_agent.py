from pathlib import Path
from unittest import mock

from actions import dev_agent as da


# --------------------------------------------------------------------------- #
# _classify_error / _has_error
# --------------------------------------------------------------------------- #

def test_classify_error_detects_dependency_error():
    assert da._classify_error("ModuleNotFoundError: No module named 'moviepy.editor'") == "dependency_error"


def test_classify_error_none_for_clean_output():
    assert da._classify_error("STDOUT:\nHello, world!\n") == "none"


def test_has_error_true_for_real_traceback_with_nonzero_exit():
    output = (
        "STDERR:\nTraceback (most recent call last):\n"
        "  File \"main.py\", line 3, in <module>\n"
        "ModuleNotFoundError: No module named 'moviepy.editor'"
    )
    assert da._has_error(output, "python main.py", returncode=1) is True


def test_has_error_false_when_process_exits_clean_despite_warning_text():
    """Regression test: a project that itself catches an optional-dependency
    ImportError, logs a WARNING, and keeps running (exit code 0) must NOT be
    treated as broken just because the log text contains 'no module named'."""
    output = (
        "STDERR:\n2026-08-17 12:51:21,075 - WARNING - moviepy or numpy not "
        "fully installed (No module named 'moviepy.editor'). Video and audio "
        "processing functions will be disabled."
    )
    assert da._has_error(output, "python main.py", returncode=0) is False


def test_has_error_true_for_traceback_even_with_clean_returncode():
    """Defensive: some frameworks print a traceback but still exit 0 —
    don't let that slip through just because the exit code looks clean."""
    output = "STDOUT:\nTraceback (most recent call last):\n  raise ValueError('bad')"
    assert da._has_error(output, "python main.py", returncode=0) is True


def test_has_error_falls_back_to_keyword_classification_without_returncode():
    """When returncode is unknown (e.g. timeout/FileNotFoundError paths),
    behavior should match the pre-existing keyword-based classification."""
    output = "ModuleNotFoundError: No module named 'requests'"
    assert da._has_error(output, "python main.py", returncode=None) is True


# --------------------------------------------------------------------------- #
# _run_project now returns (output, returncode)
# --------------------------------------------------------------------------- #

def test_run_project_returns_output_and_returncode(tmp_path):
    fake_result = mock.Mock(stdout="hello\n", stderr="", returncode=0)
    with mock.patch.object(da.subprocess, "run", return_value=fake_result):
        output, returncode = da._run_project("python main.py", tmp_path, timeout=5)
    assert "hello" in output
    assert returncode == 0


def test_run_project_timeout_returns_none_returncode(tmp_path):
    with mock.patch.object(da.subprocess, "run", side_effect=da.subprocess.TimeoutExpired(cmd="x", timeout=5)):
        output, returncode = da._run_project("python main.py", tmp_path, timeout=5)
    assert "Timed out" in output
    assert returncode is None


# --------------------------------------------------------------------------- #
# _try_auto_install: correct pip package names, not raw import names
# --------------------------------------------------------------------------- #

def test_auto_install_pins_moviepy_to_legacy_version(tmp_path):
    """Regression test for the exact bug: unpinned 'pip install moviepy'
    grabs 2.x, which removed the moviepy.editor submodule that generated
    code almost always imports from — guaranteeing every retry fails
    identically. Must install the last 1.x release instead."""
    error = "ModuleNotFoundError: No module named 'moviepy.editor'"
    fake_result = mock.Mock(returncode=0)
    with mock.patch.object(da.subprocess, "run", return_value=fake_result) as run:
        assert da._try_auto_install(error, tmp_path) is True
    installed_spec = run.call_args.args[0][-1]
    assert installed_spec == "moviepy==1.0.3"


def test_auto_install_maps_cv2_to_opencv_python(tmp_path):
    error = "ModuleNotFoundError: No module named 'cv2'"
    fake_result = mock.Mock(returncode=0)
    with mock.patch.object(da.subprocess, "run", return_value=fake_result) as run:
        da._try_auto_install(error, tmp_path)
    assert run.call_args.args[0][-1] == "opencv-python"


def test_auto_install_uses_bare_name_for_unmapped_packages(tmp_path):
    error = "ModuleNotFoundError: No module named 'requests'"
    fake_result = mock.Mock(returncode=0)
    with mock.patch.object(da.subprocess, "run", return_value=fake_result) as run:
        da._try_auto_install(error, tmp_path)
    assert run.call_args.args[0][-1] == "requests"


def test_auto_install_returns_false_when_no_module_error_present(tmp_path):
    with mock.patch.object(da.subprocess, "run") as run:
        assert da._try_auto_install("some other kind of error", tmp_path) is False
    run.assert_not_called()


# --------------------------------------------------------------------------- #
# _install_dependencies: correct the planner's bare dependency names too
# --------------------------------------------------------------------------- #

def test_install_dependencies_corrects_bare_moviepy_before_installing(tmp_path):
    not_installed = mock.Mock(returncode=1)
    install_ok = mock.Mock(returncode=0, stderr="")

    with mock.patch.object(da.subprocess, "run", side_effect=[not_installed, install_ok]) as run:
        da._install_dependencies(["moviepy"], tmp_path)

    install_call = run.call_args_list[-1]
    assert "moviepy==1.0.3" in install_call.args[0]


def test_install_dependencies_respects_planner_supplied_pin(tmp_path):
    """If the planner already pinned a version itself, don't override it."""
    not_installed = mock.Mock(returncode=1)
    install_ok = mock.Mock(returncode=0, stderr="")

    with mock.patch.object(da.subprocess, "run", side_effect=[not_installed, install_ok]) as run:
        da._install_dependencies(["moviepy==2.1.0"], tmp_path)

    install_call = run.call_args_list[-1]
    assert "moviepy==2.1.0" in install_call.args[0]
    assert "moviepy==1.0.3" not in install_call.args[0]
