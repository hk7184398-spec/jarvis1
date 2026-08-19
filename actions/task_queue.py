"""
JARVIS Task Queue
Distributed task queue for async job processing
"""

import json
import threading
import time
from typing import Callable, Optional, Any, Dict, List
from dataclasses import dataclass, asdict, field
from datetime import datetime
from enum import Enum
from pathlib import Path


class JobStatus(Enum):
    """Job status in queue."""
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"


class JobPriority(Enum):
    """Job priority for scheduling."""
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


@dataclass
class Job:
    """Represents a queued job."""
    id: str
    name: str
    func_name: str
    args: tuple = field(default_factory=tuple)
    kwargs: dict = field(default_factory=dict)
    status: str = JobStatus.PENDING.value
    priority: int = JobPriority.NORMAL.value
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    result: Any = None
    error: Optional[str] = None
    retries: int = 0
    max_retries: int = 3


class TaskQueue:
    """Manages a task queue for async job processing."""
    
    def __init__(self, num_workers: int = 2, queue_dir: str = "task_queue"):
        self.num_workers = num_workers
        self.queue_dir = Path(queue_dir)
        self.queue_dir.mkdir(exist_ok=True)
        
        self.jobs: Dict[str, Job] = {}
        self.queue: List[str] = []  # Job IDs
        self.workers: List[threading.Thread] = []
        self.running = False
        self.func_registry: Dict[str, Callable] = {}
        self.lock = threading.Lock()
    
    def register_function(self, name: str, func: Callable) -> None:
        """Register a function that can be queued."""
        self.func_registry[name] = func
    
    def enqueue(
        self,
        func_name: str,
        job_name: str,
        args: tuple = (),
        kwargs: dict = None,
        priority: JobPriority = JobPriority.NORMAL,
        max_retries: int = 3
    ) -> str:
        """
        Enqueue a job.
        
        Args:
            func_name: Name of registered function to call
            job_name: Human-readable job name
            args: Function positional arguments
            kwargs: Function keyword arguments
            priority: Job priority
            max_retries: Maximum retries on failure
        
        Returns:
            Job ID
        """
        if kwargs is None:
            kwargs = {}
        
        job_id = f"job_{datetime.now().timestamp()}_{len(self.jobs)}"
        job = Job(
            id=job_id,
            name=job_name,
            func_name=func_name,
            args=args,
            kwargs=kwargs,
            priority=priority.value,
            max_retries=max_retries
        )
        
        with self.lock:
            self.jobs[job_id] = job
            self.queue.append(job_id)
            self._sort_queue()
            self._persist_job(job)
        
        return job_id
    
    def get_job(self, job_id: str) -> Optional[Job]:
        """Get job details."""
        return self.jobs.get(job_id)
    
    def get_jobs_by_status(self, status: JobStatus) -> List[Job]:
        """Get all jobs with a specific status."""
        return [j for j in self.jobs.values() if j.status == status.value]
    
    def cancel_job(self, job_id: str) -> bool:
        """Cancel a pending job."""
        job = self.jobs.get(job_id)
        if job and job.status == JobStatus.PENDING.value:
            job.status = JobStatus.CANCELLED.value
            if job_id in self.queue:
                self.queue.remove(job_id)
            return True
        return False
    
    def start(self) -> None:
        """Start processing jobs."""
        if self.running:
            return
        
        self.running = True
        for i in range(self.num_workers):
            worker = threading.Thread(
                target=self._worker_loop,
                name=f"TaskQueueWorker-{i}",
                daemon=True
            )
            worker.start()
            self.workers.append(worker)
    
    def stop(self) -> None:
        """Stop processing jobs."""
        self.running = False
    
    def _worker_loop(self) -> None:
        """Worker thread main loop."""
        while self.running:
            job_id = self._get_next_job()
            if not job_id:
                time.sleep(0.5)
                continue
            
            job = self.jobs[job_id]
            self._execute_job(job)
    
    def _get_next_job(self) -> Optional[str]:
        """Get next job from queue."""
        with self.lock:
            if self.queue:
                job_id = self.queue.pop(0)
                return job_id
        return None
    
    def _execute_job(self, job: Job) -> None:
        """Execute a job."""
        func = self.func_registry.get(job.func_name)
        if not func:
            job.status = JobStatus.FAILED.value
            job.error = f"Function not found: {job.func_name}"
            self._persist_job(job)
            return
        
        job.status = JobStatus.RUNNING.value
        job.started_at = datetime.now().isoformat()
        
        try:
            result = func(*job.args, **job.kwargs)
            job.result = result
            job.status = JobStatus.COMPLETED.value
            job.completed_at = datetime.now().isoformat()
        except Exception as e:
            job.error = str(e)
            job.retries += 1
            
            if job.retries < job.max_retries:
                job.status = JobStatus.RETRYING.value
                with self.lock:
                    self.queue.append(job.id)
            else:
                job.status = JobStatus.FAILED.value
                job.completed_at = datetime.now().isoformat()
        
        self._persist_job(job)
    
    def _sort_queue(self) -> None:
        """Sort queue by priority."""
        self.queue.sort(
            key=lambda jid: self.jobs[jid].priority if jid in self.jobs else 0,
            reverse=True
        )
    
    def _persist_job(self, job: Job) -> None:
        """Persist job to disk."""
        job_file = self.queue_dir / f"{job.id}.json"
        with open(job_file, 'w') as f:
            json.dump(asdict(job), f, indent=2, default=str)
    
    def load_jobs(self) -> None:
        """Load jobs from disk."""
        for job_file in self.queue_dir.glob("*.json"):
            try:
                with open(job_file, 'r') as f:
                    data = json.load(f)
                    job = Job(**data)
                    self.jobs[job.id] = job
                    if job.status == JobStatus.PENDING.value:
                        self.queue.append(job.id)
            except Exception:
                pass
        
        self._sort_queue()


# Global task queue instance
_queue = None


def get_task_queue(num_workers: int = 2) -> TaskQueue:
    """Get or create the global task queue."""
    global _queue
    if _queue is None:
        _queue = TaskQueue(num_workers=num_workers)
    return _queue
