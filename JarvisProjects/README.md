# JARVIS Projects

This directory contains specialized JARVIS sub-projects and integrations.

## Project Structure

### Web Interface
- `jarvis1_web_interface/` - React/FastAPI web dashboard for JARVIS

### Automation Suites
- `tiktok_automation/` - TikTok video generation and posting pipeline
- `tiktok_automation_bot/` - Alternative TikTok bot implementation
- `Jarvis-Claude-Integration/` - Deep Claude API integration
- `Whatsapp_Automation/` - WhatsApp messaging and automation

### Specialized Integrations
- `jarvis_shopify_monitor_skill/` - Shopify store monitoring
- `velmora_project_manager/` - Project management integration

### Development & Output
- `logs/` - Logging directory for sub-projects
- `media/` - Media assets and outputs
- `output/` - Generated files and results
- `temp/` - Temporary working directory

## Running Sub-Projects

Each project should have its own README with setup and execution instructions.

### Quick Start
```bash
cd jarvis1_web_interface
python -m uvicorn app:app --reload

# Or start TikTok automation
cd ../tiktok_automation
python main.py
```

## Configuration
- Each project inherits config from parent JARVIS instance
- API keys should be referenced from main config/api_keys.json
- Logs are centralized in the parent logs/ directory
