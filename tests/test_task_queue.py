import threading
import time

import pytest

from agent import task_queue
from agent.task_queue import Task, TaskPriority, TaskQueue, TaskStatus


class FakeExecutor:
    """Records executions and optionally blocks or raises."""

    def __init__(self, result="done", error=None, delay=0.0):
        self.result = result
        self.error = error
        self.delay = delay
        self.calls: list[dict] = []

    def execute(self, goal, speak=None, cancel_flag=None):
        self.calls.append({"goal": goal, "speak": speak, "cancel_flag": cancel_flag})
        if self.delay:
            time.sleep(self.delay)
        if self.error:
            raise self.error
        return self.result


@pytest.fixture
def queue():
    q = TaskQueue()
    yield q
    q.stop()


def _wait_for(predicate, timeout=5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.02)
    return False


def test_task_ordering_is_by_priority_only():
    high = Task(priority=TaskPriority.HIGH.value, created_at=100.0, task_id="a", goal="a")
    low = Task(priority=TaskPriority.LOW.value, created_at=1.0, task_id="b", goal="b")
    assert high < low


def test_submit_orders_queue_by_priority_then_age(queue):
    first = queue.submit("normal first", TaskPriority.NORMAL)
    low = queue.submit("low", TaskPriority.LOW)
    high = queue.submit("high", TaskPriority.HIGH)
    second = queue.submit("normal second", TaskPriority.NORMAL)

    assert [t.task_id for t in queue._queue] == [high, first, second, low]
    assert queue.pending_count() == 4


def test_submit_defaults_to_normal_priority(queue):
    task_id = queue.submit("goal")
    assert queue._tasks[task_id].priority == TaskPriority.NORMAL.value
    assert queue._tasks[task_id].status is TaskStatus.PENDING


def test_get_status_returns_none_for_unknown_task(queue):
    assert queue.get_status("missing") is None


def test_get_status_reports_task_fields(queue):
    task_id = queue.submit("my goal")
    assert queue.get_status(task_id) == {
        "task_id": task_id,
        "goal": "my goal",
        "status": "pending",
        "result": None,
        "error": "",
    }


def test_get_all_statuses_truncates_goal(queue):
    queue.submit("g" * 80)
    statuses = queue.get_all_statuses()
    assert len(statuses) == 1
    assert statuses[0]["goal"] == "g" * 50


def test_cancel_marks_task_cancelled(queue):
    task_id = queue.submit("goal")
    assert queue.cancel(task_id) is True
    task = queue._tasks[task_id]
    assert task.status is TaskStatus.CANCELLED
    assert task.cancel_flag.is_set()
    assert queue.pending_count() == 0


def test_cancel_unknown_task(queue):
    assert queue.cancel("missing") is False


def test_cancel_finished_task_is_rejected(queue):
    task_id = queue.submit("goal")
    queue._tasks[task_id].status = TaskStatus.COMPLETED
    assert queue.cancel(task_id) is False


def test_next_task_respects_concurrency_limit(queue):
    queue.submit("goal")
    queue._active_count = queue._max_concurrent
    assert queue._next_task() is None


def test_next_task_skips_cancelled_tasks(queue):
    first = queue.submit("first")
    second = queue.submit("second")
    queue.cancel(first)
    assert queue._next_task().task_id == second


def test_get_executor_is_cached(queue, monkeypatch):
    executor = FakeExecutor()
    monkeypatch.setattr(queue, "_executor", executor)
    assert queue._get_executor() is executor
    assert queue._get_executor() is executor


def test_run_task_completes_and_invokes_callback(queue):
    executor = FakeExecutor(result="finished")
    queue._executor = executor
    seen = []
    task = Task(
        priority=TaskPriority.NORMAL.value,
        created_at=time.time(),
        task_id="t1",
        goal="do it",
        on_complete=lambda task_id, result, error: seen.append((task_id, result)),
    )
    queue._tasks["t1"] = task
    queue._active_count = 1

    queue._run_task(task)

    assert task.status is TaskStatus.COMPLETED
    assert task.result == "finished"
    assert queue._active_count == 0
    assert seen == [("t1", "finished")]
    assert executor.calls[0]["goal"] == "do it"


def test_run_task_records_failure(queue):
    queue._executor = FakeExecutor(error=RuntimeError("kaboom"))
    task = Task(
        priority=TaskPriority.NORMAL.value,
        created_at=time.time(),
        task_id="t2",
        goal="do it",
    )
    queue._active_count = 1

    queue._run_task(task)

    assert task.status is TaskStatus.FAILED
    assert task.error == "kaboom"
    assert queue._active_count == 0


def test_run_task_marks_cancelled_task_and_skips_callback(queue):
    queue._executor = FakeExecutor()
    calls = []
    task = Task(
        priority=TaskPriority.NORMAL.value,
        created_at=time.time(),
        task_id="t3",
        goal="do it",
        on_complete=lambda *args: calls.append(args),
    )
    task.cancel_flag.set()
    queue._active_count = 1

    queue._run_task(task)

    assert task.status is TaskStatus.CANCELLED
    assert calls == []


def test_run_task_swallows_callback_errors(queue, capsys):
    queue._executor = FakeExecutor()

    def boom(task_id, result):
        raise ValueError("callback broke")

    task = Task(
        priority=TaskPriority.NORMAL.value,
        created_at=time.time(),
        task_id="t4",
        goal="do it",
        on_complete=boom,
    )
    queue._active_count = 1

    queue._run_task(task)

    assert task.status is TaskStatus.COMPLETED
    assert "on_complete callback error" in capsys.readouterr().out


def test_worker_loop_runs_submitted_task(queue):
    executor = FakeExecutor()
    queue._executor = executor
    queue.start()
    queue.start()  # second call is a no-op
    task_id = queue.submit("run me")

    assert _wait_for(lambda: queue._tasks[task_id].status is TaskStatus.COMPLETED)
    assert executor.calls[0]["goal"] == "run me"
    assert queue.pending_count() == 0


def test_stop_halts_worker_thread(queue):
    queue._executor = FakeExecutor()
    queue.start()
    worker = queue._worker_thread
    queue.stop()
    worker.join(timeout=5)
    assert not worker.is_alive()


def test_get_queue_starts_singleton_once(monkeypatch):
    started = []
    monkeypatch.setattr(task_queue, "_queue_started", False)
    monkeypatch.setattr(task_queue._queue, "start", lambda: started.append(1))

    assert task_queue.get_queue() is task_queue._queue
    assert task_queue.get_queue() is task_queue._queue
    assert started == [1]


def test_task_cancel_flag_defaults_to_unset_event():
    task = Task(priority=1, created_at=0.0, task_id="x", goal="g")
    assert isinstance(task.cancel_flag, threading.Event)
    assert not task.cancel_flag.is_set()
