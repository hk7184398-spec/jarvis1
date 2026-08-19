"""
JARVIS Executor
Handles task execution, scheduling, and async operations
"""

import asyncio
import threading
from typing import Callable, Optional, Any, List
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum


class TaskStatus(Enum):
    """Task execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Task:
    """Represents an executable task."""
    id: str
    name: str
    func: Callable
    args: tuple = ()
    kwargs: dict = None
    status: TaskStatus = TaskStatus.PENDING
    result: Any = None
    error: Optional[str] = None
    created_at: datetime = None
    completed_at: Optional[datetime] = None
    
    def __post_init__(self):
        if self.kwargs is None:
            self.kwargs = {}
        if self.created_at is None:
            self.created_at = datetime.now()


class JARVISExecutor:
    """Manages task execution and scheduling."""
    
    def __init__(self, max_workers: int = 4):
        self.max_workers = max_workers
        self.tasks: dict[str, Task] = {}
        self.task_queue: List[Task] = []
        self.running = False
        self.executor_thread: Optional[threading.Thread] = None
    
    def execute_sync(self, task: Task) -> Any:
        """Execute a task synchronously."""
        try:
            task.status = TaskStatus.RUNNING
            result = task.func(*task.args, **task.kwargs)
            task.result = result
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now()
            return result
        except Exception as e:
            task.error = str(e)
            task.status = TaskStatus.FAILED
            task.completed_at = datetime.now()
            raise
    
    async def execute_async(self, task: Task) -> Any:
        """Execute a task asynchronously."""
        try:
            task.status = TaskStatus.RUNNING
            if asyncio.iscoroutinefunction(task.func):
                result = await task.func(*task.args, **task.kwargs)
            else:
                result = task.func(*task.args, **task.kwargs)
            task.result = result
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now()
            return result
        except Exception as e:
            task.error = str(e)
            task.status = TaskStatus.FAILED
            task.completed_at = datetime.now()
            raise
    
    def submit_task(self, task: Task) -> str:
        """Submit a task for execution."""
        self.tasks[task.id] = task
        self.task_queue.append(task)
        return task.id
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """Get a task by ID."""
        return self.tasks.get(task_id)
    
    def cancel_task(self, task_id: str) -> bool:
        """Cancel a pending task."""
        task = self.tasks.get(task_id)
        if task and task.status == TaskStatus.PENDING:
            task.status = TaskStatus.CANCELLED
            return True
        return False
    
    def start(self) -> None:
        """Start the executor."""
        if self.running:
            return
        self.running = True
        self.executor_thread = threading.Thread(target=self._process_queue, daemon=True)
        self.executor_thread.start()
    
    def stop(self) -> None:
        """Stop the executor."""
        self.running = False
    
    def _process_queue(self) -> None:
        """Process tasks from the queue."""
        while self.running:
            if self.task_queue:
                task = self.task_queue.pop(0)
                try:
                    self.execute_sync(task)
                except Exception:
                    pass
            else:
                threading.Event().wait(0.1)
    
    def get_status(self, task_id: str) -> Optional[TaskStatus]:
        """Get the status of a task."""
        task = self.tasks.get(task_id)
        return task.status if task else None


# Global executor instance
_executor = None


def get_executor() -> JARVISExecutor:
    """Get or create the global executor."""
    global _executor
    if _executor is None:
        _executor = JARVISExecutor()
        _executor.start()
    return _executor
