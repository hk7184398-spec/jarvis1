# JARVIS — Bugs

> Yeh file JARVIS project ke saare known bugs, issues, aur unresolved problems track karti hai. `TASKS.md` naye features/build tasks ke liye hai, `BUGS.md` un cheezon ke liye hai jo already bani hui hain lekin sahi kaam nahi kar rahi.

---

## Kaise use karein is file ko

- Har bug ko ek **unique ID** do (`BUG-001`, `BUG-002`, ...) — kabhi delete/reuse mat karo IDs, sirf status change karo.
- Status values: `[ ] Open` → `[~] In Progress` → `[x] Fixed` → `[R] Reopened` (agar fix baad me phir se toot jaye).
- Har bug entry me yeh fields honi chahiye (neeche template hai):
  - **Severity** — kitna critical hai
  - **Module** — konsi file/skill affected hai
  - **Description** — kya galat ho raha hai
  - **Steps to Reproduce** — kaise dobara trigger karein
  - **Expected vs Actual** — kya hona chahiye tha vs kya hua
  - **Root Cause** — jab pata chal jaye (pehle blank rahega)
  - **Fix** — kya badla gaya, kaunsi file me
  - **Status + Date**

---

## Severity Levels (definitions)

| Level | Matlab | Example |
|---|---|---|
| **P0 – Critical** | System crash ho jata hai ya data loss/security risk | MT5 connection crash pura JARVIS le doobta hai |
| **P1 – High** | Core feature kaam nahi karti, lekin system chalta rehta hai | WhatsApp auto-reply silently fail ho raha hai |
| **P2 – Medium** | Feature kaam karti hai lekin galat/incomplete result deti hai | Trading report ka chart data purana dikhata hai |
| **P3 – Low** | Cosmetic ya minor annoyance | Dashboard status text thoda misaligned hai |

---

## Open Bugs

### BUG-001
- **Severity:** (P0 / P1 / P2 / P3)
- **Module/File:** `core/...` ya `skills/...`
- **Status:** `[ ]` Open
- **Reported:** YYYY-MM-DD
- **Description:**
- **Steps to Reproduce:**
  1.
  2.
  3.
- **Expected behavior:**
- **Actual behavior:**
- **Root cause:** _(pending investigation)_
- **Fix:** _(pending)_
- **Related task/skill:** _(agar TASKS.md se koi task related hai to uska reference)_

<!-- Naya bug add karne ke liye upar wala template copy-paste karo aur BUG-002, BUG-003... karte jao -->

---

## Fixed Bugs (archive)

> Fix hone ke baad bug yahan move karo — history rakhne ke liye, delete mat karo.

<!-- Example:
### BUG-000 (example, fixed)
- **Severity:** P1
- **Module/File:** `skills/communication/whatsapp/handler.py`
- **Status:** `[x]` Fixed
- **Reported:** 2026-01-10
- **Fixed:** 2026-01-12
- **Description:** Auto-reply do baar message bhej raha tha ek hi trigger par.
- **Root cause:** Rate-limiter ka debounce window bug tha.
- **Fix:** `handler.py` me debounce logic corrected, `skill_log` me duplicate-check add kiya.
-->

---

## Recurring / Known-flaky Issues

> Woh problems jo bar bar aati hain lekin abhi tak permanently fix nahi ho payi — inko track karna zaroori hai taake ignore na ho jayein.

- [ ] _(example)_ MT5 connection kabhi kabhi silently drop ho jata hai bina koi error diye.

---

## Bug → Task Linkage

Agar koi bug fix karne ke liye naya feature/refactor chahiye (chhota fix nahi), to us bug ko yahan note karo aur `TASKS.md` me corresponding task add karo — bug tab tak "Open" rahega jab tak woh task complete na ho.

| Bug ID | Related Task (in TASKS.md) |
|---|---|
| BUG-001 | — |

---

## Reporting checklist (naya bug likhne se pehle)

- [ ] Kya yeh bug already kisi existing entry me hai? (duplicate check)
- [ ] Kya reproduce steps clear aur complete hain?
- [ ] Kya severity sahi assign ki gayi hai (upar table dekho)?
- [ ] Kya relevant `skill_log` entry ya error message attach/copy ki hai?
- [ ] Kya yeh bug security/credentials se related hai? Agar haan, to details is file me mat likho — sirf reference rakho aur secure channel use karo.
