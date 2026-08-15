# Facebook Page Management Guide for Jarvis

## Overview
Complete automation for posting text, photo, and video to Facebook pages with interactive workflow, viral hashtags, and automatic error handling.

---

## 1. Facebook Login & Authentication
- **Prerequisite:** One-time setup of Meta App and credentials (Section 7)
- **Token used:** Long-lived Page Access Token (60 days validity, auto-refreshes)
- **For automated posting:** No manual login needed after initial setup
- **For browser automation fallback:** Assumes browser session is already logged in

---

## 2. Navigate to Page
- **Action:** Specify the exact Facebook Page name or ID (e.g., "Velmora", "Wellmora")
- **Automation:** Meta Graph API will directly post to the specified page
- **Browser fallback:** Navigate to page URL and select from dropdown

---

## 3. Create Post: Interactive Workflow (Section 4)

This is the **core workflow** triggered by voice command. Follow these steps sequentially:

### Step 3.1: Ask Post Type
**Jarvis asks:** "Sir, کیا آپ text post کریں گے، photo post، یا video post؟"
(Text, photo, or video?)

**User responds:** "text" or "photo" or "video"

### Step 3.2: Collect Input Based on Type

#### A) Text Post
- **Jarvis asks:** "Sir, براہ کرم وہ متن لکھیں جو آپ post کرنا چاہتے ہیں۔"
  (Please provide the text content)
- **User says/types:** "Welcome to Velmora, best online shopping!"
- **Jarvis action:** 
  - Take user's text
  - Auto-generate viral hashtags (3-5 hashtags)
  - Combine: `User text + hashtags`
  - Caption ready for posting

Example caption:
```
Welcome to Velmora, best online shopping!

#Velmora #VelmoraLife #BestDeals #OnlineShopping #ShopNow
```

#### B) Photo Post
- **Jarvis asks:** "Sir, براہ کرم اپنی photo file کا path فراہم کریں۔"
  (Please provide the photo file path)
- **User says/provides:** "/home/user/Pictures/product_photo.jpg"
- **Jarvis action:**
  - Validate file exists and is image format (.jpg, .png, .gif, etc.)
  - Check file hash to prevent duplicates (Section 8)
  - Auto-generate engaging caption + viral hashtags
  - Ready for upload

#### C) Video Post
- **Jarvis asks:** "Sir, براہ کرم اپنی video file کا path فراہم کریں۔"
  (Please provide the video file path)
- **User says/provides:** "/home/user/Videos/product_demo.mp4"
- **Jarvis action:**
  - Validate file exists and is video format (.mp4, .mov, .avi, etc.)
  - Check file hash to prevent duplicates (Section 8)
  - Optionally validate video specs (aspect ratio, duration, codec) — see Section 21
  - Auto-generate engaging caption + viral hashtags
  - Ready for upload

### Step 3.3: Caption & Hashtags

**For text posts:**
- Use user-provided text as-is
- Add auto-generated viral hashtags from the pool

**For media posts (photo/video):**
- AI-generate 2-3 sentence engaging caption using Gemini
- Append auto-generated viral hashtags

**Hashtag pool (context-aware):**
```
Velmora brand:  #Velmora #VelmoraLife #VelmoraQuality #BestDeals #OnlineShopping
E-commerce:     #Ecommerce #OnlineStore #Shopping #NewArrivals #SpecialOffer
Trending:       #TopTrending #MustSee #DontMiss #ShopNow #LimitedTime
```

### Step 3.4: Post Publishing

Two methods in priority order:

**Method 1: Meta Graph API (Recommended)**
- Direct, fast, reliable
- POST to /{page-id}/feed (text)
- POST to /{page-id}/photos (photo)
- POST to /{page-id}/videos (video)
- Returns real `post_id` on success (verified-execution principle)

**Method 2: Browser Automation (Fallback)**
- If API fails after 3 retries
- Selenium opens browser → facebook.com
- Navigates to page → "Create post" modal
- Fills caption text
- Uploads media file
- Clicks "Post" button
- Waits for confirmation
- Extracts post_id from URL or DOM

---

## 4. Voice Command Trigger (Natural Language Interface)

**Example voice commands:**

```
"Velmora page par text post karo — Welcome to Velmora"
"Wellmora par photo upload karo — /home/user/new_product.jpg"
"Velmora par video post schedule kar — tomorrow 7 PM — /videos/demo.mp4"
```

**Jarvis parsing & execution:**

1. **Extract intent:** Post to page + media type (if specified)
2. **Extract page name:** "Velmora", "Wellmora", etc. → resolve to page_id
3. **Extract scheduling:** "kal 7 baje" (tomorrow 7 PM) → UTC timestamp
4. **Interactive flow:**
   - If post type not mentioned: Ask "text, photo, or video?"
   - If content not provided: Ask for text/file path
   - Once all inputs collected: Proceed to posting (Section 3.4)
5. **Post & confirm:**
   - Use Meta Graph API first
   - Log to database (Section 8)
   - Send success/failure report (Section 9/10)

---

## 5. Media Source: Google Drive Integration (Optional)

If user mentions Google Drive location:

- **Action:** Jarvis authenticates with Google Drive (OAuth token, secure storage)
- **Process:**
  - List/locate file by name or "latest file in folder"
  - Download to temp location
  - Use temp file for posting (Section 3.4)
  - Delete temp file after successful post or 3 retries

Example:
```
"Velmora par Google Drive folder se photo post karo"
→ Jarvis downloads latest image from that folder
→ Posts to Facebook
→ Cleans up temp file
```

---

## 6. Posting via Meta Graph API

### 6.1: Text Post
```
POST https://graph.facebook.com/v19.0/{page-id}/feed
Parameters:
  - message: "Your caption text with hashtags"
  - access_token: (long-lived page token)
  - published: true/false
  - scheduled_publish_time: (Unix timestamp, optional)

Response:
  {
    "id": "123456789_987654321"  ← This is the post_id
  }
```

### 6.2: Photo Post
```
POST https://graph.facebook.com/v19.0/{page-id}/photos
Parameters:
  - source: (binary image file)
  - caption: "Your caption with hashtags"
  - access_token: (long-lived page token)
  - published: true/false
  - scheduled_publish_time: (Unix timestamp, optional)

Response:
  {
    "id": "123456789"  ← Photo ID (post_id derived from this)
  }
```

### 6.3: Video Post
```
POST https://graph-video.facebook.com/v19.0/{page-id}/videos
Parameters:
  - source: (binary video file)
  - description: "Your caption with hashtags"
  - access_token: (long-lived page token)
  - published: true/false
  - scheduled_publish_time: (Unix timestamp, optional)

Response:
  {
    "id": "123456789"  ← Video ID (post_id derived from this)
  }
```

### 6.4: Verified-Execution Principle
- **NO success report without post_id**
- If API returns status 200 but no `id` field → treat as failure
- Retry up to 3 times before fallback to browser automation

---

## 7. Meta Graph API — App Setup & Credential Generation

One-time setup (manual, not automated by Jarvis):

### Step 7.1: Create a Meta App
1. Go to `https://developers.facebook.com/apps`
2. Create new App → Type: **Business**
3. Add Products: **Facebook Login** + **Pages API**

### Step 7.2: Generate Long-Lived Page Access Token
1. Open `https://developers.facebook.com/tools/explorer`
2. Select your App (created in 7.1)
3. Request permissions: `pages_manage_posts`, `pages_read_engagement`, `pages_show_list`
4. Generate short-lived User Access Token
5. Exchange for Long-Lived User Token (valid 60 days)
6. Use that token to fetch Page's Long-Lived Page Access Token (never expires unless revoked)

### Step 7.3: Store Credentials
Add to `config/api_keys.json` (git-ignored, local-only):
```json
{
  "gemini_api_key": "...",
  "openrouter_api_key": "...",
  "fb_page_id": "123456789",
  "fb_page_access_token": "EAABs...",
  "fb_app_id": "...",
  "fb_app_secret": "..."
}
```

### Step 7.4: Jarvis Code Integration
- `core/config.py` includes helpers:
  - `get_facebook_page_id()`
  - `get_facebook_page_access_token()`
- `actions/facebook_poster.py` reads credentials via these helpers
- No hardcoded secrets in source or this guide

---

## 8. Database Update (Duplicate Prevention)

**Before posting:**
- Compute SHA256 hash of media file (for photo/video)
- Check database for same `file_hash` + `page_id` within last 24 hours
- If found: Warn user and ask "force post?" to override

**After successful post:**
- Store in `memory/facebook_posts.json`:
  ```json
  {
    "post_id": "123456789_987654321",
    "page_id": "123456789",
    "media_path": "/home/user/photo.jpg",
    "file_hash": "abc123...",
    "caption": "Welcome to Velmora...",
    "post_type": "photo",
    "scheduled_time": null,
    "published_time": "2026-08-15T19:30:45Z",
    "status": "success",
    "error": null,
    "publish_method": "api"
  }
  ```

**Purpose:** Prevent accidental duplicate posting of same file within 24 hours

---

## 9. Success Reporting

**Format:**
```
"Sir, آپ کی [post_type] post کامیابی سے [page_name] page پر publish ہو گئی!
Post ID: [post_id]
Caption: '[caption first 80 chars]'

Your [post_type] post has been published successfully on [page_name]."
```

**Channels:**
- Voice reply (via `speak()` callback)
- UI log (via `player.write_log()`)
- Console print
- Database entry with status="success"

**Example:**
```
"Sir, آپ کی photo post کامیابی سے Velmora page پر publish ہو گئی!
Post ID: 123456789_987654321
Caption: 'Welcome to Velmora, best online shopping! #Velmora #VelmoraLife...'

Your photo post has been published successfully on Velmora."
```

---

## 10. Failure Handling & Retry Logic

**Automatic retry:**
- Attempt 1: Immediate
- Attempt 2: Wait 30 seconds, retry
- Attempt 3: Wait 2 minutes, retry
- Attempt 4: Wait 5 minutes, retry
- After 3 failed API attempts: Fallback to browser automation (Section 24)

**Failure scenarios:**
- Network error → Retry automatically
- Graph API error (e.g., invalid token) → Log error, fallback to browser
- File not found → Immediate failure, ask user to provide correct path
- Duplicate detected → Ask user to override with "force post"

**Failure report:**
```
"Sir, آپ کی post publish نہیں ہو سکی۔
وجہ: [error message]
کیا آپ دوبارہ کوشش کریں گے؟

Your post failed to publish. Reason: [error]. Would you like to retry?"
```

**Database entry:**
- status: "failed"
- error: (detailed error message)
- publish_method: "api" or "browser_automation"

---

## 11. Rate Limiting & Quota

**Meta Graph API rate limits:**
- Per app: 200 requests per hour (for most endpoints)
- Per page: 30 posts per day (soft limit, varies by engagement)

**Jarvis handling:**
- Log rate-limit headers from API response
- Pause posting if 429 error (Too Many Requests) detected
- Notify user: "Sir, Facebook نے rate limit لگایا ہے۔ کچھ دیر بعد کوشش کریں۔"

---

## 12. Review Gate (Optional)

For high-value pages, allow caption review before posting:

**User preference:** `review_before_post = true/false`

If enabled:
1. Generate caption + hashtags
2. Show to user: "Sir, یہ caption ٹھیک ہے؟ ... [approve/edit/cancel]"
3. User can edit or approve
4. Proceed to posting

---

## 13. Media Processing & Validation (Section 21)

### Photo Pre-Upload Checks
- Format: .jpg, .png, .gif, .webp (only)
- Size: < 4 MB recommended
- Aspect ratio: Flexible (Facebook handles it)
- Resolution: Minimum 600x400px recommended

### Video Pre-Upload Checks
- Format: .mp4 (H.264), .mov, .avi, .webm, .mkv
- Size: < 4 GB
- Duration: 1 second to 120 minutes
- Aspect ratio: 4:5 (Reels), 16:9 (Feed), 1:1 (Stories)
- Resolution: 720p minimum, 4K recommended
- Frame rate: 23-60 fps
- **If specs don't match:** Auto-transcode using ffmpeg (same as TikTok pipeline)

---

## 14. Proof Screenshot (Optional)

After successful post, capture screenshot from Facebook showing:
- Post content (caption, media)
- Engagement metrics (likes, comments, shares)
- Timestamp of publishing

Save to `memory/facebook_posts_proofs/[post_id].jpg` for record-keeping.

---

## 15. Engagement Feedback Loop (Optional)

After posting, periodically check:
- Likes, comments, shares count
- Reach, impressions
- Best-performing content type (text vs photo vs video)
- Best posting times

Use this data to:
- Optimize future captions
- Pick best posting time (Section 18)
- Improve hashtag selection

---

## 16. Scheduled Posting

**User command:**
```
"Velmora par kal 7 baje photo post schedule kar — /home/user/photo.jpg"
```

**Jarvis parsing:**
- Extract page: "Velmora"
- Extract time: "kal 7 baje" → Tomorrow 7:00 PM (UAE timezone)
- Extract media: "/home/user/photo.jpg"

**Two scheduling strategies:**

### Strategy A: Meta Native Scheduling (Recommended)
- Use `scheduled_publish_time` parameter in Graph API
- Facebook handles the publishing at exact time
- More reliable (survives Jarvis restart)

### Strategy B: Jarvis-Side Scheduling
- Store post in local database with scheduled_time
- Background cron job checks every minute
- At scheduled time, execute posting
- Less reliable if Jarvis crashes

**Recommendation:** Use Strategy A (Meta native) for posts, Strategy B for recurring schedules

---

## 17. Auto-Pause on Repeated Failure (Safety)

**Trigger:** 2-3 consecutive failed posts on same page

**Action:**
- Pause all future posts for that page
- Notify user: "Sir, [page_name] پر posting روک دی گئی ہے۔ Token شاید expire ہو گیا۔"
- Ask user to confirm/fix before resuming
- Check token validity; auto-refresh if needed (Section 7.2)

---

## 18. Best-Time-to-Post Optimization (Optional)

If user doesn't specify scheduling time:

**Default behavior:** "Sir, براہ کرم وقت بھی بتائیں۔"
(Ask for time explicitly)

**Optional auto-select:**
- Pull historical engagement data (Section 15)
- Identify peak hours for that page
- Suggest: "Sir, اس page کے لیے 7 PM best time ہے۔ اسی وقت post کریں?"
- User approves or picks different time

---

## 19. A/B Caption Testing (Optional)

For important posts, generate 2 caption variants:

**Variant A (tone: informative):**
```
Discover our latest collection at Velmora! High-quality products at unbeatable prices.
#Velmora #NewArrivals #ShopNow
```

**Variant B (tone: emotional):**
```
Your shopping experience just got better! Welcome to Velmora, where quality meets affordability.
#Velmora #VelmoraLife #MustSee
```

**User chooses one before posting** (if review gate enabled, Section 12)

Or **post both variants** and monitor early engagement (1 hour) to pick winner for future posts.

---

## 20. Comment Moderation Hook (Optional)

After post goes live, periodically check comments:

- Poll comments every 6 hours for 24 hours post-publish
- Flag spam, abuse, or policy violations
- Auto-hide/delete (if enabled) or queue for user review
- Log moderation actions

**Per-page config:**
```json
{
  "page_id": "123456789",
  "moderate_comments": true,
  "auto_hide_spam": true,
  "moderation_duration_hours": 24
}
```

---

## 21. Video Processing (Step 3.3)

Before uploading video to Facebook:

**Validation:**
- Check file codec, resolution, aspect ratio (see Section 13)
- If mismatch detected: Auto-transcode using ffmpeg

**Example:** User provides 1920x1080 (16:9) video, but wants to post as Reel (4:5):
```bash
ffmpeg -i input.mp4 -vf "scale=1080:1350:force_original_aspect_ratio=decrease,pad=1080:1350:(ow-iw)/2:(oh-ih)/2" \
  -c:v libx264 -crf 23 -c:a aac -b:a 128k output_4-5.mp4
```

Jarvis performs this automatically (user doesn't need to know).

---

## 22. Bulk/Batch Scheduling (Optional)

**Example:**
```
"Velmora par agle 5 din daily 7 baje post karo"
(Post to Velmora daily at 7 PM for next 5 days)
```

**Jarvis parsing:**
- Recurrence: daily
- Count: 5 days
- Time: 7 PM
- Media source: Ask user for folder or "reuse same file?"

**Execution:**
- Create 5 separate database entries
- Schedule each via Strategy A (native Meta scheduling)
- Each gets own success/failure report

**Important:** Duplicate check (Section 8) must allow intentional re-posts across different days.

---

## 23. Cost & Quota Tracking

**Jarvis logging:**
- Each API call logs request count, response size, timestamp
- Aggregate daily: X posts, Y MB uploaded
- Weekly summary: "Sir, اس ہفتے Velmora par 12 posts upload ہوئے۔"

**If future paid services integrated:**
- Track cost per post, quota usage
- Alert if approaching quota limit
- Weekly cost report

---

## 24. Fallback to Browser Automation (Critical)

**Trigger:** API posting fails after 3 retries OR permission/app-review issues

**Process:**
1. Open Selenium WebDriver in headless Chrome
2. Navigate to facebook.com
3. Verify already logged in (check for profile element)
4. Navigate to target page
5. Click "Create post" button
6. Wait for compose modal
7. Fill caption text in contenteditable div
8. If media file: Upload via file input
9. Click "Post" button
10. Wait 3 seconds for modal to close
11. Extract post_id (simplified: use timestamp-based ID)
12. Report success or failure

**Requirements:**
- Chrome/Chromium installed
- Selenium WebDriver Python library
- User must be logged in to Facebook (no auto-login)

**Fallback logging:**
```json
{
  "publish_method": "browser_automation",
  "error": "API failed after 3 retries: invalid_token"
}
```

---

## 25. Media Retention Policy

**Temp files:**
- Downloaded from Google Drive (Section 5): Delete immediately after successful post
- Or delete after 3 failed retries if fallback to browser was attempted

**Proof screenshots** (Section 14):
- Keep for 30 days
- Auto-delete older files (weekly cleanup job)

**Local database** (`memory/facebook_posts.json`):
- Keep indefinitely for audit trail
- Periodic archival (e.g., monthly backups)

---

## 26. Complete Workflow Summary

**Voice command from user:**
```
"Sir, Velmora page par text post kar — Welcome to Velmora!"
```

**Jarvis execution (automated):**
1. ✅ Parse command → page=Velmora, type=text, content="Welcome to Velmora!"
2. ✅ Load credentials from `config/api_keys.json`
3. ✅ Generate caption: "Welcome to Velmora! #Velmora #VelmoraLife #BestDeals #OnlineShopping #ShopNow"
4. ✅ Call Meta Graph API: POST /123456789/feed with message
5. ✅ Receive post_id: "123456789_987654321"
6. ✅ Log to database: facebook_posts.json
7. ✅ Report success: "Sir, آپ کی text post کامیابی سے Velmora page پر publish ہو گئی! Post ID: 123456789_987654321"
8. ✅ Optional: Update engagement tracking, check comments, suggest next post time

**If API fails:**
1. ⚠️ Retry up to 3 times with backoff
2. ⚠️ Open browser, log in, navigate to page
3. ⚠️ Click "Create post", fill caption, upload media, click "Post"
4. ✅ Report success via browser method
5. ✅ Log database entry with `publish_method="browser_automation"`

**End result:** Post is live on Velmora page with proper caption + hashtags, full audit trail, and success confirmation to user.

---

## 27. Credential Reference

```json
{
  "fb_page_id": "YOUR_PAGE_ID_HERE",
  "fb_page_access_token": "EAABs...",
  "fb_app_id": "YOUR_APP_ID_HERE",
  "fb_app_secret": "YOUR_APP_SECRET_HERE"
}
```

Store in `config/api_keys.json` (git-ignored, local-only, user fills in manually).

---

## 28. Troubleshooting

| Issue | Solution |
|-------|----------|
| "Invalid access token" | Token expired. Refresh via Section 7.2 or login to Facebook developers console. |
| "Page access denied" | User role on page insufficient. Make posting user an Admin/Editor on page. |
| "Post already exists" | Duplicate detected. Say "force post" to override or choose different content. |
| "Video format unsupported" | Run through ffmpeg preprocessing (Section 21) or provide supported format. |
| "Rate limit exceeded" | Wait 1 hour. Meta limits 30 posts/day per page. Spread posts across hours. |
| "Browser modal not found" | Browser automation assumes facebook.com UI. UI may have changed. Fallback to manual posting. |
| "File not found" | Path is wrong or file was deleted. Check path or re-provide file location. |

---

## 29. Future Enhancements

1. **Instagram integration:** Extend workflow to Instagram (same media, different captions)
2. **TikTok sync:** Auto-post to TikTok after Facebook (with vertical format conversion)
3. **Analytics dashboard:** Show post performance, best times, top content
4. **Influencer collaboration:** Tag collaborators, track shared posts
5. **Content calendar:** Visual scheduler for batch posts
6. **Hashtag analytics:** Track hashtag performance, optimize pool

