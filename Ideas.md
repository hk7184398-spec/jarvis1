# JARVIS — Ideas & Roadmap

> A living document of feature ideas, improvements, and long-term direction for JARVIS. Organized by priority horizon so it's easy to decide what to build next vs. what to park for later.

---

## How to use this file

- **P0 — Now:** high value, low-medium effort, unblocks other work. Build next.
- **P1 — Next:** valuable but either bigger effort or depends on P0 work landing first.
- **P2 — Later:** good ideas, not urgent — revisit once core system is stable.
- **P3 — Exploratory:** interesting but speculative, needs a spike/prototype before committing.

Move items between sections as priorities shift. Strike through (`~~like this~~`) or move to a `## Done` section at the bottom once shipped, so this file also doubles as a lightweight changelog of what JARVIS has grown into.

---

## P0 — Now

### 1. Unified skills router
**Why:** Right now capabilities are scattered special-case code paths. A single router makes every capability discoverable, testable, and consistently gated — one place decides "which skill handles this," instead of that logic being duplicated per-feature.
**How:** Per the skills master-prompt spec — `skill_loader.py` scans `skills/` at boot, parses each `SKILL.md` frontmatter (`triggers`, `requires_confirmation`, `cost`), builds a match index. `router.py` takes parsed intent from Gemini Live/Claude, matches against triggers, falls back to an LLM classification call if confidence is low.
**Depends on:** Nothing — this is the foundation everything else below builds on.
**Done when:** Every existing capability (WhatsApp, MT5, YouTube, Facebook) is reachable only through the router, not hardcoded if/else chains in the main loop.

### 2. Central `skill_log` audit table
**Why:** Trust requires visibility. If Dani asks "aaj tumne kya kiya," JARVIS should have a real, queryable answer — not a guess based on chat history.
**How:** One SQLite table: `skill_log(id, timestamp, skill_name, action, params_json, result, success, error_message)`. Every `handler.execute()` call wraps itself with a log-entry write on both success and failure — make this a decorator (`@logged_action`) applied uniformly by the router, so individual skills don't need to remember to log themselves.
**Depends on:** Unified skills router (needs a single call-point to wrap with logging).
**Done when:** "jarvis, aaj ke saare actions dikhao" returns a real, accurate list pulled from this table.

### 3. Session/health dashboard
**Why:** Right now, knowing whether WhatsApp is connected, MT5 is connected, or a video job is stuck probably requires asking each module individually. One glance should answer all of it.
**How:** A simple local page (Flask/FastAPI + a static HTML page, or a tkinter panel if staying desktop-native) that polls each skill's `get_status()` method (add this method to every skill's interface) every few seconds: WhatsApp bridge connected?, MT5 connected?, last YouTube/TikTok job + stage, any pending confirmations.
**Depends on:** Unified skills router (needs `get_status()` as a standard interface method every skill implements).
**Done when:** Dani can glance at one screen and know the full system state without asking JARVIS anything.

### 4. Pending-confirmation queue
**Why:** Right now, each skill that needs Dani's approval ("publish kar doon?", "shutdown karun?") probably improvises its own ask-and-wait pattern. A single queue makes this consistent and makes it impossible for a confirmation prompt to get lost or ignored.
**How:** A `pending_confirmations` table (`id, skill_name, action_description, params_json, created_at, expires_at, status`). Any skill call with `requires_confirmation: true` writes here instead of directly acting, and the router surfaces "Dani, ye pending hai: [description]" either via voice or the dashboard. Dani's yes/no resolves the row and either executes or discards the queued action.
**Depends on:** Unified skills router.
**Done when:** No skill implements its own ad-hoc confirmation logic — all of them go through this one queue.

### 5. Graceful degradation on API failures
**Why:** A silent hang or crash on an API failure (Gemini down, YouTube quota hit, MT5 disconnected) is the difference between "JARVIS is reliable" and "JARVIS sometimes just stops working and I don't know why."
**How:** Audit every external API call site. Each one needs: a timeout, a defined retry strategy (exponential backoff, max N attempts), and — critically — a defined fallback behavior or a clear spoken/logged error instead of an unhandled exception. Wrap risky calls in a shared `safe_api_call()` helper that standardizes this pattern.
**Depends on:** Nothing — can start immediately, independent of the other P0 items.
**Done when:** Every external API call in the codebase has been audited and passes through the shared retry/fallback wrapper.



---

## P1 — Next

### 1. Voice interruption / barge-in
**Why:** Waiting for JARVIS to finish a long TTS response before giving a new command feels slow and unnatural for a daily-driver assistant — real conversation involves interrupting.
**How:** Run TTS playback in a way that can be cancelled mid-stream (chunk-based playback rather than one long blocking call), and keep the mic hot-listening during playback for a wake-phrase or any speech that should trigger an interrupt. On detected interrupt: stop current audio, discard the rest of the queued response, and immediately start processing the new input.
**Depends on:** Nothing new — mostly a change to the existing TTS/audio-playback loop.
**Done when:** Dani can speak over JARVIS mid-sentence and have it stop and listen immediately.

### 2. Daily/weekly digest
**Why:** Turns JARVIS from purely reactive ("only answers what I ask") to proactive ("tells me what I need to know without being asked") — the single highest-leverage upgrade for making it feel like a real assistant rather than a command tool.
**How:** A scheduled job (via the `calendar_reminders` skill's `apscheduler`) that runs once daily/weekly, pulls from: `trading_data` (P&L summary), `youtube_automation`/`tiktok_automation` (recent job outcomes + analytics), `skill_log` (any failures needing attention), calendar (upcoming items). Compiles into one short spoken or WhatsApp-delivered summary — keep it to the few things that actually need Dani's attention, not a dump of everything.
**Depends on:** `skill_log` (P0 #2), trading_data skill, youtube/tiktok automation skills.
**Done when:** Dani receives one digest per day/week without asking, and it's genuinely useful (not noise).

### 3. Cross-skill workflows ("macros")
**Why:** Right now, a request like "trading report bana ke WhatsApp pe bhej do" requires Dani to either ask in two separate steps or JARVIS to have that exact combo hardcoded. A general workflow system lets any skill's output feed into any other skill's input.
**How:** A simple workflow definition: an ordered list of `(skill, action, param_mapping)` steps where each step's output can be referenced by the next step's params (e.g. `documents.generate_report() -> file_path` feeds into `whatsapp_automation.send_media(file_path=...)`). Start with a small hardcoded set of common workflows (report→WhatsApp, video→TikTok repurpose→post) before building a fully generic workflow engine — validate the pattern is useful before over-engineering it.
**Depends on:** Unified skills router (P0 #1), and at least two skills worth chaining (documents + whatsapp_automation already exist in spec).
**Done when:** At least 2–3 common multi-step requests work as a single spoken command instead of Dani chaining them manually.

### 4. Cost/usage tracking dashboard
**Why:** API costs (Claude/OpenAI/Gemini tokens, TTS characters, YouTube quota units) can add up invisibly — better to see burn rate proactively than discover it on a bill.
**How:** Every API call site logs estimated cost (token count × known price, or quota units consumed) to a `usage_log` table, tagged by provider and skill. Dashboard (extends the P0 health dashboard) shows daily/weekly spend per provider, with a configurable alert threshold (`.env: DAILY_COST_ALERT_USD=`).
**Depends on:** Session/health dashboard (P0 #3) as the display surface.
**Done when:** Dani can see today's/this week's spend broken down by provider without checking each provider's own billing page.

### 5. Multi-account trading support
**Why:** If Dani ever runs demo + live, or multiple brokers, the current single-connection assumption in `trading_data` breaks down.
**How:** Refactor `trading_data` skill functions to accept an optional `account_id` param (default to a configured primary account for backward compatibility), with account configs (broker, login, server) stored in `.env` or a small config table rather than hardcoded.
**Depends on:** Existing trading_data skill (no new dependency, just a refactor).
**Done when:** Dani can ask "demo account ka balance batao" vs "live account ka balance batao" and get correctly scoped answers.

### 6. Content calendar view
**Why:** Juggling "what's scheduled on YouTube," "what's scheduled on TikTok," and "what's scheduled on Facebook" as three separate questions is annoying — one view is simpler.
**How:** A generated weekly table (could be a simple auto-refreshed section on the health dashboard, or a periodically regenerated image/HTML snippet) pulling `scheduled_at` from `youtube_jobs`, `tiktok_jobs`, and the Facebook posting module's own schedule store.
**Depends on:** YouTube automation (schedule_upload), TikTok automation (post scheduling), existing Facebook module.
**Done when:** One glance answers "is hafte kya kya schedule hai across all platforms."



---

## P2 — Later

### 1. Local LLM fallback
**Why:** Cloud API downtime or cost pressure shouldn't fully block JARVIS. Cheap/low-stakes decisions (like intent routing) don't need top-tier reasoning — save the paid API calls for tasks that actually need them.
**How:** Run a small model locally via Ollama (e.g. a 7-8B instruction-tuned model). Use it specifically for router intent classification and simple confirmations ("did the user say yes or no"), not for creative/complex tasks like script generation, which stay on cloud APIs.
**Depends on:** Unified skills router (needs a defined classification interface to swap the backend behind).
**Done when:** Router can fall back to local classification when cloud APIs are unavailable, without the whole assistant becoming unusable.

### 2. EA performance analytics layer
**Why:** Right now, comparing NEMESIS/APEX_VELOCITY_SCALP/ProfessionalTradingSystem performance is probably anecdotal ("EA X feels better lately"). A real data layer makes strategy decisions evidence-based.
**How:** Extend `trading_data` skill to log every trade (entry/exit price, EA name, mode, P&L, timestamp) to a dedicated `trade_history` table, separate from the live read-only MT5 polling. Build simple aggregate queries (win rate, average R:R, drawdown by EA) that JARVIS can answer on request.
**Depends on:** trading_data skill (extends it, no new external dependency).
**Done when:** "jarvis, NEMESIS ka is mahine ka win rate batao" returns a real computed answer, not a guess.

### 3. Smarter content repurposing
**Why:** Manually picking which YouTube video to repurpose for TikTok is extra cognitive load — the analytics data already exists to make this decision automatically.
**How:** A scheduled check (weekly) against `youtube_jobs` + analytics data, identifying the best-performing recent video (by views/watch-time), then proactively suggesting it as a TikTok repurposing candidate via the digest (P1 #2) rather than auto-repurposing without asking.
**Depends on:** YouTube automation analytics (section 9.2 `get_channel_analytics`), daily/weekly digest (P1 #2).
**Done when:** The digest includes a "this video might be worth repurposing" suggestion automatically.

### 4. Contact-aware WhatsApp tone
**Why:** The existing auto-reply system already does language detection — extending it to tone/formality per contact makes replies feel appropriately different for family vs. trading-group vs. business contacts, rather than one-size-fits-all.
**How:** Add a `contact_profiles` table (`contact_id, formality_level, notes`) that the auto-reply prompt-builder reads before generating a reply, adjusting the system prompt's tone instructions per contact.
**Depends on:** Existing WhatsApp auto-reply module (extends it).
**Done when:** Replies to different contact categories are noticeably and appropriately different in tone.

### 5. Mobile companion notifications
**Why:** Critical alerts (job failed, WhatsApp session logged out, a large trade triggered) are useless if Dani only sees them when he's back at the laptop.
**How:** Zero-extra-infra approach: reuse the existing WhatsApp module to have JARVIS message Dani's own number directly for critical alerts — no new push infrastructure needed, works anywhere Dani has WhatsApp.
**Depends on:** WhatsApp automation `send_message` (already in spec).
**Done when:** Dani reliably gets critical alerts on his phone within seconds of the triggering event.

### 6. Plugin/skill marketplace pattern
**Why:** The `SKILL.md` manifest system already sets up most of what's needed for this — formalizing it further (versioning, dependency declarations) means new skills can be dropped in without touching core code at all.
**How:** Extend the `SKILL.md` frontmatter with `version`, `dependencies` (other skill names or Python packages), and a simple compatibility check in `skill_loader.py` that warns (rather than crashes) if a dropped-in skill's dependencies aren't met.
**Depends on:** Unified skills router (P0 #1) — this is a natural extension of it, not urgent until the core system is stable.
**Done when:** Dani (or a future collaborator) can add a new skill folder and have it "just work" without editing router/loader code.



---

## P3 — Exploratory

### 1. Vision-based screen understanding
**Why:** The browser automation skill's accessibility-tree snapshot approach works for structured web pages, but can't react to arbitrary on-screen content like a live MT5 chart or a video frame.
**How:** Combine periodic screenshots with a vision-capable model call, used sparingly (this is expensive per-call) — e.g. only on explicit request ("is chart pe kya pattern dikh raha hai") rather than continuous monitoring.
**Risk/considerations:** Cost per call is much higher than text-only reasoning; needs a spike to validate accuracy before committing to any workflow depending on it.

### 2. Autonomous EA tuning loop
**Why:** Could theoretically improve EA performance over time without manual parameter tweaking.
**How:** A supervised loop where JARVIS analyzes recent trade_history (P2 #2) and proposes specific parameter adjustments, but this should propose only — never apply automatically.
**Risk/considerations:** High risk if done carelessly — a bad auto-applied parameter change on a live trading account could cause real financial loss. This idea should stay research/proposal-only indefinitely unless there's a very strong case (and probably a demo-account-only testing period) before ever touching live parameters.

### 3. Multi-modal trading alerts
**Why:** Price action alone misses context that news/sentiment provides — a combined signal could be more informative than either alone.
**How:** Combine `trading_data` price signals with `web_research` skill's news/sentiment fetching into a single composite alert format, rather than treating them as two separate things Dani has to mentally combine himself.
**Risk/considerations:** Needs careful validation that the composite signal is actually more useful than the two separate ones — easy to build something that looks sophisticated but doesn't improve decisions.

### 4. Personality/voice customization
**Why:** A single fixed personality doesn't fit every context — formal when drafting a client message, casual Roman Urdu banter otherwise.
**How:** Configurable personality modes selectable per context (could be automatic based on which skill is active, or explicit "jarvis, formal mode" toggle), affecting system prompt tone instructions.
**Risk/considerations:** Low risk, mostly a prompt-engineering exercise — good candidate to promote to P2 once core P0/P1 work is done, since it's relatively low effort.

### 5. Self-healing skill errors
**Why:** Right now, a repeated failure (e.g. edge-tts rate limiting) probably just logs and repeats silently. A diagnosis layer could tell Dani what's actually wrong.
**How:** Pattern-match repeated error signatures in `skill_log` against a small known-issues table ("this error pattern usually means X"), surfacing a plain-language diagnosis instead of a raw stack trace.
**Risk/considerations:** Start with a small hand-curated pattern list (not a full ML anomaly-detection system) — most value comes from catching the handful of errors that recur most often.



---

## Guiding principles (keep these in mind for every new idea added here)

1. **Confirmation before consequence.** Anything irreversible or externally visible (publish, send, delete, shutdown) stays behind explicit confirmation, no matter how "smart" JARVIS gets.
2. **Fail loud, not silent.** Every new feature should have a clear, Dani-visible failure mode — no swallowed exceptions, no jobs that quietly die.
3. **Single source of truth for state.** New features should extend the existing SQLite memory/job-state pattern rather than inventing parallel state stores.
4. **Roman Urdu/English mixed UX stays default.** Any new command surface (voice, WhatsApp, dashboard) should keep this consistent rather than forcing pure English.
5. **Prefer composition over duplication.** New skills should call into existing ones (documents, memory, calendar) rather than re-implementing similar logic.

---

## Done

_(Move shipped items here as they land, with the date, so this file also tracks JARVIS's growth over time.)_

- Core skills master-prompt spec written (browser automation, documents, web research, calendar/reminders, trading data, image search, communication, memory, YouTube, TikTok, WhatsApp automation, system control).
