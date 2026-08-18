# TikTok Automation Enhancement - Integration Guide

## Overview
This enhanced TikTok automation module adds direct Downloads folder video upload capability with auto-generated descriptions and hashtags using Claude API.

## Features Added

✅ **Direct Downloads Folder Integration**
- List all videos in Downloads folder
- Voice command: "Upload [video_name] to TikTok"
- Automatic video discovery

✅ **AI-Powered Content Generation**
- Claude API generates catchy descriptions
- Automated hashtag generation (10 trending hashtags)
- Urdu/English mixed content support

✅ **Seamless Upload Workflow**
- Ask for video name via voice
- Auto-generate content
- Direct upload to TikTok

✅ **Robust Error Handling & Logging**
- Detailed logging to `tiktok_automation.log`
- Fallback mechanisms
- Retry logic

## Installation Steps

### 1. Add Module to Jarvis1

```bash
# Copy the enhanced module to your Jarvis1 repo
cp tiktok_automation_enhanced.py /path/to/jarvis1/modules/automation/tiktok/
cp tiktok_config_example.json /path/to/jarvis1/config/tiktok_config.json
```

### 2. Update Dependencies

Add to `requirements.txt`:
```
selenium>=4.0.0
anthropic>=0.25.0
python-dotenv>=1.0.0
```

Install:
```bash
pip install -r requirements.txt
```

### 3. Configure Credentials

Edit `config/tiktok_config.json`:
```json
{
  "tiktok_username": "your_username",
  "tiktok_password": "your_password",
  "anthropic_api_key": "sk-ant-...",
  "auto_hashtags": true,
  "hashtag_count": 10
}
```

### 4. Integration with Jarvis Core

Add to your Jarvis voice command handler (e.g., `jarvis_voice.py`):

```python
from modules.automation.tiktok import TikTokVoiceIntegration

class JarvisAssistant:
    def __init__(self):
        self.tiktok_handler = TikTokVoiceIntegration()
    
    def handle_voice_command(self, command):
        # TikTok commands
        if "list videos" in command.lower():
            return self.tiktok_handler.handle_list_videos_command()
        
        elif "upload" in command.lower() and "tiktok" in command.lower():
            # Extract video name from command
            # Example: "upload video.mp4 to tiktok"
            video_name = self._extract_video_name(command)
            if video_name:
                return self.tiktok_handler.handle_upload_command(video_name)
            else:
                return "Please provide the video filename. Example: 'Upload myvideo.mp4 to TikTok'"
        
        # ... other commands
```

### 5. Voice Command Examples

After integration, Jarvis will support:

```
"List videos in Downloads"
→ Shows available videos

"Upload video.mp4 to TikTok"
→ Asks for confirmation, then:
  • Finds video in Downloads
  • Generates description via Claude
  • Generates hashtags
  • Uploads and posts to TikTok

"Show me TikTok uploads"
→ Shows upload history and logs
```

## File Structure

```
jarvis1/
├── modules/
│   └── automation/
│       └── tiktok/
│           ├── tiktok_automation_enhanced.py    # Main module
│           └── __init__.py
├── config/
│   └── tiktok_config.json                       # Configuration
└── logs/
    └── tiktok_automation.log                    # Activity logs
```

## How It Works - Workflow Diagram

```
Voice Command: "Upload video.mp4 to TikTok"
        ↓
Jarvis voice handler receives command
        ↓
Extract video name from command
        ↓
TikTokVoiceIntegration.handle_upload_command()
        ↓
TikTokAutomation.list_downloads_videos()
        ↓
Find matching video file
        ↓
TikTokAutomation.generate_description_and_hashtags()
        ↓
Call Claude API with video name
        ↓
Claude generates description + hashtags
        ↓
TikTokAutomation.upload_to_tiktok_api()
        ↓
Selenium browser automation (fallback method)
        ↓
Open TikTok → Upload video → Add description → Add hashtags → Post
        ↓
Return success/failure status to voice assistant
```

## Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `tiktok_username` | string | - | Your TikTok username |
| `tiktok_password` | string | - | Your TikTok password |
| `anthropic_api_key` | string | - | Claude API key |
| `auto_hashtags` | bool | true | Auto-generate hashtags |
| `hashtag_count` | int | 10 | Number of hashtags to generate |
| `auto_description` | bool | true | Auto-generate description |
| `upload_method` | string | selenium | "selenium" or "api" |
| `max_retries` | int | 3 | Retry attempts on failure |

## Security Notes

⚠️ **DO NOT commit credentials to git!**
- Use environment variables or `.env` file
- Add `config/tiktok_config.json` to `.gitignore`
- Use GitHub Secrets for CI/CD deployments

### Secure Configuration Example

`.env` file:
```
TIKTOK_USERNAME=your_username
TIKTOK_PASSWORD=your_password
ANTHROPIC_API_KEY=sk-ant-...
```

Load in Python:
```python
import os
from dotenv import load_dotenv

load_dotenv()
config = {
    "tiktok_username": os.getenv("TIKTOK_USERNAME"),
    "tiktok_password": os.getenv("TIKTOK_PASSWORD"),
    "anthropic_api_key": os.getenv("ANTHROPIC_API_KEY")
}
```

## Logging

All activities are logged to `tiktok_automation.log`:

```
2026-08-18 14:23:45 - TikTok Automation - INFO - TikTok Automation initialized
2026-08-18 14:23:50 - TikTok Automation - INFO - Found 11 videos in Downloads
2026-08-18 14:24:01 - TikTok Automation - INFO - Generated description and hashtags for: video.mp4
2026-08-18 14:25:15 - TikTok Automation - INFO - Posted to TikTok successfully
```

## Troubleshooting

### Issue: "Video not found in Downloads"
- Check video filename matches exactly (case-sensitive)
- Verify video is in `C:\Users\YourUsername\Downloads` (Windows)
- List videos first with "List videos in Downloads"

### Issue: Selenium timeout
- Ensure TikTok website is accessible
- Check if Chrome/Chromium is installed
- Verify TikTok credentials are correct

### Issue: Claude API errors
- Verify API key is valid
- Check API rate limits
- Ensure anthropic package is updated

## Next Steps

1. **Rename to config.json** after adding credentials
2. **Test locally** with a sample video
3. **Push to GitHub** (remember to add config to .gitignore)
4. **Update Jarvis voice handler** to integrate commands
5. **Test with voice commands**

## GitHub Push Instructions

```bash
# After adding this module to your repo:

git add modules/automation/tiktok/
git add config/tiktok_config.json
git add TIKTOK_INTEGRATION_GUIDE.md

# Add config to gitignore
echo "config/tiktok_config.json" >> .gitignore

git commit -m "feat: Add enhanced TikTok automation with Downloads folder upload"
git push origin main
```

## Support & Debugging

Enable debug logging:
```python
logging.getLogger().setLevel(logging.DEBUG)
```

Check logs:
```bash
tail -f tiktok_automation.log
```

Test module directly:
```bash
python -m modules.automation.tiktok.tiktok_automation_enhanced
```
