# Facebook Posting Implementation Checklist for Jarvis1

## ✅ Completion Roadmap

### Phase 1: Setup & Configuration (One-time)
- [ ] Go to https://developers.facebook.com/apps
- [ ] Create Meta Business App
- [ ] Add "Facebook Login" product
- [ ] Add "Pages API" product
- [ ] Generate Long-Lived Page Access Token (60-day validity)
- [ ] Store credentials in `config/api_keys.json`:
  ```json
  {
    "fb_page_id": "YOUR_PAGE_ID",
    "fb_page_access_token": "EAABs...",
    "fb_app_id": "YOUR_APP_ID",
    "fb_app_secret": "YOUR_APP_SECRET"
  }
  ```

### Phase 2: Code Integration
- [ ] Replace `actions/facebook_poster.py` with `facebook_poster_improved.py`
- [ ] Update `facebook.md` with new documentation
- [ ] Verify imports in `facebook_poster.py`:
  - [ ] `from core.config import get_facebook_page_access_token, get_facebook_page_id`
  - [ ] `from core.files import atomic_write_text, restrict_permissions`
  - [ ] `from core.paths import BASE_DIR`
  - [ ] Selenium WebDriver (for browser automation fallback)
  - [ ] requests library (for Graph API)
  - [ ] Gemini API (for caption generation)

- [ ] Ensure `core/config.py` has these helper functions:
  ```python
  def get_facebook_page_id(required: bool = True) -> str:
      return get_api_key("fb_page_id", required=required)
  
  def get_facebook_page_access_token(required: bool = True) -> str:
      return get_api_key("fb_page_access_token", required=required)
  ```

- [ ] Ensure `memory/facebook_posts.json` can be created (directory exists)

### Phase 3: Test Facebook API
- [ ] Test text post:
  ```python
  from actions.facebook_poster import facebook_post
  
  result = facebook_post({
      "post_type": "text",
      "page_name": "Velmora",
      "text_content": "Welcome to Velmora! #Velmora #BestDeals"
  })
  print(result)
  ```

- [ ] Test photo post:
  ```python
  result = facebook_post({
      "post_type": "photo",
      "page_name": "Velmora",
      "media_path": "/path/to/photo.jpg"
  })
  print(result)
  ```

- [ ] Test video post:
  ```python
  result = facebook_post({
      "post_type": "video",
      "page_name": "Velmora",
      "media_path": "/path/to/video.mp4"
  })
  print(result)
  ```

- [ ] Verify posts appear on Facebook page immediately
- [ ] Check `memory/facebook_posts.json` for database entry
- [ ] Verify success report is accurate with real post_id

### Phase 4: Voice Command Integration
- [ ] Add Facebook posting to voice command handler (wherever JARVIS processes voice)
- [ ] Register trigger phrases:
  ```
  "Velmora par text post kar"
  "Wellmora page par photo upload karo"
  "Velmora par video post schedule kar"
  "Facebook par post karo"
  ```

- [ ] Implement voice command parsing:
  ```python
  # Example in main voice handler
  if "facebook" in command.lower() or "velmora" in command.lower():
      from actions.facebook_poster import facebook_post
      
      # Extract page name, type, content if provided
      page_name = extract_page_name(command)  # "Velmora", "Wellmora", etc.
      
      # Call facebook_post with parameters
      result = facebook_post(
          {
              "page_name": page_name,
              # post_type, text_content, media_path will be asked interactively
          },
          player=your_player_instance,  # For UI logging
          speak=your_speak_function      # For voice feedback
      )
      
      return result
  ```

### Phase 5: Browser Automation Fallback (Optional but Recommended)
- [ ] Install Selenium:
  ```bash
  pip install selenium --break-system-packages
  ```

- [ ] Install ChromeDriver or use webdriver-manager:
  ```bash
  pip install webdriver-manager --break-system-packages
  ```

- [ ] Update browser automation code in `facebook_poster.py` to use webdriver-manager:
  ```python
  from webdriver_manager.chrome import ChromeDriverManager
  from selenium.webdriver.chrome.service import Service
  
  service = Service(ChromeDriverManager().install())
  driver = webdriver.Chrome(service=service, options=options)
  ```

- [ ] Test browser fallback manually (simulate API failure)
- [ ] Ensure user is logged into Facebook in browser before relying on fallback

### Phase 6: Testing All Workflows

#### Test Scenario 1: Interactive Text Post
```
Command: "Velmora page par text post kar"
Jarvis asks: "کیا آپ text post کریں گے، photo post، یا video post؟"
User: "text"
Jarvis asks: "براہ کرم متن لکھیں"
User: "Welcome to Velmora!"
Jarvis: Auto-generates hashtags, posts via API, returns success
```
- [ ] Confirm text appears on Facebook
- [ ] Confirm hashtags are included
- [ ] Confirm database entry exists

#### Test Scenario 2: Photo Post with File Path
```
Command: "Velmora par photo post kar — /home/user/product.jpg"
Jarvis: Validates file, generates caption, posts via API, returns success
```
- [ ] Confirm photo appears on Facebook
- [ ] Confirm caption + hashtags are correct
- [ ] Confirm database entry exists with file_hash

#### Test Scenario 3: Duplicate Prevention
```
Command: "Velmora par photo post kar — /home/user/product.jpg" (repeat)
Jarvis: Detects duplicate (same file_hash + page), asks "force post?"
```
- [ ] Confirm duplicate check works
- [ ] Confirm force override works

#### Test Scenario 4: Scheduled Post
```
Command: "Velmora par kal 7 baje text post schedule kar — Welcome!"
Jarvis: Parses time, schedules post, returns success with scheduled_time
```
- [ ] Confirm post is scheduled (not published immediately)
- [ ] Confirm scheduled_publish_time is set correctly
- [ ] Manually check Facebook Scheduler to verify

#### Test Scenario 5: API Failure → Browser Fallback
```
Manually break API (e.g., wrong token temporarily)
Command: "Velmora par text post kar"
Jarvis: Attempts API 3 times, then opens browser automation
User: (Already logged in to Facebook)
Result: Post via browser, returns success with browser_automation method
```
- [ ] Confirm fallback triggers after 3 API failures
- [ ] Confirm browser automation successfully posts
- [ ] Confirm database logs publish_method="browser_automation"

### Phase 7: Voice Feedback & Logging

- [ ] Implement `speak` callback (voice output):
  ```python
  def speak(message: str):
      # Use TTS library (Google, Festival, etc.)
      # Play audio to speaker
      pass
  ```

- [ ] Implement `player.write_log()` callback (UI logging):
  ```python
  class JarvisPlayer:
      def write_log(self, message: str):
          # Append to UI log, Obsidian note, or console
          pass
  ```

- [ ] Test that both voice and UI log receive success/failure messages
- [ ] Verify voice messages are in Urdu/Roman Urdu mix for user

### Phase 8: Documentation & Handoff

- [ ] Update Jarvis README with Facebook posting section
- [ ] Add example voice commands to docs:
  ```
  "Velmora par text post kar — Welcome to Velmora!"
  "Wellmora par photo upload karo — /home/user/new_product.jpg"
  "Velmora par video schedule kar — kal 7 baje — /home/user/demo.mp4"
  ```

- [ ] Document troubleshooting section (see facebook.md Section 28)
- [ ] Add database schema docs for facebook_posts.json
- [ ] Add credential setup instructions to `.env.example` or docs

### Phase 9: Monitoring & Maintenance

**Weekly:**
- [ ] Check `memory/facebook_posts.json` for recent posts
- [ ] Monitor API rate-limit headers
- [ ] Review any failed posts

**Monthly:**
- [ ] Rotate/refresh Page Access Token if approaching expiry
- [ ] Archive old posts database
- [ ] Analyze engagement metrics (likes, shares, comments)

**Quarterly:**
- [ ] Update viral hashtag pool based on trending topics
- [ ] Review caption generation quality, improve prompts if needed
- [ ] Test browser automation fallback (ensure UI hasn't changed)

---

## 📋 Key Files to Modify/Create

| File | Action | Status |
|------|--------|--------|
| `actions/facebook_poster.py` | Replace with improved version | ⏳ Ready to copy |
| `facebook.md` | Update with full workflow | ⏳ Ready to copy |
| `config/api_keys.json` | Add FB credentials | ⏳ Instruction only |
| `core/config.py` | Add FB helper functions | ⏳ Code snippet ready |
| `memory/facebook_posts.json` | Create (auto-generated) | ✅ Auto-created |

---

## 🧪 Quick Test Commands

Once integrated, test with these Python snippets:

### Test 1: API Connection
```python
from actions.facebook_poster import facebook_post

result = facebook_post({
    "post_type": "text",
    "page_name": "Velmora",
    "text_content": "Testing Jarvis Facebook integration!"
})
print(result)
```

### Test 2: Interactive Flow (with mock speaker)
```python
from actions.facebook_poster import facebook_post

def mock_speak(msg):
    print(f"[SPEAKER] {msg}")

result = facebook_post(
    {"page_name": "Velmora"},
    speak=mock_speak
)
print(result)
```

### Test 3: Check Database
```python
import json
from pathlib import Path
from core.paths import BASE_DIR

db_path = BASE_DIR / "memory" / "facebook_posts.json"
if db_path.exists():
    posts = json.loads(db_path.read_text())
    for post in posts[-3:]:  # Last 3 posts
        print(f"Post ID: {post['post_id']}, Type: {post['post_type']}, Status: {post['status']}")
```

### Test 4: Duplicate Check
```python
from actions.facebook_poster import facebook_post

# First post
result1 = facebook_post({
    "post_type": "photo",
    "media_path": "/path/to/photo.jpg"
})
print(f"First post: {result1}")

# Try same file again (should warn)
result2 = facebook_post({
    "post_type": "photo",
    "media_path": "/path/to/photo.jpg"
})
print(f"Second post (duplicate): {result2}")

# Force override
result3 = facebook_post({
    "post_type": "photo",
    "media_path": "/path/to/photo.jpg",
    "force": True
})
print(f"Force post: {result3}")
```

---

## ⚠️ Common Issues & Solutions

### Issue 1: "Module not found" (Selenium)
```
Solution: pip install selenium --break-system-packages
```

### Issue 2: "Invalid access token"
```
Solution: 
1. Go to https://developers.facebook.com/tools/explorer
2. Regenerate Long-Lived Page Access Token
3. Update config/api_keys.json with new token
4. Retry posting
```

### Issue 3: "Page ID not found"
```
Solution:
1. Open https://www.facebook.com/YOUR_PAGE
2. Look at URL: facebook.com/[PAGE_ID]/
3. Copy PAGE_ID
4. Update config/api_keys.json: "fb_page_id": "PAGE_ID"
5. Retry posting
```

### Issue 4: "File not found"
```
Solution:
1. Ensure file path is absolute (e.g., /home/user/photo.jpg)
2. Use .expanduser() for ~ paths
3. Check file permissions (must be readable by Jarvis process)
4. Try: Path(path).expanduser().resolve() to debug
```

### Issue 5: "Browser automation: element not found"
```
Solution:
1. Facebook UI may have changed
2. Try manual posting via facebook.com to verify UI
3. Update CSS selectors in browser automation code
4. Fallback to manual posting if UI is too different
```

---

## 🚀 Deployment Checklist (Before Going Live)

- [ ] All 5 test scenarios pass
- [ ] Voice commands recognized correctly
- [ ] Database logging working
- [ ] Success/failure messages clear and accurate
- [ ] No hardcoded credentials in code
- [ ] Credentials stored securely in config/api_keys.json (git-ignored)
- [ ] Browser fallback tested and working
- [ ] Rate limiting handled gracefully
- [ ] Duplicate prevention working
- [ ] Hashtags are viral and relevant
- [ ] Documentation updated
- [ ] Team members trained on voice commands
- [ ] Monitoring/logs setup for production

---

## 📞 Support & Troubleshooting

If something breaks:

1. **Check logs:**
   ```bash
   tail -f memory/facebook_posts.json  # See latest post attempts
   ```

2. **Test API directly:**
   ```bash
   curl -X POST https://graph.facebook.com/v19.0/{page-id}/feed \
     -d "message=Test" \
     -d "access_token=YOUR_TOKEN"
   ```

3. **Verify token:**
   ```bash
   curl https://graph.facebook.com/me?access_token=YOUR_TOKEN
   ```

4. **Check browser session:**
   - Manually open facebook.com in Chrome
   - Verify you're logged in
   - This is required for browser automation fallback

5. **Enable debug logging:**
   - Add verbose prints to facebook_poster.py
   - Check stderr for Selenium/requests errors

---

## 🎯 Success Criteria

Your implementation is successful when:

✅ User voice command: "Velmora par text post kar — Welcome!"
✅ Jarvis generates caption with hashtags
✅ Post appears on Facebook within 10 seconds
✅ Database entry created with real post_id
✅ User receives voice confirmation

✅ User says: "Velmora par photo upload karo"
✅ Jarvis asks for file path
✅ User provides: "/home/user/product.jpg"
✅ Photo appears on Facebook within 20 seconds (upload takes time)
✅ Viral hashtags automatically added

✅ User tries duplicate file
✅ Jarvis warns: "یہ فائل پہلے ہی post ہو چکی ہے"
✅ User can override with "force"

✅ API fails (simulated)
✅ Browser automation fallback triggers
✅ Post still published successfully

When all above work → **Live deployment ready!**
