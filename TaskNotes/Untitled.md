# JARVIS Development Notes

## Current Work

### Action Modules
- ✅ attention_monitor.py - Windows notification listener
- ✅ docx_tools.py - Word document generation
- ✅ error_handler.py - Centralized error handling
- ✅ executor.py - Task execution and scheduling
- ✅ meeting_assistant.py - Meeting/call management
- ✅ office_builder.py - Office document automation
- ✅ pdf_tools.py - PDF manipulation
- ✅ planner.py - Task planning
- ✅ ppt_template_workflow.py - PowerPoint automation
- ✅ task_queue.py - Async job queue

### Recent Fixes
- GitHub push: consolidated modified files and removed junk directories
- Line ending (CRLF/LF) configuration
- Submodule handling for mcp-obsidian

## Next Steps
1. Integrate new action modules into main.py
2. Test action module imports and core functionality
3. Add routing rules to core/prompt.txt for new tools
4. Extend TOOL_DECLARATIONS for new actions
5. Update SKILLS_REGISTRY.md with new capabilities

## Notes
- Prefer async execution for I/O-bound tasks
- Keep API keys in config/api_keys.json (never in code)
- Use error_handler for all exception handling
- Register functions with task_queue for background jobs
