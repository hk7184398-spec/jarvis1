# Facebook Page Management Guide for Jarvis

## 1. Facebook Login
- **Action:** Direct Jarvis to the Facebook login page.
- **Credentials:** Use securely stored credentials to log in automatically.

## 2. Navigate to Page
- **Action:** Provide the exact name or ID of the Facebook Page for posting.
- **Process:** Jarvis will navigate to the specified Facebook Page.

## 3. Create Post (Video/Photo)

### Step 3.1: Select Media
- **Action:** Specify the local path/location of the video or photo file.
- **Process:** Jarvis will access the file from the given location.

### Step 3.2: Upload
- **Action:** Initiate the post creation process on the Facebook Page.
- **Process:** Upload the selected video or photo.

### Step 3.3: Add Description and Hashtags
- **Instruction:** Jarvis should automatically generate viral descriptions and relevant hashtags based on the content or context.
- **Process:**
    - Analyze the media content.
    - Generate engaging, viral-style descriptions.
    - Research and include trending/relevant hashtags.

### Step 3.4: Post
- **Action:** Finalize and publish the post on the selected Facebook Page.

## 4. Voice Command Trigger (Natural Language Interface)

- **Trigger phrase example:** "Jarvis, Velmora page par kal 7 baje post schedule kar do."
- **Process:**
    1. Jarvis parses the voice command to extract:
        - **Page name** (e.g., "Velmora")
        - **Schedule time** (e.g., "kal 7 baje" → tomorrow 7:00 PM, resolved to an absolute timestamp)
        - **Media source** — if not mentioned, Jarvis asks: "Kis file/location se post karna hai?" (or defaults to a pre-configured Drive folder, see Section 5)
    2. Once media location is confirmed (e.g., Google Drive path), Jarvis fetches the file, analyzes it, and generates caption + hashtags (per Step 3.3).
    3. Post is queued/scheduled internally until the resolved timestamp.
    4. At the scheduled time, Jarvis publishes the post via the Meta Graph API.
    5. On success, Jarvis logs the post in the local database (see Section 8) and sends a confirmation report to the user (see Section 9).
    6. On failure, Jarvis logs the failure reason, retries automatically, and sends a failure report if retries are exhausted (see Section 10).

## 5. Media Source: Google Drive Integration

- **Action:** User mentions a Google Drive location (folder or file link) in the voice command or in a prior setup step.
- **Process:**
    - Jarvis authenticates with Google Drive (OAuth token, stored securely — same pattern as Facebook credentials).
    - Jarvis lists/locates the specified file (by name, latest file in folder, or exact link).
    - File is downloaded to a local temp path before upload to Facebook.
    - Temp file is deleted after successful post (or retained briefly for retry attempts, then cleaned up).

## 6. Posting via Meta Graph API

- **Action:** Replace/supplement browser-automation posting (Steps 3.2–3.4) with direct Meta Graph API calls where possible.
- **Process:**
    - Use Page Access Token (long-lived, securely stored, refreshed before expiry).
    - For photos: `POST /{page-id}/photos` with `url` or binary upload + `caption`.
    - For videos: `POST /{page-id}/videos` with binary upload + `description`.
    - For scheduled posts: use `published=false` + `scheduled_publish_time` (Unix timestamp) if native FB scheduling is preferred over Jarvis-side scheduling.
    - API response returns a `post_id` — this is the source of truth for success confirmation (verified-execution principle: no success report without a real `post_id`).

## 7. Meta Graph API — App Setup & Credential Generation

This section documents the one-time setup required before Jarvis can make any Meta Graph API call in Section 6. This is a manual setup process (done once via browser, not automated by Jarvis) — the resulting credentials are then stored and referenced by Jarvis's code.

### Step 7.1: Create a Meta App
- Go to `https://developers.facebook.com/apps`.
- Create a new App → select type **Business**.
- Under the App's Products, add **Facebook Login** and **Pages API**.

### Step 7.2: Generate a Page Access Token
- Open Graph API Explorer (`https://developers.facebook.com/tools/explorer`), select the App created above.
- Request the following permissions: `pages_manage_posts`, `pages_read_engagement`, `pages_show_list`.
- Generate a **short-lived User Access Token** first.
- Exchange it for a **Long-Lived User Access Token** (extends validity from ~1 hour to ~60 days).
- Use the Long-Lived User Token to fetch the target Page's **Long-Lived Page Access Token** — this token does not expire unless manually revoked, and is the one Jarvis will actually use for posting.

### Step 7.3: Store Credentials
- `jarvis1` does **not** use a `.env` file for its core credentials — API keys (Gemini, OpenRouter) are stored in `config/api_keys.json`, which is git-ignored and read via `core/config.py` (`load_config()` / `get_api_key()`).
- Facebook credentials follow the same pattern. Add these keys to `config/api_keys.json`:
    - `fb_page_id`
    - `fb_page_access_token`
    - `fb_app_id`
    - `fb_app_secret`
- **Note:** Actual credential values are intentionally left out of this guide and out of the GitHub repo. `config/api_keys.json` stays local-only (already covered by `.gitignore`) — the user fills in real values directly on their machine, never in a committed file.

### Step 7.4: Jarvis Code Integration
- `core/config.py` gets two new helper functions, following the existing `get_gemini_key()` / `get_openrouter_key()` pattern:
    - `get_facebook_page_id(required: bool = True) -> str`
    - `get_facebook_page_access_token(required: bool = True) -> str`
    - (App ID/Secret can be read the same way via `get_api_key("fb_app_id")` / `get_api_key("fb_app_secret")` if/when needed for token refresh flows.)
- A new module, e.g. `actions/facebook_poster.py`, calls these helpers instead of reading environment variables directly.
- No credentials should ever be hardcoded in source files or written into this guide — this matches the existing security pattern used across the `jarvis1` repo.
- This module is what Section 6's Graph API calls (`POST /{page-id}/photos`, `POST /{page-id}/videos`, etc.) will actually run through.

## 8. Database Update (Duplicate Prevention)

- **Action:** After a successful publish, update the local database.
- **Process:**
    - Store: `post_id`, `page_name`, `media_source_path`, `file_hash` (to detect the same file being reused), `caption`, `hashtags`, `scheduled_time`, `published_time`, `status`.
    - Before creating a new post, Jarvis checks the database for a matching `file_hash` + `page_name` within a recent time window to avoid accidental duplicate posting (e.g., same voice command triggered twice).

## 9. Success Reporting

- **Action:** After successful publish, notify the user.
- **Format example:** "Post successfully published on Velmora page at 7:00 PM. Post ID: XXXX. Caption: '...'"
- **Channel:** Voice reply and/or Obsidian/log entry, per Jarvis's existing reporting pattern.

## 10. Failure Handling

- **Action:** If any step fails (login, file fetch, upload, API call, scheduling), Jarvis must:
    1. Log the exact failure reason (API error code, network issue, missing file, expired token, etc.).
    2. Retry automatically — recommended: 3 attempts with exponential backoff (e.g., 30s, 2min, 5min).
    3. If all retries fail, send a failure report to the user with:
        - What step failed
        - Why it failed (plain-language reason, not just raw error)
        - Whether the media file/schedule is still queued or needs manual re-trigger

## 11. Cross-Platform Content Reuse

- **Context:** Same media file may already be used in the TikTok or YouTube pipeline.
- **Action:** When generating captions/hashtags for Facebook, adapt style per platform rather than reusing the exact same text everywhere.
- **Process:**
    - Facebook: longer, more descriptive caption; moderate hashtag count (3-5, relevant not spammy).
    - TikTok: short, punchy, trend-driven caption; higher hashtag density.
    - Jarvis should check if a caption/hashtag set already exists for this `file_hash` from another platform's pipeline, and if so, generate a Facebook-specific variant instead of copy-pasting.

## 12. Content Policy Pre-Check

- **Action:** Before publishing, run the auto-generated caption/hashtags through a basic compliance check.
- **Process:**
    - Screen for banned/flagged words, excessive or spammy hashtag patterns, and misleading claims.
    - If a violation is detected, regenerate the caption/hashtags automatically (up to 2 retries) before falling back to asking the user for manual review.
    - Goal: reduce risk of the Page being flagged, restricted, or reach-limited by Facebook.

## 13. Multi-Page Account Switching

- **Context:** Setup may later expand to manage more than one Facebook Page.
- **Action:** Page selection logic must be explicit and unambiguous.
- **Process:**
    - If the voice command names a Page (e.g., "Velmora page par..."), use that Page.
    - If no Page is named, use a pre-configured default Page — but only after Jarvis confirms once per session which Page is default, to avoid posting to the wrong Page silently.
    - Store each Page's own access token, ID, and settings separately (never share tokens across Pages).

## 14. Post-Publish Proof

- **Action:** In addition to logging the `post_id`, capture a screenshot of the live published post.
- **Process:**
    - After publish confirmation from the Graph API, Jarvis (via browser automation) opens the post URL and takes a screenshot.
    - Screenshot is saved alongside the database entry (Section 8) as an extra verification layer.
    - Reinforces the verified-execution principle: success is confirmed not just by API response but by visual proof the post actually exists live.

## 15. Engagement Feedback Loop

- **Action:** Periodically pull performance data for past posts.
- **Process:**
    - Use Facebook Insights API to fetch likes, shares, comments, and reach for previously published posts (e.g., 24h and 7-day checkpoints).
    - Store this data against each post's database entry.
    - Feed high-performing caption/hashtag patterns back into the caption-generation logic (Step 3.3) so future posts trend toward what has historically performed better on this Page.

## 16. "Abhi" vs Scheduled Disambiguation

- **Action:** Explicitly distinguish immediate-publish commands from scheduled ones.
- **Process:**
    - If the voice command includes "abhi" / "now" / no time reference at all with clear publish intent, Jarvis publishes immediately — bypassing the scheduling queue (Section 4) entirely.
    - If a future time is mentioned ("kal", "7 baje", a specific date), Jarvis queues it as a scheduled post.
    - This distinction must be resolved before any file fetch/caption generation begins, so "abhi" commands aren't delayed by scheduling logic overhead.

## 17. Auto-Pause on Repeated Failure

- **Action:** Protect against silent, repeated failures on a given Page.
- **Process:**
    - If a Page has consecutive failed publish attempts (e.g., 2-3 in a row) — commonly due to an expired token or revoked permission — Jarvis automatically pauses all further scheduled posts for that Page.
    - User is notified immediately with the reason and asked to confirm/fix before Jarvis resumes.
    - Prevents a backlog of scheduled posts from failing one-by-one unnoticed while the root cause (e.g., token expiry) goes unaddressed.

## 18. Best-Time-to-Post Optimization

- **Action:** If the user gives a publish command without specifying a time (e.g., just "post kar do"), Jarvis should not default to immediate/random posting.
- **Process:**
    - Pull historical performance data from Section 15 (Engagement Feedback Loop) for the target Page.
    - Identify the time slot(s) with historically highest engagement (likes/shares/reach) for that Page.
    - Auto-select the best upcoming slot and inform the user (e.g., "Is Page ke liye best time 7 PM hai, us par schedule kar raha hoon") — or ask for confirmation if the user prefers a review-first mode (see Section 12's review gate concept).

## 19. A/B Caption Testing

- **Action:** For high-value posts, test more than one caption variant instead of committing to a single AI-generated caption blind.
- **Process:**
    - Jarvis generates 2 caption variants (different tone/hook) for the same media.
    - Either: (a) present both to the user to pick one before publishing, or (b) publish variant A, monitor early engagement for a short window (e.g., 1 hour), then use the winner's style as the template for the next similar post.
    - Results feed back into Section 15's engagement feedback loop for continuous improvement.

## 20. Comment Moderation Hook

- **Action:** After a post goes live, periodically check its comments — especially important for business-critical Pages.
- **Process:**
    - Poll comments on recent posts (e.g., every few hours for the first 24-48 hours after publish).
    - Flag spam, abusive, or policy-violating comments using basic keyword/pattern detection.
    - Optionally auto-hide/delete flagged comments, or queue them for user review — configurable per Page.
    - This is an optional module; can be toggled on/off per Page depending on how actively the user wants moderation handled.

## 21. Video Processing Pre-Step

- **Action:** Before upload, ensure video meets Facebook's recommended specs.
- **Process:**
    - Check aspect ratio, resolution, and duration against Facebook's current recommended formats.
    - If the video doesn't match (e.g., wrong aspect ratio for feed vs. Reels), use ffmpeg to auto-resize/crop/re-encode — same approach already used in the TikTok pipeline's vertical-video step (Stage 3 assembly).
    - This avoids Facebook auto-cropping the video awkwardly or rejecting the upload outright.

## 22. Bulk/Batch Scheduling

- **Action:** Allow one voice command to create a recurring or multi-post schedule, instead of requiring a separate command per post.
- **Example trigger:** "Agle 5 din daily 7 baje post karo."
- **Process:**
    - Jarvis parses the recurrence pattern (daily/weekly, count or end date, fixed time).
    - For each occurrence, Jarvis needs a media source — either the same file reused (flagged clearly, since Section 8's duplicate check would otherwise block it) or a folder of multiple files consumed in sequence (e.g., next unused file in a Google Drive folder each day).
    - Each scheduled instance gets its own database entry (Section 8) and follows the same success/failure reporting (Sections 9-10) individually.

## 23. Cost/Quota Awareness

- **Action:** Track usage of any paid or quota-limited tools involved in the pipeline.
- **Process:**
    - Meta Graph API itself is free but rate-limited (see Section 28 of the Suggestions list below on rate limits).
    - If future enhancements add paid services (e.g., a premium hashtag research API, paid image/video processing), Jarvis should log each call's cost/quota usage.
    - Periodic summary (e.g., weekly) of usage/cost can be included in Jarvis's reporting so unexpected charges don't surprise the user.

## 24. Fallback to Browser Automation

- **Action:** If the Meta Graph API call fails for a systemic reason (permission issue, app review pending, temporary API outage), don't just retry the same failing method blindly.
- **Process:**
    - After the standard retry attempts (Section 10) are exhausted for API-level failures, Jarvis falls back to the browser-automation posting flow already described in Section 3 (Selenium-based login → navigate → upload → post).
    - This fallback acts as a redundancy layer so a single point of failure (API access) doesn't fully block posting.
    - Fallback usage should still be logged and reported to the user, since it indicates something is wrong with the primary (API) path that may need attention.

## 25. Media Retention Policy

- **Action:** Define how long locally stored files are kept.
- **Process:**
    - Applies to: temp files downloaded from Google Drive (Section 5) and post-publish proof screenshots (Section 14).
    - Recommended default: auto-delete after 30 days, or immediately after successful publish + proof screenshot for temp media files (keeping only the screenshot longer-term as lightweight proof).
    - A periodic cleanup job (e.g., daily/weekly) should scan and purge expired files to prevent disk space from filling up over time.

## 26. Complete Guide

This guide ensures seamless automation — from one-time Meta App/token setup, to a single voice command triggering Google Drive media retrieval, AI-generated captions/hashtags, Meta Graph API publishing, database-backed duplicate prevention, cross-platform-aware captioning, compliance pre-checks, post-publish proof, engagement-driven improvement, optimal timing, A/B testing, comment moderation, video pre-processing, batch scheduling, cost tracking, automation fallback, and storage cleanup — with no manual steps required after initial setup beyond the voice instruction itself.

---

## 27. Credential Placeholder Reference (fill in separately)

These keys go into `config/api_keys.json` (git-ignored, local-only) — never into this guide, `.env`, or any committed source file:

```json
{
    "gemini_api_key": "...",
    "openrouter_api_key": "...",
    "fb_page_id": "",
    "fb_page_access_token": "",
    "fb_app_id": "",
    "fb_app_secret": ""
}
```

- `fb_page_id` = *(to be added by user)*
- `fb_page_access_token` = *(to be added by user)*
- `fb_app_id` = *(to be added by user)*
- `fb_app_secret` = *(to be added by user)*

---

## 28. Suggestions / Open Considerations (for Jarvis implementation clarity)

- **Timezone handling:** "kal 7 baje" needs a fixed timezone reference (UAE local time) baked into the NLP parser — ambiguous relative times ("kal", "abhi") should always resolve against the system clock, not assume a default.
- **Ambiguous page/media resolution:** If multiple Facebook Pages or multiple files match a vague reference, Jarvis should ask a clarifying question rather than guessing — same pattern as WhatsApp module's contact-matching logic.
- **Token expiry monitoring:** Meta Page Access Tokens and Google Drive OAuth tokens should be checked proactively (e.g., daily health check) so a scheduled post doesn't fail silently due to an expired token at publish time.
- **Scheduling engine choice:** Decide whether scheduling lives in Jarvis (a background thread/cron job checking a `scheduled_posts` table) or is delegated to Facebook's native `scheduled_publish_time`. Native FB scheduling is more reliable across Jarvis restarts/crashes — recommended as primary, with Jarvis-side scheduling as fallback for platforms without native scheduling (e.g., if this pattern extends to Instagram/TikTok later).
- **Rate limits:** Meta Graph API has rate limits per app/page — worth logging remaining quota from response headers to avoid unexpected throttling during high-frequency posting.
- **Caption/hashtag review gate:** Given the TikTok pipeline's existing approval/rejection gate pattern, consider whether Facebook posts should also have an optional "show me the caption before publishing" mode (configurable per user preference — auto-publish vs. review-first), especially for pages where brand tone matters.
- **File format validation:** Before upload, validate file type/size against Facebook's accepted formats (video codecs, max size/duration) to fail fast with a clear reason rather than a cryptic API error.
- **Duplicate-check window:** Define an explicit time window (e.g., 24 hours) for the `file_hash` + `page_name` duplicate check in Section 8, so intentional re-posts of the same file later aren't blocked forever.
