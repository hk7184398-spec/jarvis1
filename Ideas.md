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

- **Unified skills router** (per the skills master-prompt spec) — single entrypoint so every capability (browser, documents, YouTube, TikTok, WhatsApp, trading, system control) is discoverable and consistently gated by `requires_confirmation`, instead of being scattered special-case code paths.
- **Central `skill_log` audit table** — every action JARVIS takes (message sent, video published, system setting changed) logged with timestamp, params, and result. This is the foundation for trust — Dani should always be able to ask "aaj tumne kya kya kiya" and get a real answer.
- **Session/health dashboard** — one glance (tkinter panel or simple local web page) showing: WhatsApp bridge connected?, MT5 connected?, last YouTube job status, last TikTok job status, any pending confirmations waiting on Dani. Right now these are probably only discoverable by asking individually — this collapses it into one view.
- **Pending-confirmation queue** — a single place where anything flagged `requires_confirmation` sits until Dani approves/rejects, rather than each skill improvising its own "ask and wait" pattern. Makes the whole system's guardrails consistent and easy to reason about.
- **Graceful degradation on API failures** — every external API call (Gemini, Claude, OpenAI, YouTube, MT5) should have a defined fallback or clear failure message, never a silent hang. Worth an audit pass across existing modules.

---

## P1 — Next

- **Voice interruption / barge-in** — ability for Dani to interrupt JARVIS mid-response with a new command, instead of waiting for TTS to finish. Big usability upgrade for a daily-driver assistant.
- **Daily/weekly digest** — a scheduled voice or WhatsApp summary: trading account P&L, YouTube/TikTok performance, any failed jobs needing attention, upcoming calendar items. Turns JARVIS from reactive to proactive.
- **Cross-skill workflows** — e.g. "trading report bana ke WhatsApp pe bhej do" should chain `trading_data` → `documents` → `whatsapp_automation` automatically, rather than Dani manually invoking each step. Worth designing a simple workflow/macro system once individual skills are solid.
- **Cost/usage tracking dashboard** — running tally of API spend (Claude/OpenAI/Gemini tokens, TTS characters, YouTube quota units) so Dani can see burn rate at a glance instead of finding out from a billing surprise.
- **Multi-account trading support** — if Dani ever runs more than one MT5 account (e.g. demo + live, or multiple brokers), the trading_data skill should support named accounts rather than assuming a single connection.
- **Content calendar view** — a simple visual (even just a generated weekly table) showing what's queued/scheduled across YouTube + TikTok + Facebook, so Dani isn't juggling three separate "what's scheduled" questions.

---

## P2 — Later

- **Local LLM fallback** — a small local model (e.g. via Ollama) as a fallback path when cloud APIs are down or for cheap/low-stakes intent classification (routing decisions), reserving paid API calls for tasks that actually need top-tier reasoning.
- **EA performance analytics layer** — beyond raw MT5 read access, build a lightweight backtesting/performance-tracking layer that logs each EA's (NEMESIS, APEX_VELOCITY_SCALP, ProfessionalTradingSystem) live performance over time, so strategy comparisons are data-driven rather than anecdotal.
- **Smarter content repurposing** — auto-detect the best-performing YouTube video each week (via analytics) and auto-suggest it as a TikTok repurposing candidate, instead of Dani manually picking.
- **Contact-aware WhatsApp tone** — let the auto-reply system adjust tone/formality per contact (already has language detection; extend with a per-contact style profile) so replies to family vs. trading-group vs. business contacts feel appropriately different.
- **Mobile companion notifications** — push critical alerts (job failed, session logged out, large trade triggered) to Dani's phone even when he's away from the laptop — could piggyback on the existing WhatsApp module (JARVIS messaging Dani himself) as a zero-extra-infra solution.
- **Plugin/skill marketplace pattern** — formalize the `SKILL.md` manifest system enough that Dani (or future collaborators) could drop in a new skill folder without touching core code at all — effectively what the skills master-prompt already sets up, just taken further with versioning and dependency declarations.

---

## P3 — Exploratory

- **Vision-based screen understanding** — combine the existing browser automation snapshot approach with a vision model so JARVIS can react to arbitrary on-screen content (not just structured web pages) — e.g. "is chart pe kya pattern dikh raha hai" from a live MT5 terminal screenshot.
- **Autonomous EA tuning loop** — a supervised loop where JARVIS proposes parameter adjustments to an EA based on recent performance, but always requires explicit Dani approval before any live parameter change — research/idea stage only, high risk if done carelessly.
- **Multi-modal trading alerts** — combine price action + news sentiment (from `web_research` skill) into a single composite alert, rather than treating price and news as separate signals.
- **Personality/voice customization** — configurable JARVIS personality modes (formal/business vs. casual Roman Urdu banter) selectable per context — professional when drafting a client message, casual when chatting.
- **Self-healing skill errors** — when a skill fails repeatedly with the same error signature, JARVIS surfaces a diagnosis attempt ("ye error edge-tts rate limit ki wajah se lagta hai") rather than just logging and repeating the same failure silently next time.

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
