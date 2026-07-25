# JARVIS — Modules Documentation

> Full catalog of every module in the JARVIS system: what it does, where it lives, what it depends on, and its current build status. Use this as the single source of truth for system architecture — update it whenever a module is added, changed, or its status moves.

---

## How to read this file

Each module entry follows the same structure:
- **Status:** `LIVE` (built and working) / `SPEC` (designed, not yet built) / `PARTIAL` (built but incomplete) / `PLANNED` (not yet designed in detail)
- **Path:** where it lives in the codebase
- **Depends on:** other modules or external services it needs
- **Exposes:** the functions/interface other modules or the router can call
- **Config:** relevant `.env` keys

---

## System Map

```
jarvis/
  core/
    main.py                  # entrypoint, main voice/text loop
    router.py                 [SPEC]  intent -> skill dispatch
    skill_loader.py            [SPEC]  loads SKILL.md manifests
    memory_db.py               [LIVE]  SQLite wrapper (existing memory system)
    ai_provider.py             [LIVE]  multi-provider abstraction (OpenAI/Anthropic/Gemini/OpenRouter)
    tts_stt.py                 [LIVE]  text-to-speech / speech-to-text
    dashboard.py               [PARTIAL] tkinter dashboard
  skills/
    browser_automation/        [SPEC]
    documents/                 [SPEC]
    web_research/               [SPEC]
    calendar_reminders/          [SPEC]
    trading_data/                [LIVE]  (MT5, read-only)
    image_search/                 [SPEC]
    communication/
      whatsapp/                  [LIVE]  (whatsapp-web.js bridge + auto-reply)
      facebook/                  [LIVE]  (Graph API posting)
      youtube/                   [LIVE]  (AutoTube Pro pipeline)
    memory/                       [SPEC]  (formalizes memory_db.py as a skill)
    youtube_automation/            [SPEC]  (extends existing youtube/ module)
    tiktok_automation/              [PLANNED]
    whatsapp_automation/             [SPEC]  (extends existing whatsapp/ module)
    system_control/                   [PLANNED]
```

---

## Core Modules

### `core/main.py`
**Status:** LIVE
**Purpose:** Entrypoint — starts the voice/text input loop, initializes AI provider connections, brings up the dashboard and background bridges (WhatsApp Node process, MT5 connection).
**Depends on:** `ai_provider.py`, `tts_stt.py`, `memory_db.py`, and (once built) `router.py`.
**Exposes:** N/A — process entrypoint.
**Internal structure:** Boot sequence should be explicit and ordered: (1) load `.env` config, (2) initialize `memory_db.py` connection, (3) initialize `ai_provider.py` (test at least one provider is reachable before continuing), (4) spawn the WhatsApp Node bridge as a subprocess and wait for its "ready" signal, (5) connect to MT5 terminal, (6) start `tts_stt.py` audio loop, (7) launch dashboard, (8) enter main input loop.
**Data flow:** User speech/text → `tts_stt.listen()` → raw text → (once router exists) `router.route()` → skill execution → result → `tts_stt.speak()`.
**Known risks / edge cases:** If any boot step fails (e.g. MT5 terminal not running, WhatsApp QR not scanned), `main.py` should not silently continue in a half-initialized state — it should clearly report which subsystem failed and let JARVIS still function for everything that *did* initialize correctly (graceful partial startup, not all-or-nothing).

### `core/router.py`
**Status:** SPEC (see skills master-prompt)
**Purpose:** Central dispatch — takes parsed intent, matches against every skill's declared triggers, routes execution to the correct skill handler, enforces `requires_confirmation` uniformly.
**Depends on:** `skill_loader.py`, `ai_provider.py` (for fallback intent classification).
**Exposes:** `route(intent, entities) -> skill_result`
**Config:** `ROUTER_CONFIDENCE_THRESHOLD=0.75`
**Internal structure:** Two-stage matching — (1) fast keyword/embedding similarity check against the trigger index built by `skill_loader.py` (cheap, no API call); (2) if confidence is below threshold, fall back to an explicit LLM classification call ("which of these skills handles this command") via `ai_provider.py`. This two-stage design keeps routing fast and cheap for the common case, only paying for an extra API call on genuinely ambiguous input.
**Data flow:** raw text → intent+entity extraction (existing Gemini Live/Claude parsing) → `router.route()` → matched skill's `handler.execute(params)` → wraps result in the `@logged_action` decorator (writes to `skill_log`) → returns to `main.py` for response generation.
**Known risks / edge cases:** Ambiguous commands that could match two skills equally (e.g. "message bhejo" could mean WhatsApp or a future SMS skill) need a disambiguation prompt back to Dani rather than silently picking one — same pattern as WhatsApp's contact disambiguation (section 11.2 of the skills spec).

### `core/skill_loader.py`
**Status:** SPEC
**Purpose:** Scans `skills/` at boot, parses each `SKILL.md` YAML frontmatter, builds the trigger-matching index used by the router. On restart, also resumes any in-progress job (YouTube/TikTok pipeline) that wasn't in a terminal state.
**Depends on:** filesystem access to `skills/`.
**Exposes:** `load_all_skills() -> dict[skill_name, manifest]`, `resume_incomplete_jobs()`
**Internal structure:** On each `SKILL.md` found, parse YAML frontmatter for `name`, `triggers`, `requires_confirmation`, `cost`; validate the corresponding `handler.py` actually exports an `execute()` function before registering the skill (fail loud with a clear message if a skill folder is malformed, rather than crashing the whole loader or silently skipping it).
**Data flow:** filesystem scan → parsed manifests → in-memory trigger index (dict or lightweight embedding index) → handed to `router.py` at boot.
**Known risks / edge cases:** A skill with a broken `handler.py` (import error, missing `execute()`) should be logged as unavailable and excluded from routing, not bring down the entire loader — one bad skill folder shouldn't take down all of JARVIS.

### `core/memory_db.py`
**Status:** LIVE
**Purpose:** SQLite-backed persistent memory — the existing ADAB/JARVIS memory system storing conversation context, learned facts, and (per the skills spec) will also house `skill_log`, `pending_confirmations`, `youtube_jobs`, `tiktok_jobs`, `trade_history`, `alarms`, `contact_profiles`, and `usage_log` tables as those features land.
**Depends on:** Nothing (base infrastructure).
**Exposes:** `remember()`, `recall()`, `search_memory()`, raw query access for other modules' tables.
**Internal structure:** Single SQLite file (e.g. `jarvis_memory.db`) with one connection pool shared across modules — since SQLite handles concurrent writes poorly, either use WAL mode (`PRAGMA journal_mode=WAL`) to allow concurrent reads during writes, or funnel all writes through a single serialized queue if write contention becomes an issue as more skills land.
**Data flow:** Every skill that needs persistence (job state, logs, schedules) reads/writes through this module rather than opening its own SQLite connection — keeps schema management and migrations centralized in one place.
**Known risks / edge cases:** As more tables get added (this file already lists 8+ planned tables beyond the original memory tables), schema migrations need a lightweight versioning approach (even a simple `schema_version` table + ordered migration scripts) so upgrades don't require manually altering a live database.

### `core/ai_provider.py`
**Status:** LIVE
**Purpose:** Abstraction layer over multiple AI providers (OpenAI, Anthropic, Gemini, OpenRouter) so skills/core logic don't need to know which provider is active — supports the multi-provider fallback pattern already established in Adab v3.0.
**Depends on:** Provider API keys in `.env`.
**Exposes:** `generate(prompt, provider=None) -> text`, `classify_intent(text) -> intent`
**Config:** `OPENAI_API_KEY=`, `ANTHROPIC_API_KEY=`, `GEMINI_API_KEY=`, `OPENROUTER_API_KEY=`, `DEFAULT_PROVIDER=`
**Internal structure:** A common interface (e.g. `BaseProvider` class) with one concrete implementation per provider, each normalizing that provider's response format into a shared internal shape so callers never deal with provider-specific response quirks.
**Data flow:** `generate(prompt)` → tries `DEFAULT_PROVIDER` first → on failure (timeout, rate limit, auth error), falls through an ordered fallback list of other configured providers → returns first successful response, or a clear "all providers failed" error if none succeed.
**Known risks / edge cases:** Different providers have different context window limits and pricing — the fallback logic should account for this (e.g. don't silently fall back to a provider that will truncate a long prompt without warning). This is also the natural integration point for the P2 local-LLM-fallback idea (an Ollama-backed provider implementation slotting into the same interface).

### `core/tts_stt.py`
**Status:** LIVE
**Purpose:** Text-to-speech (edge-tts) and speech-to-text for the voice interaction loop. Target for the P1 barge-in upgrade (chunked playback + hot-mic interrupt detection).
**Depends on:** `edge-tts`, STT engine (existing choice — Whisper or provider-native).
**Exposes:** `speak(text)`, `listen() -> text`, (planned) `speak_interruptible(text)`
**Internal structure:** Current `speak()` is presumably a single blocking call (generate full audio, then play). The barge-in upgrade requires restructuring this into streamed/chunked synthesis + playback (sentence-by-sentence or fixed-duration chunks) with a cancellation flag checked between chunks.
**Data flow:** text → edge-tts synthesis → audio buffer → playback device; audio input → STT engine → text → passed to router.
**Known risks / edge cases:** Roman Urdu/mixed-language text can trip up TTS pronunciation and STT recognition accuracy — worth an explicit test pass with real Roman Urdu phrases Dani actually uses, not just English, since this is the primary interaction language.

### `core/dashboard.py`
**Status:** PARTIAL
**Purpose:** tkinter-based control panel. Target for the P0 health-dashboard upgrade — needs a standard `get_status()` polling loop across all skills, plus a rendered view of the pending-confirmation queue.
**Depends on:** Every skill implementing a `get_status()` method once the router pattern lands.
**Exposes:** N/A — UI layer.
**Internal structure:** Polling loop (e.g. every 3-5 seconds) calling `get_status()` on each loaded skill, updating a status panel; separate panel rendering rows from `pending_confirmations` with approve/reject buttons wired to resolve those rows directly.
**Data flow:** `skill_loader`'s registered skills → periodic `get_status()` calls → UI refresh; `pending_confirmations` table → UI list → Dani's click → resolves the row → router executes or discards.
**Known risks / edge cases:** Polling every skill on a fixed interval could become slow as skill count grows — consider event-driven status updates (skills push status changes rather than being polled) if the dashboard starts lagging once more skills are LIVE.

---

## Skill Modules

### `skills/browser_automation/`
**Status:** SPEC
**Purpose:** General-purpose web interaction (open/click/fill/scrape/screenshot) for tasks outside the dedicated WhatsApp/Facebook/YouTube modules. Also used as a fallback posting mechanism for TikTok if API access isn't approved.
**Depends on:** `playwright` (Python bindings).
**Exposes:** `open(url)`, `snapshot()`, `click(ref)`, `fill(ref, text)`, `screenshot(path)`
**Config:** `BROWSER_ALLOWED_DOMAINS=`
**Internal structure:** A `BrowserSession` singleton keeps one persistent browser context alive in a background thread rather than spawning a new browser per command — matches the pattern already used for the WhatsApp Web bridge staying alive across the session.
**Data flow:** command → resolve target (URL or existing page) → action (click/fill/etc.) → accessibility-tree snapshot captured and fed back to the AI provider for the next decision, not a full screenshot (cheaper in tokens).
**Known risks / edge cases:** Persistent logged-in sessions (via `--profile=`) mean this module effectively holds Dani's website credentials in browser storage — the domain allowlist in `.env` is the main safety boundary here and should be treated as security-critical config, not just a convenience setting.

### `skills/documents/`
**Status:** SPEC
**Purpose:** Create/read PDF, DOCX, XLSX, PPTX. Powers trading-report generation (pulls from `trading_data`) and feeds into cross-skill workflows like report→WhatsApp.
**Depends on:** `pypdf`/`reportlab`, `python-docx`, `openpyxl`, `python-pptx`.
**Exposes:** `generate_pdf()`, `generate_docx()`, `generate_xlsx()`, `generate_pptx()`, `read_document(path) -> text`
**Internal structure:** One handler file with format-specific sub-functions, dispatched by requested output type; a `templates/` folder holds reusable layouts (trading-report, invoice) so generation is fast and visually consistent rather than building documents from scratch each time.
**Data flow:** For trading reports specifically — `trading_data.get_positions()`/`get_account_summary()` → data passed into the DOCX/PDF template renderer → equity curve chart rendered via matplotlib → embedded as an image in the final document.
**Known risks / edge cases:** Generated documents can contain sensitive financial data (account balances, positions) — output files should land in a clearly Dani-only location, and if this skill ever feeds into `whatsapp_automation.send_media()`, the recipient-whitelist guardrail from that skill becomes the safety net preventing an accidental send of financial data to the wrong contact.

### `skills/web_research/`
**Status:** SPEC
**Purpose:** Multi-step research — search, fetch, extract, synthesize. Used for market news, EA strategy research, and (P3) multi-modal trading alerts combining price + sentiment.
**Depends on:** Search API (SerpAPI/Bing/Google Custom Search), `trafilatura`.
**Exposes:** `search(query)`, `fetch_and_extract(url)`, `research(topic, depth)`
**Config:** `SEARCH_API_KEY=`
**Internal structure:** `research(topic, depth)` orchestrates the other two functions — search, pick top N results, fetch+extract each, feed all extracted text into the AI provider for a synthesized summary; a simple 1-hour cache on fetched pages avoids duplicate fetches during iterative conversations on the same topic.
**Data flow:** query → search API → ranked URLs → `trafilatura` extraction per URL → combined clean text → `ai_provider.generate()` for synthesis → Roman Urdu/English summary returned to Dani.
**Known risks / edge cases:** Must check robots.txt before scraping and never fetch content behind login walls — this is both an ethical/legal boundary and a practical one (authenticated pages usually won't extract cleanly anyway).

### `skills/calendar_reminders/`
**Status:** SPEC
**Purpose:** Alarms, reminders, and the scheduling backbone (`apscheduler`) that other skills piggyback on for scheduled actions — YouTube upload scheduling, TikTok post scheduling, WhatsApp scheduled messages, and the P1 daily/weekly digest.
**Depends on:** `apscheduler`, `memory_db.py` (persists alarms across restarts).
**Exposes:** `create_alarm()`, `create_reminder()`, `list_upcoming()`, `schedule_job(fn, run_at)`
**Internal structure:** `alarms` table in `memory_db.py` stores every scheduled job (time, message/callback reference, repeat rule); on boot, `skill_loader.py` reloads all future-dated rows and re-registers them with `apscheduler` — this is what makes scheduling survive a JARVIS restart.
**Data flow:** Any skill needing a scheduled action calls `schedule_job(fn, run_at)` rather than implementing its own timer — this is the single scheduling backbone referenced by youtube_automation, tiktok_automation, and whatsapp_automation.
**Known risks / edge cases:** If JARVIS is offline when a scheduled time passes (laptop shut down), the reload-on-boot logic needs a policy for missed jobs — fire immediately on next boot, or skip and notify Dani it was missed? This should be an explicit, documented decision, not accidental behavior.

### `skills/trading_data/`
**Status:** LIVE (read-only MT5 integration) — router-wrapping is SPEC
**Purpose:** XAUUSD price, positions, account summary from MT5. Foundation for P1 multi-account support and P2 EA performance analytics (`trade_history` table).
**Depends on:** MetaTrader5 Python package, running MT5 terminal.
**Exposes:** `get_price()`, `get_positions()`, `get_account_summary()`, (planned) `get_trade_history(ea_name, range)`
**Config:** `MT5_LOGIN=`, `MT5_PASSWORD=`, `MT5_SERVER=`
**Internal structure:** Currently a direct polling wrapper around the MetaTrader5 Python API; the planned `trade_history` extension adds a write path (logging each closed trade) alongside the existing read-only live-data path — these should stay clearly separated so the read-only guarantee on live account access isn't accidentally weakened.
**Data flow:** MT5 terminal (local) → MetaTrader5 Python API → `trading_data` functions → consumed by `documents` (reports), `youtube_automation`/digest (P1), and directly by voice queries.
**Known risks / edge cases:** This module intentionally has no auto-trading/order-placement capability — that boundary should stay explicit in code (no `place_order()` function exists) so no future skill can accidentally wire up live trade execution through this module without a very deliberate, separate decision.

### `skills/image_search/`
**Status:** SPEC
**Purpose:** Reference images for YouTube thumbnails, Facebook posts, and general "X kaisa dikhta hai" queries.
**Depends on:** Unsplash API / Pexels API (existing keys, reused from AstroTalk and YouTube B-roll pipeline).
**Exposes:** `search_images(query, count)`
**Config:** `UNSPLASH_API_KEY=`, `PEXELS_API_KEY=`
**Internal structure:** Thin wrapper — no local storage of images beyond what's needed for the immediate task (thumbnail generation, B-roll); results are URLs/temp downloads, not a persistent local image library.
**Data flow:** query → API call → ranked image results → either shown to Dani directly, or piped into `youtube_automation`'s thumbnail step / `communication/facebook` posting.
**Known risks / edge cases:** Reused API keys from AstroTalk/YouTube B-roll pipeline mean rate limits are shared across those use-cases — worth tracking combined usage against the free/paid tier limits of whichever provider is active.

### `skills/communication/whatsapp/`
**Status:** LIVE (bridge + whitelist auto-reply) — outbound "pat message" extension is SPEC
**Purpose:** whatsapp-web.js Node bridge with fuzzy contact matching, language-detecting whitelist auto-reply, and rate limiting. See `skills/whatsapp_automation/` for the outbound-send extension.
**Depends on:** Node.js `whatsapp-web.js`, local IPC channel to Python core.
**Exposes:** (existing) auto-reply handling; (new, spec'd) `send_message()`, `send_media()`, `broadcast()`
**Internal structure:** Node process runs as a persistent child process of the Python core, communicating over a local socket/HTTP JSON protocol; existing message types handle inbound (auto-reply), new outbound message types (`SEND_TEXT`, `SEND_MEDIA`, `BROADCAST`) are added to the same protocol rather than a second bridge (see `whatsapp_automation` below).
**Data flow:** Inbound: WhatsApp Web session → Node bridge → Python core → language detection + whitelist check → AI-generated reply → back through bridge → sent. Outbound (new): Python core → `SEND_TEXT`/`SEND_MEDIA` message → Node bridge → WhatsApp Web session → delivery-status ticks read back.
**Known risks / edge cases:** WhatsApp Web sessions can silently log out (QR expired, phone disconnected) — both inbound auto-reply and outbound sends need to detect this state and surface it clearly (`get_session_status()` in the automation extension) rather than queuing messages that will never send.

### `skills/communication/facebook/`
**Status:** LIVE
**Purpose:** Facebook Graph API page posting — text/link/photo/video, insights.
**Depends on:** Facebook Graph API access token.
**Exposes:** `post(content_type, content)`, `get_insights()`
**Config:** `FB_PAGE_ACCESS_TOKEN=`, `FB_PAGE_ID=`
**Internal structure:** Direct Graph API wrapper — no separate state machine needed since Facebook posts are typically single-step (unlike the multi-stage YouTube/TikTok pipelines).
**Data flow:** content (text/media) → Graph API POST → post ID returned → optionally tracked for later `get_insights()` calls.
**Known risks / edge cases:** Facebook access tokens expire — this module should detect an expired-token error distinctly and alert Dani to re-authenticate, same pattern as the YouTube OAuth2 refresh-failure handling.

### `skills/communication/youtube/` (AutoTube Pro pipeline)
**Status:** LIVE — formalizing as a router skill (`youtube_automation/`) is SPEC
**Purpose:** Full pipeline — trend research → AI script → edge-tts → Pexels B-roll → captions → music → thumbnail → OAuth2 upload with confirm-publish.
**Depends on:** YouTube Data/Analytics APIs (OAuth2), Pexels API, `ai_provider.py`, `tts_stt.py`.
**Exposes:** (existing) pipeline trigger; (new, spec'd) full state-machine tracking — see `youtube_automation/` below.
**Config:** `YOUTUBE_CLIENT_ID=`, `YOUTUBE_CLIENT_SECRET=`, `YOUTUBE_REFRESH_TOKEN=`
**Internal structure:** This is the underlying pipeline logic (script→voiceover→broll→captions→music→render→thumbnail→upload); `youtube_automation/` wraps it with the state machine, retry logic, and router visibility rather than replacing it.
**Data flow:** See `youtube_automation/` entry below for the full state-machine data flow — this module is the set of stage-implementations the state machine calls into.
**Known risks / edge cases:** See section 9.3 of the skills master-prompt for the full per-stage failure-handling breakdown (trend research fallback, script validation, TTS retry, B-roll query widening, render error surfacing, OAuth2 refresh, quota handling).

### `skills/memory/`
**Status:** SPEC
**Purpose:** Formalizes `memory_db.py` as a discoverable, router-visible skill so other skills can read/write context uniformly (e.g. browser_automation remembering a logged-in session).
**Depends on:** `memory_db.py`.
**Exposes:** `remember()`, `recall()`, `search_memory()`
**Internal structure:** Thin skill-interface wrapper around `memory_db.py` — no new storage logic, just makes the existing memory system addressable through the same `handler.execute()` pattern as every other skill, so it's discoverable by the router like anything else.
**Data flow:** Any skill needing arbitrary key-value context storage (not one of the dedicated tables like `youtube_jobs`) goes through this skill's `remember()`/`recall()` rather than reaching into `memory_db.py` directly — keeps a consistent access pattern.
**Known risks / edge cases:** As more skills store more context, `search_memory()`'s current keyword-search approach may need to become semantic (embedding-based) to stay useful — noted as an explicit "if needed later" escape hatch rather than over-building this upfront.

### `skills/youtube_automation/`
**Status:** SPEC (full detail in skills master-prompt, section 9)
**Purpose:** Router-visible wrapper around the existing YouTube pipeline with a full persisted state machine (`youtube_jobs` table), per-stage error handling/retry, quota checks, and analytics.
**Depends on:** `skills/communication/youtube/` (underlying pipeline), `calendar_reminders` (scheduled upload), `memory_db.py` (job state persistence).
**Exposes:** `trigger_full_pipeline()`, `check_pipeline_status()`, `retry_failed_job()`, `cancel_job()`, `schedule_upload()`, `get_channel_analytics()`, `list_recent_jobs()`
**Internal structure:** `youtube_jobs` table tracks every job through the explicit state list (QUEUED → RESEARCHING_TREND → ... → PUBLISHED/FAILED); a background worker (thread pool or polled job queue) processes stage transitions asynchronously so the main voice loop never blocks on a multi-minute render.
**Data flow:** `trigger_full_pipeline(topic)` creates a job row → background worker advances it stage by stage, calling into `skills/communication/youtube/` for the actual work at each stage → `check_pipeline_status()` reads current state for voice queries → on restart, `skill_loader.resume_incomplete_jobs()` picks up any job not in a terminal state.
**Known risks / edge cases:** See section 9.3 of the skills master-prompt for the complete per-stage error/retry matrix — this is the most operationally complex module in the system and the state machine design specifically exists to prevent silent failures at any of its 10+ stages.

### `skills/tiktok_automation/`
**Status:** PLANNED (design in skills master-prompt, section 10)
**Purpose:** Short-form video pipeline — repurpose YouTube renders (ffmpeg vertical crop) or generate native shorts, post via Content Posting API (draft-mode default) or browser fallback.
**Depends on:** `ffmpeg`, `skills/youtube_automation/` (for repurpose-mode source content), `browser_automation` (fallback posting), TikTok Content Posting API credentials (if approved).
**Exposes:** `repurpose_for_tiktok()`, `generate_native_short()`, `post_video()`, `get_analytics()`
**Config:** `TIKTOK_MAX_POSTS_PER_DAY=`, `TIKTOK_AUTO_PUBLISH=false`
**Internal structure:** Mirrors the YouTube state machine pattern but in its own `tiktok_jobs` table (QUEUED → SCRIPT → VOICEOVER → BROLL → RENDER → CAPTION_BURN → READY_FOR_REVIEW → POSTED/DRAFTED) — deliberately consistent with the YouTube pattern so the same background-worker/resume-on-restart infrastructure can be reused rather than building a second bespoke system.
**Data flow:** Repurpose mode: existing `youtube_jobs` render → ffmpeg crop/reframe → caption reposition → `tiktok_jobs` READY_FOR_REVIEW. Native mode: independent script→voiceover→broll→render pipeline at vertical aspect ratio from the start.
**Known risks / edge cases:** TikTok's Content Posting API requires app review for direct public posting — until approved, this module defaults to draft-mode uploads (or browser-automation staging short of the final "Post" click) rather than assuming direct-publish capability exists. This is a hard platform constraint, not a design choice that can be worked around.

### `skills/whatsapp_automation/`
**Status:** SPEC (full detail in skills master-prompt, section 11)
**Purpose:** Outbound messaging extension on top of the existing WhatsApp bridge — direct send, scheduled send, media send, broadcast — with delivery confirmation and contact disambiguation.
**Depends on:** `skills/communication/whatsapp/` (bridge), `calendar_reminders` (scheduled send).
**Exposes:** `resolve_contact()`, `send_message()`, `send_scheduled_message()`, `send_media()`, `broadcast()`, `get_session_status()`
**Config:** `WHATSAPP_MAX_BROADCAST=10`
**Internal structure:** Adds new message types (`SEND_TEXT`, `SEND_MEDIA`, `BROADCAST`) to the existing Node bridge protocol rather than building a second bridge process; scheduling piggybacks entirely on `calendar_reminders`'s `apscheduler` rather than implementing its own timer logic.
**Data flow:** `send_message(contact, message)` → `resolve_contact()` fuzzy-matches against known contacts (disambiguates if multiple matches) → bridge `SEND_TEXT` call → waits for delivery-tick status → returns real delivery result, not fire-and-forget.
**Known risks / edge cases:** This is one of the highest-guardrail modules in the system — non-whitelisted-contact sends require confirmation every time, broadcast is capped, and rate limiting is shared with the existing auto-reply limiter specifically to prevent any code path (bug or otherwise) from turning JARVIS into a spam vector on Dani's own WhatsApp account.

### `skills/system_control/`
**Status:** PLANNED (design in skills master-prompt, section 12)
**Purpose:** Local OS control — volume, brightness, folder/file management, app launch/kill, power actions, screenshots, screen lock.
**Depends on:** `pycaw` (volume), `screen-brightness-control`, `psutil`, `pyautogui`.
**Exposes:** `volume_up()`, `volume_down()`, `set_volume()`, `mute()`, `brightness_set()`, `create_folder()`, `delete_item()`, `open_app()`, `close_app()`, `lock_screen()`, `shutdown()`, `restart()`, `take_screenshot()`
**Internal structure:** Flat function set, no persistent state needed beyond the audit log — each function is a direct, synchronous OS call with no async/queued behavior (unlike the multi-stage pipelines above).
**Data flow:** voice command → direct OS-level function call → immediate result/confirmation spoken back; irreversible actions (`shutdown()`, `restart()`, `delete_item()`) route through `pending_confirmations` first regardless of any `.env` auto-approve setting.
**Known risks / edge cases:** This module runs with the same OS-user privileges as JARVIS itself and should never attempt privilege escalation, registry edits, or system file access — every action here is a real, immediate, often irreversible change to Dani's actual machine, so this is the module where the "fail loud, confirm before consequence" principle (from IDEAS.md guiding principles) matters most.

---

## Cross-cutting infrastructure (not modules themselves, but shared by all)

### `skill_log` table
**Status:** SPEC (P0 #2 in ideas roadmap)
**Purpose:** Universal audit trail — every skill action logged with timestamp, params, result, success/failure.
**Used by:** Every skill, via a shared `@logged_action` decorator applied at the router level.

### `pending_confirmations` table
**Status:** SPEC (P0 #4 in ideas roadmap)
**Purpose:** Single queue for anything requiring Dani's explicit approval before executing.
**Used by:** Any skill action with `requires_confirmation: true` in its manifest.

### `usage_log` table
**Status:** PLANNED (P1 #4 in ideas roadmap)
**Purpose:** API cost/token/quota tracking per provider and skill.
**Used by:** `ai_provider.py`, `youtube_automation` (quota units), `tts_stt.py` (character counts).

---

## Module status summary

| Status | Count | Modules |
|---|---|---|
| LIVE | 8 | main.py, memory_db.py, ai_provider.py, tts_stt.py, trading_data, whatsapp (bridge), facebook, youtube (pipeline) |
| PARTIAL | 1 | dashboard.py |
| SPEC | 9 | router.py, skill_loader.py, browser_automation, documents, web_research, calendar_reminders, image_search, memory, youtube_automation, whatsapp_automation |
| PLANNED | 3 | tiktok_automation, system_control, cross-cutting tables (skill_log, pending_confirmations, usage_log) |

---

## Maintenance note

Update this file whenever:
- A module moves between status categories (e.g. SPEC → LIVE once built).
- A new module/skill is added to the system.
- A module's dependencies or exposed interface changes.

Keeping this in sync with `JARVIS_SKILLS_MASTER_PROMPT.md` and `IDEAS.md` means all three documents together give a complete picture: **what exists (MODULES.md), how to build what's missing (skills master-prompt), and what's next (IDEAS.md).**
