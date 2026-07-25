# JARVIS — Skills System Master Prompt
## Specification for AI-Generated Skill Modules (Python / Node hybrid)

> Feed this document to an AI codegen tool (Claude, GPT, etc.) to generate the full working `skills/` package for JARVIS. Each skill is a self-contained module with a `TRIGGER` matcher, an `execute()` entrypoint, and a `SKILL.md`-style manifest that JARVIS's router reads at startup to decide which skill handles a given Roman Urdu / English command.

---

## 0. Architecture Overview

JARVIS currently routes commands through Gemini Live / Claude for intent parsing. This spec adds a **skills layer**: a directory of self-describing modules that get dynamically loaded, so new capabilities can be dropped in without touching core routing logic.

```
jarvis/
  core/
    router.py          # matches parsed intent -> skill
    skill_loader.py     # scans skills/ dir, loads manifests
  skills/
    browser_automation/
      SKILL.md
      handler.py
    documents/
      SKILL.md
      handler.py
    calendar_reminders/
      SKILL.md
      handler.py
    web_research/
      SKILL.md
      handler.py
    trading_data/           # already exists (MT5 module) — wrap as skill
      SKILL.md
      handler.py
    image_search/
      SKILL.md
      handler.py
    communication/          # WhatsApp / FB / YouTube — already exists, wrap as skill
      SKILL.md
      handler.py
    memory/
      SKILL.md
      handler.py
    youtube_automation/
      SKILL.md
      handler.py
    tiktok_automation/
      SKILL.md
      handler.py
    whatsapp_automation/
      SKILL.md
      handler.py
    system_control/
      SKILL.md
      handler.py
```

### SKILL.md manifest format (every skill must have one)

```markdown
---
name: browser_automation
triggers: ["browser kholo", "website kholo", "search karo web pe", "scrape", "form fill karo"]
requires_confirmation: false   # true = JARVIS must ask user before executing
cost: low|medium|high          # rough compute/API cost signal for router
---
# Description
One paragraph: what this skill does and when router should pick it.

# Entrypoint
`handler.execute(params: dict) -> dict`

# Example commands
- "jarvis, playwright.dev khol ke screenshot lo"
```

`skill_loader.py` parses the YAML frontmatter of every `SKILL.md`, builds a keyword+embedding index of `triggers`, and at runtime does a similarity match against the parsed user intent to pick the best skill (fallback: ask Gemini/Claude to classify if confidence < threshold).

---

## 1. Skill: Browser Automation

**Purpose:** General-purpose web interaction — open pages, fill forms, scrape data, take screenshots — for tasks outside the existing WhatsApp/Facebook/YouTube modules.

**Backend:** `@playwright/cli` wrapped as a subprocess, OR native `playwright` Python bindings for tighter control (recommended for JARVIS since it's already Python-first).

**Implementation approach:**
- Use `playwright.sync_api` (not the CLI) inside `handler.py` so JARVIS doesn't spawn a separate CLI process per command — keep one persistent browser context alive in a background thread, similar to how the WhatsApp Web bridge stays alive.
- Maintain a `BrowserSession` singleton with:
  - `open(url)`, `snapshot()` (accessibility-tree based, not screenshot — cheaper for AI to reason over), `click(ref)`, `fill(ref, text)`, `screenshot(path)`
- Snapshot-first pattern: after every action, capture the accessibility snapshot (not a full screenshot) and feed just that back into the AI provider for the next decision — keeps token cost low.
- Persistent profile support (`--profile=/path`) for logged-in sessions (e.g. if Dani wants JARVIS to check something on a site where he's already logged in).

**Guardrails:**
- `requires_confirmation: true` for any action that submits a form, makes a purchase, or posts content — mirror the same whitelist/rate-limit pattern already used in the WhatsApp auto-reply module.
- Never auto-fill payment fields.
- Domain allowlist configurable via `.env` (`BROWSER_ALLOWED_DOMAINS=`).

**Example commands (Roman Urdu):**
```
"jarvis, google pe XAUUSD news search karo aur summary do"
"jarvis, is form ko fill kar do [screenshot/URL]"
"jarvis, playwright.dev ka screenshot lo"
```

---

## 2. Skill: Document Generation & Reading

**Purpose:** Create/read PDF, DOCX, XLSX, PPTX on request — e.g. "jarvis, trading report PDF bana do" or "is docx ko parh ke summary do".

**Backend libraries:**
- PDF: `pypdf` / `reportlab` for creation, `pdfplumber` for extraction
- DOCX: `python-docx`
- XLSX: `openpyxl` or `xlsxwriter`
- PPTX: `python-pptx`

**Implementation approach:**
- Single `documents/handler.py` with sub-functions per format, dispatched by file extension or explicit request.
- Template system: keep a `templates/` folder (e.g. trading-report template, invoice template) so generation is fast and consistent — Dani can define his own templates once.
- For trading reports specifically: pull data from the existing MT5 module (`trading_data` skill) and auto-populate a DOCX/PDF template with today's XAUUSD positions, P&L, equity curve chart (matplotlib -> embedded image).

**Example commands:**
```
"jarvis, aaj ka trading report PDF bana do"
"jarvis, is Word file ko parh ke key points bata do"
"jarvis, YouTube script ko PPTX slides mein convert kar do"
```

---

## 3. Skill: Web Research

**Purpose:** Multi-step research — not just single search, but "search + read top results + synthesize" for things like gold market news, EA strategy research, competitor YouTube channel analysis.

**Backend:** Any search API (SerpAPI, Bing Search API, or Google Custom Search JSON API — pick one and put key in `.env`), plus `requests`/`trafilatura` for fetching and extracting article text.

**Implementation approach:**
- `search(query) -> list[result]`
- `fetch_and_extract(url) -> clean_text` (use `trafilatura` — handles most site boilerplate stripping automatically)
- `research(topic, depth=3) -> summary` — orchestrates: search, pick top N results, fetch each, feed all extracted text to the LLM provider for a synthesized Roman Urdu/English summary.
- Cache fetched pages for 1 hour to avoid duplicate calls during iterative conversations.

**Guardrails:**
- Respect robots.txt (use a library like `reppy` or manual check) before scraping.
- Never scrape content behind login walls.

**Example commands:**
```
"jarvis, gold price movement ke bare mein latest news dho"
"jarvis, XAUUSD ke liye is week ka fundamental outlook research karo"
```

---

## 4. Skill: Calendar & Reminders

**Purpose:** Native OS-level alarms/reminders/calendar events — separate from WhatsApp reminders.

**Backend (Windows, since JARVIS is desktop-first):**
- Calendar: `win32com.client` to talk to Outlook if installed, OR a local SQLite-based reminder table + Windows Task Scheduler (`schtasks`) for alarms if no calendar app is wired up.
- Simple alarms: schedule via `apscheduler` (Python) running inside JARVIS's main loop — triggers a TTS announcement + desktop notification (`plyer` or `win10toast`) at the set time. This is simpler than OS integration and works cross-platform.

**Implementation approach:**
- `create_alarm(time, message, repeat_days=[])`
- `create_reminder(datetime, message)`
- `list_upcoming()`
- Store in the existing SQLite memory DB (new table `alarms`), so alarms persist across restarts — reload and re-schedule with `apscheduler` on boot.

**Example commands:**
```
"jarvis, kal subha 7 baje alarm laga do"
"jarvis, roz raat 10 baje medicine reminder do"
"jarvis, mera schedule dikhao aaj ka"
```

---

## 5. Skill: Trading Data (wrap existing MT5 module)

**Purpose:** Formalize the existing read-only MT5 integration as a discoverable skill so the router can invoke it consistently alongside new skills.

**No new backend work needed** — wrap existing functions (`get_price`, `get_positions`, `get_account_summary`) behind the standard `handler.execute(params)` interface so it's uniform with the rest of the system.

**Extension point:** since `documents` skill now exists, trading_data can call into it to auto-generate PDF/DOCX reports on demand (see Section 2).

**Example commands:**
```
"jarvis, XAUUSD ka current price batao"
"jarvis, mera account summary do"
```

---

## 6. Skill: Image Search

**Purpose:** Fetch reference images for YouTube thumbnails, Facebook posts, or just answering "X kaisa dikhta hai" questions.

**Backend:** Unsplash API (already used for AstroTalk) or Pexels API (already used in the YouTube B-roll pipeline) — reuse existing keys.

**Implementation approach:**
- `search_images(query, count=3) -> list[image_url]`
- Feed results into the existing YouTube thumbnail pipeline or Facebook posting module directly when relevant.

**Example commands:**
```
"jarvis, thumbnail ke liye gold bars ki images dho"
```

---

## 7. Skill: Communication (wrap existing WhatsApp/FB/YouTube modules)

**No new work** — same wrapping pattern as Section 5, just expose existing WhatsApp-web.js bridge, Facebook Graph API poster, and YouTube upload pipeline as three sub-skills under one manifest so the router treats them uniformly.

---

## 8. Skill: Memory

**Purpose:** Expose JARVIS's existing SQLite memory as a first-class skill so other skills can read/write context (e.g. browser_automation remembering a logged-in session, or trading_data remembering Dani's risk preferences).

**Implementation approach:**
- `remember(key, value, scope="global"|"session")`
- `recall(key)`
- `search_memory(query)` — simple keyword search over stored entries, or embed with a lightweight local embedding model (e.g. `sentence-transformers/all-MiniLM-L6-v2`) if semantic recall is needed later.

---

## 9. Skill: YouTube Automation (formalize as discoverable skill)

**Purpose:** Wrap the existing YouTube pipeline (trend research → AI script → edge-tts → Pexels B-roll → captions → music → thumbnail → OAuth2 upload) as a router-visible, voice-controllable skill with full state tracking, error recovery, and analytics — so JARVIS always knows exactly what stage a video is at and never leaves a task in an ambiguous state.

### 9.1 Full pipeline state machine

Every video job moves through explicit, persisted states (stored in SQLite table `youtube_jobs`) so JARVIS can resume, report, or retry at any point instead of losing track mid-pipeline:

```
QUEUED -> RESEARCHING_TREND -> SCRIPT_GENERATING -> SCRIPT_READY
       -> VOICEOVER_GENERATING -> BROLL_FETCHING -> CAPTIONS_GENERATING
       -> MUSIC_ADDING -> RENDERING -> THUMBNAIL_GENERATING
       -> READY_FOR_REVIEW -> (confirmation) -> UPLOADING
       -> UPLOADED_PRIVATE -> (confirmation) -> PUBLISHED
       -> FAILED (with failure_stage + error_message + retry_count)
```

Each state transition is logged with a timestamp. If JARVIS restarts mid-pipeline, `skill_loader` reads any job not in a terminal state (`PUBLISHED`/`FAILED`/`CANCELLED`) and resumes from the last completed stage rather than starting over — this avoids wasting API credits (script gen, TTS, thumbnail gen) on stages already done.

### 9.2 Functions (`handler.py`)

- `trigger_full_pipeline(topic: str, target_length_sec: int = 480) -> job_id` — creates a `youtube_jobs` row, kicks off async pipeline in a background worker thread/queue (use `concurrent.futures.ThreadPoolExecutor` or a simple job queue table polled by a worker loop — avoid blocking the main voice-assistant loop).
- `check_pipeline_status(job_id=None) -> dict` — if `job_id` omitted, return status of the most recent active job. Returns `{stage, percent_complete, eta_estimate, last_error}`.
- `retry_failed_job(job_id) -> bool` — resumes from `failure_stage` rather than restarting the whole pipeline.
- `cancel_job(job_id) -> bool` — stops pipeline, cleans up partial temp files (rendered clips, unused audio), marks `CANCELLED`.
- `schedule_upload(job_id, datetime) -> bool` — after `READY_FOR_REVIEW`, instead of immediate upload, store `scheduled_at` and let the `calendar_reminders` skill's scheduler fire the upload at that time. If the video isn't actually rendered yet when the scheduled time hits (still `RENDERING`), JARVIS should proactively notify Dani rather than silently failing.
- `get_channel_analytics(range="7d") -> dict` — views, watch-time-minutes, subscriber delta, top-performing video in range, via YouTube Analytics API v2. Cache result 30 min to avoid hammering quota.
- `list_recent_jobs(limit=5) -> list[dict]` — quick voice-answerable "kaunsi videos chal rahi hain / recently bani hain" query.

### 9.3 Error handling per stage (so nothing silently breaks)

- **Trend research fails / API timeout** → retry once with backoff, then fall back to Dani-specified topic list in `.env` (`YOUTUBE_FALLBACK_TOPICS=`) and notify Dani which fallback was used.
- **Script generation fails or returns empty/too-short content** → validate word count against `target_length_sec` before proceeding; if invalid, auto-retry generation once with an adjusted prompt, else mark `FAILED` with clear reason.
- **TTS (edge-tts) fails** → check for rate-limit vs. network error distinctly (different retry strategy); if edge-tts is down entirely, fall back to a configured secondary TTS engine if one exists.
- **B-roll fetch (Pexels) returns insufficient clips for script length** → widen search query (drop most specific keyword), and if still short, reuse clips with different in/out points rather than failing the whole job.
- **Render (ffmpeg) fails** → capture ffmpeg stderr into `youtube_jobs.error_message`, this is almost always a codec/path/font issue — surface the raw error to Dani rather than a generic "render failed" so he can debug fast.
- **Upload OAuth2 token expired** → attempt silent refresh via stored refresh_token; if refresh itself fails, pause pipeline at `READY_FOR_REVIEW`-equivalent state and alert Dani to re-authenticate — never let this crash the whole assistant process.
- **Quota exceeded (YouTube Data API daily limit)** → detect the specific quota-exceeded error code, queue the upload for next quota reset (~midnight Pacific) rather than just failing, and tell Dani the video is rendered and waiting.

### 9.4 Guardrails

- `requires_confirmation: true` before the private→public publish switch — matches existing confirm-publish step. JARVIS must read back the title + first line of description before Dani confirms, not just say "publish kar doon?".
- Upload quota check *before* triggering pipeline (YouTube Data API has daily quota units, upload costs ~1600 units) — warn Dani if fewer than 2 uploads' worth of quota remain.
- Never auto-publish without explicit confirmation, even if `schedule_upload` time has arrived — scheduled publish still requires Dani's earlier explicit confirmation at scheduling time (i.e. confirmation happens once, at scheduling, not skipped later).
- Duplicate-topic guard: before starting a new job, check `youtube_jobs` history for a very similar topic in the last N days and ask Dani to confirm he wants to proceed anyway.

**Example commands:**
```
"jarvis, aaj ke liye ek gold trading video bana do"
"jarvis, video ka status kya hai abhi?"
"jarvis, channel ki analytics batao is hafte ki"
"jarvis, video ko kal subha 9 baje schedule kar do"
"jarvis, jo video fail hui thi wo dubara try karo"
```

---

## 10. Skill: TikTok Automation

**Purpose:** Short-form video posting pipeline for TikTok — repurpose existing YouTube pipeline output (vertical crop) or generate native short-form content, plus posting/scheduling, with the same rigor and state tracking as the YouTube skill so nothing gets posted by accident or lost mid-process.

### 10.1 Two content sourcing modes

1. **Repurpose mode** — take a completed YouTube `youtube_jobs` render, extract the strongest 15–60s segment (either Dani specifies timestamps, or auto-detect using the existing script's highest-energy/hook section — the opening line is usually the strongest hook), crop to 9:16.
2. **Native mode** — generate a short-form-specific script (shorter, punchier, hook-in-first-3-seconds structure) independently via the same AI script generator used in YouTube pipeline but with a "short-form" prompt template, then run through the same TTS → B-roll → render steps at vertical aspect ratio from the start.

### 10.2 Backend & auth reality check

- TikTok's **Content Posting API** requires app review and an approved use-case (audited by TikTok) before it allows unaudited/direct public posting from non-reviewed apps — until that approval exists, posting defaults to **DRAFT mode** upload via the API (posts to Dani's own TikTok drafts/inbox for him to manually confirm/publish inside the app) rather than direct-to-public.
- If Content Posting API access isn't set up at all, fall back to `browser_automation` skill: reuse a persistent logged-in TikTok profile session, navigate to the upload page, fill caption, and — **stop short of clicking final "Post"** — leave it staged for Dani's manual tap unless he's explicitly set `TIKTOK_AUTO_PUBLISH=true` in `.env` (off by default).

### 10.3 Functions (`handler.py`)

- `repurpose_for_tiktok(source_job_id, start_sec=None, end_sec=None) -> vertical_video_path` — ffmpeg smart-crop (center-weighted or face-tracked crop if `opencv` face detection is wired in) from 16:9 to 9:16, auto-selects strongest segment if timestamps not given, burns in captions from existing caption file repositioned for vertical framing.
- `generate_native_short(topic) -> job_id` — full independent short-form pipeline, tracked in its own `tiktok_jobs` table mirroring the YouTube state machine (QUEUED → SCRIPT → VOICEOVER → BROLL → RENDER → CAPTION_BURN → READY_FOR_REVIEW → POSTED/DRAFTED).
- `post_video(video_path, caption, hashtags: list[str]) -> post_id_or_draft_id` — routes to Content Posting API (draft mode by default) or browser fallback per 10.2.
- `get_analytics() -> dict` — views/likes/shares/completion-rate via API if available; note in response if analytics are unavailable due to API access tier.

### 10.4 Guardrails

- `requires_confirmation: true` for every post, no exceptions, even in "auto publish" `.env` mode Dani must have confirmed at least the caption/hashtags before the render was finalized.
- Rate limit: max N posts/day configurable (`TIKTOK_MAX_POSTS_PER_DAY=`, sane default 2) to avoid spam-flagging the account.
- Never automate engagement (likes/follows/comments/duets) — posting and analytics-reading only, to stay within platform ToS as much as possible and avoid account flags.
- If falling back to browser automation, session cookies/login state must live only in the local persistent profile — never logged or transmitted elsewhere.
- Hashtag/caption content should avoid anything that could trip TikTok's automated spam/misinformation filters (e.g. no engagement-bait phrasing like "follow for more" spam patterns) — keep it natural.

**Example commands:**
```
"jarvis, is YouTube video ko TikTok ke liye vertical bana do"
"jarvis, sabse strong 30 second wala part nikal ke short bana do"
"jarvis, ek naya native TikTok short bana do gold trading tips pe"
"jarvis, TikTok pe draft bhej do caption ke sath"
"jarvis, TikTok analytics batao"
```

---

## 11. Skill: WhatsApp Automation (extends existing WhatsApp module)

**Purpose:** Formalize and extend the existing whatsapp-web.js bridge — this spec adds outbound "pat message" (scheduled/one-off direct send), media send, and broadcast as clean, router-visible actions distinct from the whitelist auto-reply system, with explicit delivery confirmation so JARVIS never assumes a message went through when it didn't.

### 11.1 Bridge architecture recap + extension points

The existing Node.js `whatsapp-web.js` process runs as a persistent child process/service that JARVIS's Python core talks to over a local IPC channel (existing pattern — likely a small HTTP server or stdin/stdout JSON protocol already used for the auto-reply module). This skill adds new message types to that same protocol rather than building a second bridge:

```
Python core  <--JSON over local socket/HTTP-->  Node whatsapp-web.js bridge  <-->  WhatsApp Web session
```

New outbound message types added to the existing protocol: `SEND_TEXT`, `SEND_MEDIA`, `SEND_SCHEDULED` (Python-side scheduling, bridge just receives `SEND_TEXT`/`SEND_MEDIA` at fire time), `BROADCAST`.

### 11.2 Functions (`handler.py`)

- `resolve_contact(name_or_number: str) -> contact_id` — reuses existing fuzzy contact matcher; if match confidence is low (multiple similar names, e.g. "Ali" matching 3 contacts), JARVIS must ask Dani to disambiguate rather than guessing ("Ali Khan, Ali Raza, ya Ali Trading Group — kaunsa Ali?").
- `send_message(contact, message) -> delivery_result` — sends via bridge, **waits for and returns actual delivery status** (sent/delivered/failed) rather than firing-and-forgetting; WhatsApp Web gives single/double-tick status which the bridge should surface back.
- `send_scheduled_message(contact, message, datetime) -> scheduled_job_id` — registers with `calendar_reminders` skill's `apscheduler`; at fire time calls `send_message` and, critically, **if the contact is no longer resolvable or WhatsApp Web session is logged out at fire time, JARVIS must notify Dani that the scheduled message failed** rather than silently dropping it.
- `send_media(contact, file_path, caption="") -> delivery_result` — validates file exists and is under WhatsApp's size limits (16MB for most media, 100MB video) *before* attempting send, to fail fast with a clear reason instead of a vague bridge timeout.
- `broadcast(contact_list: list[str], message) -> dict[contact, delivery_result]` — sends individually to each resolved contact (not using WhatsApp's native broadcast-list feature, which requires all recipients to have Dani's number saved — individual sends are more reliable), returns a per-contact result map so partial failures are visible, not hidden behind an aggregate "sent" status.
- `get_session_status() -> dict` — is WhatsApp Web session currently logged in/QR-pending/disconnected; JARVIS should proactively check this before any send attempt and warn Dani immediately if session needs re-scanning a QR code, rather than letting sends silently queue and fail.

### 11.3 Guardrails (same spirit as existing auto-reply whitelist)

- `send_message`/`send_media`/`broadcast` to any contact **not already on the existing whitelist** requires `requires_confirmation: true` — JARVIS reads back contact name + message content before sending, every time, for non-whitelisted contacts.
- Whitelisted contacts can be sent to without per-message confirmation, but still subject to rate limiting.
- Rate limit reused from the existing auto-reply module's limiter (per-contact and global caps) — outbound "pat messages" count against the same limits so a scripted loop can't accidentally spam one contact.
- `broadcast` capped at a max recipient count (`WHATSAPP_MAX_BROADCAST=`, sane default 10) — anything larger requires explicit Dani override, since WhatsApp Web itself can flag accounts for bulk-messaging patterns.
- Never auto-send to numbers not previously known to JARVIS (i.e. no cold-outreach automation) — this skill is for Dani's own contacts only, not for building a marketing/spam tool.
- All sends logged to `skill_log` with contact, timestamp, message hash (not full content, for privacy in logs), and delivery status.

**Example commands:**
```
"jarvis, Ali ko WhatsApp pe message bhejo 'meeting 5 baje hai'"
"jarvis, kal 9 baje mama ko reminder message bhejo"
"jarvis, trading group ko alert bhejo XAUUSD buy signal ka"
"jarvis, ye screenshot Ahmed ko WhatsApp pe bhej do"
"jarvis, WhatsApp session connected hai ya nahi check karo"
```

---

## 12. Skill: System Control (laptop settings)

**Purpose:** Voice/text-triggered control over local OS-level settings — volume, files/folders, brightness, power state, and other "computer, do X" style commands.

**Backend (Windows-first, since JARVIS runs on Dani's laptop):**
- Volume control: `pycaw` (Python Core Audio Windows Library) for precise up/down/mute/set-to-N%, or simulate media keys via `keyboard`/`pyautogui` (`volume up` / `volume down` / `volume mute` virtual keys) for a simpler no-dependency approach.
- Brightness: `screen-brightness-control` library.
- Folder/file management: native `os`/`pathlib` — create, rename, move, delete (delete always behind confirmation).
- App control: `psutil` to list/kill running processes; `os.startfile()` or `subprocess.Popen` to launch apps.
- Power actions: `os.system("shutdown /s /t 0")`, `/r` for restart, `/h` for hibernate (Windows-specific commands).
- Screenshot/lock screen: `pyautogui.screenshot()`, `ctypes.windll.user32.LockWorkStation()`.

**Implementation approach — function list:**
- `volume_up(step=10)` / `volume_down(step=10)` / `set_volume(percent)` / `mute()` / `unmute()`
- `brightness_set(percent)` / `brightness_up()` / `brightness_down()`
- `create_folder(path, name)` / `create_file(path, name)` / `delete_item(path)` (confirmation required) / `rename_item(path, new_name)`
- `open_app(name)` / `close_app(name)` / `list_running_apps()`
- `lock_screen()` / `shutdown()` / `restart()` / `sleep()` (last three always `requires_confirmation: true`)
- `take_screenshot(save_path)`

**Guardrails:**
- `shutdown`, `restart`, `delete_item` → always `requires_confirmation: true`, no exceptions, regardless of `.env` settings.
- System control skill should run with the same OS-user privileges as JARVIS itself — no privilege escalation, no registry edits, no system file access.
- Log every system_control action (what changed, old value → new value) to the `skill_log` table for auditability, since these are irreversible-ish local machine changes.

**Example commands:**
```
"jarvis, volume 20% kam kar do"
"jarvis, volume full kar do"
"jarvis, Desktop pe 'Trading Notes' naam ka folder bana do"
"jarvis, screen lock kar do"
"jarvis, laptop shutdown kar do" -> JARVIS confirms first: "Pakka shutdown karun? (haan/nahi)"
```

---

## 13. Router Logic (core/router.py)

```
1. Parse user command (Gemini Live / Claude) -> extract intent + entities
2. Compute similarity between intent and each skill's `triggers` list
3. If top match confidence > 0.75 -> route directly
4. Else -> ask LLM provider: "Which skill handles: <command>? Options: [skill list]"
5. If requires_confirmation -> JARVIS speaks/sends confirmation prompt, waits for Dani's yes/no
6. Execute skill.handler.execute(params)
7. Log result to memory skill for context continuity
```

---

## 14. Safety & Guardrails Summary (apply across all skills)

- Every skill declares `requires_confirmation` in its manifest — router enforces this uniformly.
- Rate limiting: reuse the existing WhatsApp auto-reply rate-limiter pattern for any skill that can spam (browser automation, communication).
- `.env`-based feature flags: every skill can be individually disabled (`SKILL_BROWSER_AUTOMATION_ENABLED=false`) without code changes.
- All skill actions logged to SQLite `skill_log` table (timestamp, skill, params, result, success/fail) for debugging and audit.

---

## Deliverable ask for codegen tool

Generate the following files, single-file-per-skill where possible, with full inline documentation and `.env` config blocks, matching JARVIS's existing coding conventions (Roman Urdu/English comments where clarifying, comprehensive error handling, no placeholder stubs):

1. `core/skill_loader.py`
2. `core/router.py`
3. `skills/browser_automation/handler.py` + `SKILL.md`
4. `skills/documents/handler.py` + `SKILL.md`
5. `skills/web_research/handler.py` + `SKILL.md`
6. `skills/calendar_reminders/handler.py` + `SKILL.md`
7. `skills/trading_data/handler.py` + `SKILL.md` (wrapper only)
8. `skills/image_search/handler.py` + `SKILL.md`
9. `skills/communication/handler.py` + `SKILL.md` (wrapper only)
10. `skills/memory/handler.py` + `SKILL.md`
11. `skills/youtube_automation/handler.py` + `SKILL.md`
12. `skills/tiktok_automation/handler.py` + `SKILL.md`
13. `skills/whatsapp_automation/handler.py` + `SKILL.md`
14. `skills/system_control/handler.py` + `SKILL.md`
