# JARVIS — Tasks

> Granular, ordered, checkbox-level build tasks for JARVIS. This file turns `MODULES.md` (what exists), `JARVIS_SKILLS_MASTER_PROMPT.md` (how to build what's missing), and `IDEAS.md` (what's next) into an actual sequenced to-do list. Work top to bottom within each phase — phases are ordered by dependency, not just priority.

---

## How to use this file

- `[ ]` = not started, `[~]` = in progress, `[x]` = done. Update as you go — this file should always reflect real current state.
- Each task lists its **file(s)**, what **done** looks like, and any **blocked by** dependency.
- Tasks are deliberately small — if a task feels like more than a few hours of work, it should probably be split further before starting.
- Phases are sequential (Phase 1 mostly needs Phase 0 done first), but within a phase, unrelated tasks can be done in parallel.

---

## Phase 0 — Foundation (blocks everything else)

Nothing in the skills layer works without this. Do this first, completely, before touching any individual skill.

### 0.1 Database schema setup
- [ ] Design and create `skill_log` table: `id, timestamp, skill_name, action, params_json, result, success, error_message`. **File:** `core/memory_db.py` (migration/schema addition). **Done when:** table exists and a manual test insert/query works.
- [ ] Design and create `pending_confirmations` table: `id, skill_name, action_description, params_json, created_at, expires_at, status`. **File:** `core/memory_db.py`. **Done when:** table exists, status transitions (pending→approved/rejected/expired) are enforced.
- [ ] Add a lightweight `schema_version` table + migration runner so future schema changes don't require manual DB surgery. **File:** `core/memory_db.py` + new `migrations/` folder. **Done when:** running the migration runner twice is a no-op (idempotent), and adding a new migration file is picked up automatically.
- [ ] Enable SQLite WAL mode (`PRAGMA journal_mode=WAL`) to reduce write-contention issues as more modules write concurrently. **File:** `core/memory_db.py` connection setup. **Done when:** confirmed via `PRAGMA journal_mode;` returning `wal`.

### 0.2 Skill manifest system
- [ ] Define the final `SKILL.md` YAML frontmatter schema (`name`, `triggers`, `requires_confirmation`, `cost`, `version`, `dependencies`). **File:** new `docs/skill_manifest_spec.md` (reference doc, not code). **Done when:** every field has a documented type and example value.
- [ ] Build `skill_loader.py`: scan `skills/` directory, parse each `SKILL.md`, validate corresponding `handler.py` exports `execute()`. **File:** `core/skill_loader.py`. **Done when:** loader correctly registers a test skill and correctly *rejects* (with a clear log message, not a crash) a deliberately malformed test skill.
- [ ] Build the trigger-matching index (keyword or lightweight embedding-based) used by the router. **File:** `core/skill_loader.py`. **Done when:** given a sample command, the loader returns a ranked list of candidate skills with confidence scores.
- [ ] Add `@logged_action` decorator that wraps any `handler.execute()` call and writes to `skill_log` automatically. **File:** `core/router.py` or a shared `core/decorators.py`. **Done when:** calling any decorated function produces exactly one `skill_log` row per call, on both success and failure paths.

### 0.3 Router
- [ ] Build `router.py`: two-stage matching — fast trigger-index lookup, falls back to LLM classification via `ai_provider.py` if confidence < `ROUTER_CONFIDENCE_THRESHOLD`. **File:** `core/router.py`. **Blocked by:** 0.2 (skill_loader). **Done when:** 5 varied test commands each route to the correct skill, including at least one ambiguous case that correctly triggers the LLM fallback.
- [ ] Implement disambiguation prompting for genuinely ambiguous commands (two skills matched with similar confidence). **File:** `core/router.py`. **Done when:** an ambiguous test command produces a clear clarifying question back to Dani instead of silently picking one skill.
- [ ] Wire `requires_confirmation` enforcement: if a matched skill's manifest says `true`, router writes to `pending_confirmations` instead of executing directly. **File:** `core/router.py`. **Blocked by:** 0.1 (pending_confirmations table). **Done when:** a test skill flagged `requires_confirmation: true` never executes without an approved row in `pending_confirmations`.

### 0.4 Standard skill interface
- [ ] Define and document the standard skill interface every `handler.py` must implement: `execute(params: dict) -> dict`, `get_status() -> dict`. **File:** `docs/skill_interface_spec.md`. **Done when:** the spec includes a minimal example handler.py that passes loader validation.
- [ ] Retrofit `skills/trading_data/` (existing LIVE module) to match the new standard interface. **File:** `skills/trading_data/handler.py`. **Blocked by:** interface spec above. **Done when:** trading_data is loadable and routable through the new router exactly like a brand-new skill.
- [ ] Retrofit `skills/communication/whatsapp/` (existing LIVE module) to match the new standard interface. **File:** `skills/communication/whatsapp/handler.py`. **Done when:** existing auto-reply functionality still works unchanged after the retrofit — this is a wrapping exercise, not a rewrite.
- [ ] Retrofit `skills/communication/facebook/` similarly. **File:** `skills/communication/facebook/handler.py`.
- [ ] Retrofit `skills/communication/youtube/` similarly (wrap only — full state machine comes in Phase 3). **File:** `skills/communication/youtube/handler.py`.

### 0.5 API reliability wrapper
- [ ] Build `safe_api_call()` shared helper: timeout, exponential backoff retry (max N attempts), standardized failure result shape. **File:** new `core/api_utils.py`. **Done when:** a deliberately-failing test call retries the expected number of times then returns a clean error rather than raising an uncaught exception.
- [ ] Audit every existing external API call site (`ai_provider.py`, MT5 connection, WhatsApp bridge, Facebook Graph API, YouTube APIs) and route them through `safe_api_call()`. **Files:** all of the above. **Done when:** a checklist of every audited call site exists and each one is confirmed wrapped (track this as a sub-checklist here as you go).

**Phase 0 exit criteria:** A brand-new dummy skill (e.g. "echo skill" that just repeats input) can be dropped into `skills/`, gets picked up by `skill_loader.py`, is routable via `router.py`, and appears in `skill_log` after being called — all without touching `main.py` or `router.py` code. If this works, the foundation is solid.

---

## Phase 1 — P0 roadmap items (system reliability & visibility)

### 1.1 Health dashboard
- [ ] Add `get_status()` implementation to every LIVE/retrofitted skill (trading_data, whatsapp, facebook, youtube). **Files:** each skill's `handler.py`. **Blocked by:** 0.4.
- [ ] Build dashboard polling loop calling `get_status()` on every loaded skill every 3-5 seconds. **File:** `core/dashboard.py`. **Done when:** dashboard visibly updates when a skill's status changes (test by manually disconnecting MT5 and confirming the dashboard reflects it within one poll cycle).
- [ ] Add pending-confirmations panel to dashboard with approve/reject buttons wired to resolve rows directly. **File:** `core/dashboard.py`. **Blocked by:** 0.1, 0.3. **Done when:** approving a row in the dashboard actually triggers the queued skill execution.

### 1.2 Graceful degradation audit
- [ ] Complete the `safe_api_call()` audit checklist from 0.5 fully — no exceptions.
- [ ] Add explicit partial-startup handling to `main.py`: if MT5 fails to connect at boot, JARVIS still starts with trading_data marked unavailable rather than crashing entirely. **File:** `core/main.py`. **Done when:** killing the MT5 terminal before boot still results in a working JARVIS session (minus trading features, clearly flagged as unavailable).
- [ ] Same partial-startup treatment for WhatsApp bridge failing to connect. **File:** `core/main.py`.

**Phase 1 exit criteria:** Dani can glance at the dashboard and know true system state; killing any one subsystem before boot no longer breaks the whole assistant.

---

## Phase 2 — Core new skills (independent, can parallelize across sessions)

Each of these is independent of the others — pick based on what's most useful right now.

### 2.1 `skills/documents/`
- [ ] Scaffold skill folder + `SKILL.md` manifest (triggers, `requires_confirmation: false` for generation, `true` for anything that emails/sends the doc elsewhere).
- [ ] Implement `generate_pdf()`, `generate_docx()`, `generate_xlsx()`, `generate_pptx()` using `reportlab`/`python-docx`/`openpyxl`/`python-pptx`.
- [ ] Implement `read_document(path) -> text` covering all four formats.
- [ ] Build the trading-report template specifically: pulls from `trading_data.get_positions()` + `get_account_summary()`, renders an equity-curve chart via matplotlib, embeds in DOCX/PDF. **Blocked by:** 0.4 (trading_data retrofit).
- [ ] Test: generate a real trading report end-to-end and manually verify the output file is correct and readable.

### 2.2 `skills/web_research/`
- [ ] Scaffold skill folder + `SKILL.md`.
- [ ] Pick and configure a search API (SerpAPI/Bing/Google Custom Search) — add key to `.env`.
- [ ] Implement `search(query) -> list[result]`.
- [ ] Implement `fetch_and_extract(url) -> clean_text` using `trafilatura`, with robots.txt check before fetching.
- [ ] Implement `research(topic, depth=3) -> summary` orchestrating search → fetch → synthesize via `ai_provider.generate()`.
- [ ] Add 1-hour cache on fetched pages (simple in-memory dict or a `research_cache` table) to avoid duplicate fetches.
- [ ] Test: run a real research query on a gold-market topic and manually verify the summary is accurate and non-hallucinated against the source.

### 2.3 `skills/calendar_reminders/`
- [ ] Scaffold skill folder + `SKILL.md`.
- [ ] Create `alarms` table in `memory_db.py`: `id, time, message, repeat_days, created_at, active`.
- [ ] Implement `create_alarm()`, `create_reminder()`, `list_upcoming()`.
- [ ] Implement `schedule_job(fn, run_at)` as the general-purpose scheduling primitive other skills will call.
- [ ] Wire `apscheduler` boot-time reload: on startup, load all future/active rows from `alarms` and re-register them. **Blocked by:** `skill_loader.resume_incomplete_jobs()` pattern from 0.2.
- [ ] Decide and document the missed-alarm policy (fire immediately on next boot vs. skip-and-notify) — don't leave this undefined.
- [ ] Test: create an alarm, restart JARVIS before it fires, confirm it still fires correctly after restart.

### 2.4 `skills/image_search/`
- [ ] Scaffold skill folder + `SKILL.md`.
- [ ] Implement `search_images(query, count) -> list[image_url]` using existing Unsplash/Pexels keys.
- [ ] Test: query returns valid, relevant image URLs for a sample query.

### 2.5 `skills/browser_automation/`
- [ ] Scaffold skill folder + `SKILL.md`.
- [ ] Build `BrowserSession` singleton with persistent background-thread browser context (not a new browser per command).
- [ ] Implement `open(url)`, `snapshot()`, `click(ref)`, `fill(ref, text)`, `screenshot(path)`.
- [ ] Implement domain allowlist enforcement from `.env` (`BROWSER_ALLOWED_DOMAINS=`) — reject navigation to non-allowlisted domains with a clear message.
- [ ] Add `requires_confirmation: true` gating for form-submit / purchase / content-post actions specifically (not for read-only navigation/scraping).
- [ ] Test: open a real page, take a snapshot, click an element, confirm the accessibility-tree snapshot approach works end-to-end.

### 2.6 `skills/memory/`
- [ ] Scaffold skill folder + `SKILL.md` — thin wrapper only.
- [ ] Implement `remember()`, `recall()`, `search_memory()` as pass-throughs to `memory_db.py`.
- [ ] Test: another skill (e.g. browser_automation storing a logged-in session flag) successfully reads/writes through this skill interface.

**Phase 2 exit criteria:** All six independent skills are LIVE, routable, and individually tested. None of them yet talk to each other in a workflow (that's Phase 4).

---

## Phase 3 — Content pipelines (higher complexity, build after Phase 2)

### 3.1 `skills/youtube_automation/` — state machine wrapper
- [ ] Create `youtube_jobs` table: `id, topic, stage, percent_complete, created_at, updated_at, scheduled_at, failure_stage, error_message, retry_count`.
- [ ] Implement state transitions exactly matching the sequence in skills master-prompt section 9.1 (QUEUED → ... → PUBLISHED/FAILED), each transition timestamped.
- [ ] Implement `trigger_full_pipeline(topic, target_length_sec)` — creates job row, kicks off background worker (ThreadPoolExecutor or polled queue).
- [ ] Implement `check_pipeline_status(job_id=None)` — returns stage/percent/eta/last_error, defaults to most recent active job.
- [ ] Implement `retry_failed_job(job_id)` — resumes from `failure_stage`, not full restart.
- [ ] Implement `cancel_job(job_id)` — stops pipeline, cleans up partial temp files.
- [ ] Implement `schedule_upload(job_id, datetime)` — integrates with `calendar_reminders.schedule_job()`.
- [ ] Implement `get_channel_analytics(range)` via YouTube Analytics API v2, with 30-min cache.
- [ ] Implement `list_recent_jobs(limit)`.
- [ ] Implement per-stage error handling exactly per section 9.3 of the skills master-prompt: trend-research fallback list, script length validation + retry, TTS rate-limit vs network-error distinction, B-roll query widening, ffmpeg stderr capture, OAuth2 silent-refresh-then-alert, quota-exceeded queueing.
- [ ] Implement duplicate-topic guard (check recent job history before starting a very similar new job).
- [ ] Wire `requires_confirmation: true` before private→public publish, with JARVIS reading back title + first line of description.
- [ ] Wire `resume_incomplete_jobs()` in `skill_loader.py` specifically for this table.
- [ ] Test: run a real end-to-end video job from trigger to published, then deliberately kill JARVIS mid-pipeline and confirm it resumes correctly on restart.

### 3.2 `skills/tiktok_automation/`
- [ ] Create `tiktok_jobs` table mirroring the YouTube state pattern (QUEUED → SCRIPT → VOICEOVER → BROLL → RENDER → CAPTION_BURN → READY_FOR_REVIEW → POSTED/DRAFTED).
- [ ] Implement `repurpose_for_tiktok(source_job_id, start_sec, end_sec)` — ffmpeg 16:9→9:16 crop, auto-strongest-segment detection if timestamps omitted, caption reposition/burn-in.
- [ ] Implement `generate_native_short(topic)` — independent short-form script→voiceover→broll→render pipeline at vertical aspect ratio.
- [ ] Investigate and document current TikTok Content Posting API access status (approved vs. not) — this determines which posting path is default.
- [ ] Implement `post_video(video_path, caption, hashtags)` — API draft-mode path if available, else `browser_automation`-based staged-but-not-published fallback.
- [ ] Implement `get_analytics()` via API where available, with a clear "unavailable at current access tier" response otherwise.
- [ ] Wire `requires_confirmation: true` for every post, no exceptions, plus `TIKTOK_MAX_POSTS_PER_DAY` rate limit enforcement.
- [ ] Test: repurpose a real YouTube job into a vertical short and confirm output video quality/framing is acceptable before wiring up posting.

### 3.3 Wrap `skills/communication/facebook/` fully into router pattern
- [ ] Add `get_status()`.
- [ ] Add `SKILL.md` manifest with proper triggers.
- [ ] Confirm existing `post()`/`get_insights()` functions match the standard `execute(params)` interface (wrap if needed rather than rewrite).

**Phase 3 exit criteria:** A real video can go from "jarvis, ek video bana do" to published on YouTube, and separately can be repurposed and posted (or drafted) to TikTok, entirely through the router with full state tracking and no silent failures anywhere in either pipeline.

---

## Phase 4 — WhatsApp automation & system control

### 4.1 `skills/whatsapp_automation/`
- [ ] Add new outbound message types (`SEND_TEXT`, `SEND_MEDIA`, `BROADCAST`) to the existing Node bridge protocol. **File:** whatsapp-web.js bridge code + Python-side client.
- [ ] Implement `resolve_contact(name_or_number)` reusing existing fuzzy matcher, with explicit disambiguation prompt on multiple matches.
- [ ] Implement `send_message(contact, message)` with real delivery-status wait (not fire-and-forget).
- [ ] Implement `send_scheduled_message(contact, message, datetime)` via `calendar_reminders.schedule_job()`, with failure notification if contact/session invalid at fire time.
- [ ] Implement `send_media(contact, file_path, caption)` with pre-send file-size/existence validation.
- [ ] Implement `broadcast(contact_list, message)` — individual sends per contact (not native broadcast-list), returns per-contact result map.
- [ ] Implement `get_session_status()` — proactive check before any send attempt.
- [ ] Wire non-whitelisted-contact confirmation requirement (read back contact + message before sending).
- [ ] Wire shared rate limiter reuse from existing auto-reply module (per-contact and global caps apply to outbound sends too).
- [ ] Wire `WHATSAPP_MAX_BROADCAST` cap enforcement.
- [ ] Test: send a real message to a whitelisted contact and confirm actual delivery-tick status is correctly reported back, not assumed.

### 4.2 `skills/system_control/`
- [ ] Scaffold skill folder + `SKILL.md`.
- [ ] Implement volume functions: `volume_up()`, `volume_down()`, `set_volume()`, `mute()`, `unmute()` via `pycaw`.
- [ ] Implement brightness functions: `brightness_set()`, `brightness_up()`, `brightness_down()` via `screen-brightness-control`.
- [ ] Implement file/folder functions: `create_folder()`, `create_file()`, `rename_item()`, `delete_item()` (confirmation required) via `os`/`pathlib`.
- [ ] Implement app control: `open_app()`, `close_app()`, `list_running_apps()` via `psutil` + `subprocess`/`os.startfile()`.
- [ ] Implement power/lock actions: `lock_screen()`, `shutdown()`, `restart()`, `sleep()` — all `requires_confirmation: true` unconditionally, hardcoded, not `.env`-overridable.
- [ ] Implement `take_screenshot(save_path)` via `pyautogui`.
- [ ] Wire full action logging to `skill_log` for every system_control call (old value → new value where applicable).
- [ ] Test each function individually on the actual target machine (Windows) — these are OS-specific and need real hardware verification, not just unit tests.
- [ ] Specifically test the confirmation gate on `shutdown()`/`restart()`/`delete_item()` cannot be bypassed by any parameter or config combination.

**Phase 4 exit criteria:** Dani can send a real WhatsApp message and control real laptop settings entirely via voice/text through JARVIS, with every irreversible action correctly gated behind confirmation and every action logged.

---

## Phase 5 — P1 roadmap items (proactive intelligence)

### 5.1 Voice barge-in
- [ ] Refactor `tts_stt.speak()` into chunked synthesis + playback (sentence-level or fixed-duration chunks). **File:** `core/tts_stt.py`.
- [ ] Add cancellation-flag check between chunks.
- [ ] Add hot-mic listening during playback for interrupt detection.
- [ ] Implement `speak_interruptible(text)` as the new default speaking function, replacing blocking `speak()` calls throughout the codebase.
- [ ] Test: interrupt JARVIS mid-sentence with a new command and confirm it stops immediately and processes the new input.

### 5.2 Daily/weekly digest
- [ ] Design digest content selection logic — pull from `trading_data` (P&L), `youtube_automation`/`tiktok_automation` (job outcomes + analytics), `skill_log` (recent failures), `calendar_reminders` (upcoming items).
- [ ] Implement digest compiler that keeps it short — only genuinely actionable items, not a full data dump.
- [ ] Schedule via `calendar_reminders.schedule_job()` for daily and/or weekly cadence (configurable).
- [ ] Choose delivery channel: spoken on next interaction, or proactively via `whatsapp_automation.send_message()` to Dani's own number.
- [ ] Test: run the digest manually and sanity-check that a human would actually find it useful, not noisy.

### 5.3 Cross-skill workflows
- [ ] Design minimal workflow definition format: ordered `(skill, action, param_mapping)` steps with output-to-input referencing.
- [ ] Hardcode and test workflow #1: report generation → WhatsApp send (`documents.generate_pdf()` → `whatsapp_automation.send_media()`).
- [ ] Hardcode and test workflow #2: YouTube video → TikTok repurpose → post (`youtube_automation` → `tiktok_automation.repurpose_for_tiktok()` → `post_video()`).
- [ ] Only after these two work reliably, consider generalizing into a reusable workflow engine — don't over-build this before validating the pattern is useful.

### 5.4 Cost/usage tracking
- [ ] Create `usage_log` table: `id, timestamp, provider, skill_name, tokens_or_units, estimated_cost_usd`.
- [ ] Instrument `ai_provider.py` to log token usage per call.
- [ ] Instrument `youtube_automation` to log quota units consumed per upload.
- [ ] Instrument `tts_stt.py` to log TTS character counts.
- [ ] Add usage summary view to the dashboard (daily/weekly spend by provider).
- [ ] Add configurable alert threshold (`DAILY_COST_ALERT_USD=`) with a notification when exceeded.

### 5.5 Multi-account trading support
- [ ] Refactor `trading_data` functions to accept optional `account_id` param, defaulting to configured primary account.
- [ ] Move account configs (broker, login, server) from single `.env` values to a small `trading_accounts` config table or structured `.env` list.
- [ ] Test: query balance for two distinct configured accounts and confirm correct scoping.

### 5.6 Content calendar view
- [ ] Build a query aggregating `scheduled_at` across `youtube_jobs`, `tiktok_jobs`, and Facebook's schedule store into one unified view.
- [ ] Render as a dashboard section (simple weekly table).
- [ ] Test: schedule items across all three platforms and confirm they all appear correctly in the unified view.

**Phase 5 exit criteria:** JARVIS proactively surfaces useful information (digest) without being asked, chains multi-step requests automatically, and gives Dani full visibility into cost and content scheduling.

---

## Phase 6 — P2/P3 roadmap items (evaluate after Phase 5 is stable)

Do not start these until Phases 0–5 are solid and in daily use — these are enhancements to a working system, not blockers to having one.

- [ ] `Local LLM fallback` — spike an Ollama-backed `BaseProvider` implementation for router intent classification only.
- [ ] `EA performance analytics` — create `trade_history` table, instrument trade logging, build win-rate/drawdown query functions.
- [ ] `Smarter content repurposing` — weekly best-performer detection feeding into the digest as a suggestion.
- [ ] `Contact-aware WhatsApp tone` — `contact_profiles` table + prompt-builder integration.
- [ ] `Mobile companion notifications` — critical alerts via `whatsapp_automation.send_message()` to Dani's own number.
- [ ] `Plugin/skill marketplace pattern` — extend `SKILL.md` with `version`/`dependencies`, add compatibility checking to `skill_loader.py`.
- [ ] `Vision-based screen understanding` — spike only, validate cost/accuracy before any real integration.
- [ ] `Autonomous EA tuning loop` — proposal-only design doc first; do not implement auto-apply logic without a separate, explicit, very deliberate decision.
- [ ] `Multi-modal trading alerts` — combine `trading_data` signals with `web_research` sentiment into one alert format.
- [ ] `Personality/voice customization` — configurable tone modes, mostly a prompt-engineering task.
- [ ] `Self-healing skill errors` — small hand-curated error-pattern-to-diagnosis table, surfaced from `skill_log` pattern matches.

---

## Cross-cutting tasks (ongoing, not phase-bound)

- [ ] Keep `MODULES.md` status column updated as each task above completes (SPEC/PLANNED → LIVE).
- [ ] Keep `IDEAS.md` "Done" section updated as roadmap items ship, with dates.
- [ ] After every phase, do a real end-to-end usage session (not just unit tests) — Dani actually using JARVIS for a day on the newly shipped features, to catch UX issues automated tests won't.
- [ ] Security pass before any phase that touches credentials/tokens/financial data (Phase 3 YouTube OAuth2, Phase 4 WhatsApp/system control) — confirm no secrets are logged in `skill_log` (message hashes only, not full content, per the whatsapp_automation guardrail spec).

---

## Suggested build order summary

```
Phase 0 (Foundation)
   ↓
Phase 1 (Reliability/visibility) ─── can start in parallel with Phase 2
   ↓                                        ↓
Phase 2 (Independent new skills) ──────────┘
   ↓
Phase 3 (Content pipelines: YouTube, TikTok)
   ↓
Phase 4 (WhatsApp automation, System control)
   ↓
Phase 5 (Proactive intelligence: digest, workflows, cost tracking)
   ↓
Phase 6 (P2/P3 enhancements — evaluate case by case)
```
