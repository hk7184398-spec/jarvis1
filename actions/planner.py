"""
JARVIS Planner
Task planning, scheduling, and time management
"""

from typing import Optional, List, Dict
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum


class Priority(Enum):
    """Task priority levels."""
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    URGENT = 4


class TaskStatus(Enum):
    """Task status."""
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


@dataclass
class PlannerTask:
    """Represents a task in the planner."""
    id: str
    title: str
    description: str = ""
    priority: Priority = Priority.MEDIUM
    status: TaskStatus = TaskStatus.TODO
    due_date: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    tags: List[str] = field(default_factory=list)
    subtasks: List[str] = field(default_factory=list)


class Planner:
    """Manages tasks and planning."""
    
    def __init__(self):
        self.tasks: Dict[str, PlannerTask] = {}
        self.categories: Dict[str, List[str]] = {}
    
    def create_task(
        self,
        title: str,
        description: str = "",
        priority: Priority = Priority.MEDIUM,
        due_date: Optional[datetime] = None,
        tags: Optional[List[str]] = None
    ) -> PlannerTask:
        """Create a new task."""
        task_id = f"task_{datetime.now().timestamp()}"
        task = PlannerTask(
            id=task_id,
            title=title,
            description=description,
            priority=priority,
            due_date=due_date,
            tags=tags or []
        )
        self.tasks[task_id] = task
        return task
    
    def get_task(self, task_id: str) -> Optional[PlannerTask]:
        """Get a task by ID."""
        return self.tasks.get(task_id)
    
    def update_task_status(self, task_id: str, status: TaskStatus) -> bool:
        """Update a task's status."""
        task = self.tasks.get(task_id)
        if task:
            task.status = status
            if status == TaskStatus.COMPLETED:
                task.completed_at = datetime.now()
            return True
        return False
    
    def get_tasks_by_status(self, status: TaskStatus) -> List[PlannerTask]:
        """Get all tasks with a specific status."""
        return [t for t in self.tasks.values() if t.status == status]
    
    def get_tasks_by_priority(self, priority: Priority) -> List[PlannerTask]:
        """Get all tasks with a specific priority."""
        return [t for t in self.tasks.values() if t.priority == priority]
    
    def get_overdue_tasks(self) -> List[PlannerTask]:
        """Get all overdue tasks."""
        now = datetime.now()
        return [
            t for t in self.tasks.values()
            if t.due_date and t.due_date < now and t.status != TaskStatus.COMPLETED
        ]
    
    def get_upcoming_tasks(self, days: int = 7) -> List[PlannerTask]:
        """Get tasks due in the next N days."""
        now = datetime.now()
        cutoff = now + timedelta(days=days)
        
        return [
            t for t in self.tasks.values()
            if t.due_date and now <= t.due_date <= cutoff and t.status != TaskStatus.COMPLETED
        ]
    
    def add_subtask(self, task_id: str, subtask: str) -> bool:
        """Add a subtask to a task."""
        task = self.tasks.get(task_id)
        if task:
            task.subtasks.append(subtask)
            return True
        return False
    
    def add_tag(self, task_id: str, tag: str) -> bool:
        """Add a tag to a task."""
        task = self.tasks.get(task_id)
        if task:
            if tag not in task.tags:
                task.tags.append(tag)
            return True
        return False
    
    def get_tasks_by_tag(self, tag: str) -> List[PlannerTask]:
        """Get all tasks with a specific tag."""
        return [t for t in self.tasks.values() if tag in t.tags]
    
    def get_daily_summary(self, date: Optional[datetime] = None) -> Dict[str, any]:
        """Get a summary of tasks for a specific day."""
        if date is None:
            date = datetime.now()
        
        date_start = date.replace(hour=0, minute=0, second=0, microsecond=0)
        date_end = date_start + timedelta(days=1)
        
        tasks = [
            t for t in self.tasks.values()
            if t.due_date and date_start <= t.due_date < date_end
        ]
        
        return {
            "date": date.strftime("%Y-%m-%d"),
            "total_tasks": len(tasks),
            "completed": len([t for t in tasks if t.status == TaskStatus.COMPLETED]),
            "in_progress": len([t for t in tasks if t.status == TaskStatus.IN_PROGRESS]),
            "pending": len([t for t in tasks if t.status == TaskStatus.TODO]),
            "high_priority": len([t for t in tasks if t.priority == Priority.HIGH or t.priority == Priority.URGENT]),
            "tasks": tasks
        }
    
    def delete_task(self, task_id: str) -> bool:
        """Delete a task."""
        if task_id in self.tasks:
            del self.tasks[task_id]
            return True
        return False


# Global planner instance
_planner = None


def get_planner() -> Planner:
    """Get or create the global planner."""
    global _planner
    if _planner is None:
        _planner = Planner()
    return _planner
