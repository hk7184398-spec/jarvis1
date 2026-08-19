# JARVIS Files Restoration Guide

## Files Restored

### Action Modules (9 files)
```
actions/
├── attention_monitor.py      # Windows notification listener for calls/messages
├── docx_tools.py            # Word document generation and manipulation
├── error_handler.py         # Centralized error handling and logging
├── executor.py              # Task execution and async scheduling
├── meeting_assistant.py     # Meeting scheduling and management
├── office_builder.py        # Excel, Word, PowerPoint automation
├── pdf_tools.py             # PDF creation, extraction, merging
├── planner.py               # Task planning and time management
├── ppt_template_workflow.py # PowerPoint template-based automation
└── task_queue.py            # Async job queue and worker management
```

### Documentation & Notes
```
TaskNotes/
├── Smc strategy ea.md       # SMC Expert Advisor trading strategy notes
└── Untitled.md              # Development notes and TODOs

JarvisProjects/
└── README.md                # Overview of sub-projects structure
```

## Integration Steps

### 1. Extract Files
**Windows PowerShell:**
```powershell
cd C:\Users\Dani\Downloads\jarvis1
tar -xzf jarvis_restored_files.tar.gz
```

### 2. Verify Structure
```powershell
git status  # Should show new untracked files
```

### 3. Add & Commit
```powershell
git add actions/
git add TaskNotes/
git add JarvisProjects/
git commit -m "Restore: re-add action modules and project files

- AttentionMonitor: Windows notification listener
- Document tools: docx, pdf, ppt automation
- Task management: executor, planner, task_queue
- Meeting assistant and office builders
- Project documentation and notes"

git push
```

## Integration with main.py

### 4. Import New Action Modules (Optional)
Edit `main.py` to import and register new actions:

```python
from actions.attention_monitor import AttentionMonitor
from actions.error_handler import get_error_handler
from actions.executor import get_executor, Task
from actions.planner import get_planner, Priority, TaskStatus
from actions.task_queue import get_task_queue, JobPriority

# In your JARVIS init:
self.attention_monitor = AttentionMonitor(on_event=self._handle_notification)
self.error_handler = get_error_handler()
self.executor = get_executor()
self.planner = get_planner()
self.task_queue = get_task_queue()
```

### 5. Add Tool Declarations (Optional)
Update `core/prompt.txt` with new tools:

```
TOOL DECLARATIONS:
...
- attention_monitor: Listen to system notifications from messaging apps
- task_queue: Queue and execute long-running jobs
- planner: Create and manage tasks with priorities and deadlines
- error_handler: Log errors and attempt recovery strategies
...
```

### 6. Extend Tool Routing (Optional)
In `core/agent.py` or wherever tools are executed:

```python
elif name == "queue_job":
    queue = get_task_queue()
    queue.register_function(args['func_name'], args['func'])
    job_id = queue.enqueue(...)
    return job_id

elif name == "check_notifications":
    monitor = AttentionMonitor()
    monitor.start()
    # Process events...
```

## Next Steps
1. ✅ Extract and git add files
2. ✅ Commit and push to GitHub
3. ( ) Import modules in main.py (optional, on-demand)
4. ( ) Add TOOL_DECLARATIONS to core/prompt.txt
5. ( ) Integrate routing in core/agent.py
6. ( ) Add tests for new action modules

## Notes
- All modules follow JARVIS conventions (singleton pattern, global getter functions)
- Error handling is built-in via error_handler.py
- Each module is independent and can be used standalone
- Task queue is persistent (saves to disk, can recover from crashes)
- Planner supports priorities, tags, subtasks, and due dates

## Troubleshooting

**Import errors**: Install dependencies
```bash
pip install python-docx openpyxl python-pptx PyPDF2 reportlab
```

**Task queue issues**: Check `task_queue/` directory for persisted job files

**Notification monitor (Windows only)**: Requires pyautogui, pywinauto, psutil
```bash
pip install pyautogui pywinauto psutil edge-tts
```