# JARVIS — Commands

> Yeh file `hk7184398-spec/jarvis1` repo ko directly fetch/clone karke banayi gayi hai (actual `main.py`, `actions/*.py`, `core/prompt.txt` padh kar) — is liye yeh guesswork nahi, real code ke mutabiq hai.
> Maqsad: (1) abhi konsi commands JARVIS me already wired hain, (2) konsi command **bani hui hai lekin wire nahi hui**, (3) konsi commands add ki ja sakti hain future me.

---

## Yeh system kaise kaam karta hai (zaroori context)

JARVIS ek Gemini-Live-based voice assistant hai. Har "command" asal me ek **tool declaration** hai jo 3 jagah define hoti hai:

1. **`main.py` → `TOOL_DECLARATIONS` list** — tool ka naam, description, aur parameters (yeh Gemini ko batata hai ke tool kab/kaise call karni hai).
2. **`main.py` → `_execute_tool()`** — jab Gemini tool call karta hai, yahan `if name == "..."` branch actual Python function ko call karta hai.
3. **`actions/<file>.py`** — actual implementation (jo function `_execute_tool` call karta hai).

Kabhi kabhi `core/prompt.txt` me ek extra routing rule bhi likhi hoti hai (jaise "computer_settings use karo, agent_task nahi") taake Gemini confuse na ho konsi tool sahi hai.

**Nayi command add karne ka standard tareeqa:**
1. `actions/` me handler function likho (ya already existing file me naya action add karo).
2. `main.py` ke `TOOL_DECLARATIONS` list me naya dict entry add karo (name + description + parameters schema).
3. `main.py` ke `_execute_tool()` me matching `elif name == "..."` branch add karo jo us function ko call kare.
4. Agar tool overlap ho sakti hai kisi existing tool se (jaise "screenshot" `computer_settings` aur `computer_control` dono me hai), to `core/prompt.txt` me ek clear routing rule likho.
5. Manually test karo — voice se command bol kar confirm karo sahi tool call ho rahi hai.

---

## Section 1 — Commands jo abhi LIVE hain (already wired in `main.py`)

Yeh 20 tools abhi register hain aur kaam kar rahi hain. Har ek ke saath: kya karti hai + example voice command.

| # | Command (tool name) | Kya karti hai | Example |
|---|---|---|---|
| 1 | `open_app` | Koi bhi app/website/program open karta hai | "Jarvis, Chrome khol do" |
| 2 | `web_search` | Web search karta hai, aur `compare` mode me items compare karta hai | "Jarvis, iPhone 16 vs Samsung S25 compare karo price pe" |
| 3 | `weather_report` | Kisi city ka weather batata hai | "Jarvis, Lahore ka weather batao" |
| 4 | `send_message` | WhatsApp/Telegram/etc pe message bhejta hai | "Jarvis, Ali ko WhatsApp pe bolo main late hoon" |
| 5 | `reminder` | Windows Task Scheduler se timed reminder set karta hai | "Jarvis, kal 5 baje mujhe meeting yaad dila dena" |
| 6 | `youtube_video` | Video play/summarize/get_info/trending | "Jarvis, yeh video summarize kar do" |
| 7 | `screen_process` | Screen ya camera dekh kar analyze karta hai (vision) | "Jarvis, mera screen pe kya hai batao" |
| 8 | `computer_settings` | Volume, brightness, window mgmt, wifi, lock, shutdown, zoom, tabs | "Jarvis, volume 30% kar do" |
| 9 | `browser_control` | Browser automation — navigate, click, fill form, scroll | "Jarvis, Amazon khol kar 'laptop' search karo" |
| 10 | `file_controller` | Files/folders: list, create, delete, move, copy, rename, find, disk usage | "Jarvis, downloads folder me sabse badi file dhundo" |
| 11 | `desktop_control` | Wallpaper, organize, clean, list, desktop stats | "Jarvis, desktop clean kar do type ke hisaab se" |
| 12 | `code_helper` | Code likhna/edit/explain/run/build | "Jarvis, ek Python script likho jo CSV parse kare" |
| 13 | `dev_agent` | Poora multi-file project banata hai (plan → write → install deps → run → fix) | "Jarvis, ek to-do list app bana do React me" |
| 14 | `agent_task` | Complex multi-step goals jo multiple tools use karte hain | "Jarvis, is topic pe research karo aur file me save kar do" |
| 15 | `computer_control` | Low-level control: type, click, hotkey, screenshot, screen_find | "Jarvis, is screenshot me 'Submit' button dhund kar click karo" |
| 16 | `game_updater` | Steam/Epic games install/update/list/schedule | "Jarvis, Steam pe GTA V update kar do" |
| 17 | `flight_finder` | Google Flights search karta hai | "Jarvis, Karachi se Dubai flight dhundo 15 August ko" |
| 18 | `file_processor` | Uploaded file pe action: image/pdf/docx/csv/json/code/audio/video/archive/pptx | "Jarvis, is PDF ko summarize kar do" |
| 19 | `shutdown_jarvis` | Assistant session band karta hai | "Jarvis, bye" / "Jarvis band ho jao" |
| 20 | `save_memory` | User ke baare me important facts silently save karta hai | _(automatic, koi direct command nahi)_ |

---

## Section 2 — Bani hui hai, lekin wire NAHI hui (turant add ki ja sakti hai)

### ⚠️ `cut_viral_clips` (from `actions/viral_clipper.py`)
- **Status:** Code fully likha hua hai (`viral_clipper.py`, 425 lines) — dependencies auto-install, transcribe (faster-whisper), AI highlight detection, ffmpeg cut — sab kaam karta hai standalone.
- **Problem:** `main.py` me is tool ka `TOOL_DECLARATIONS` entry **exist nahi karta**, aur `_execute_tool()` me bhi iska `elif` branch missing hai. Matlab abhi voice se yeh command call nahi ho sakti.
- **Add karne ke steps** (repo ki apni `Viral Clip Extractor.md` file me likhe hain):
  1. `main.py` ke top pe: `from actions.viral_clipper import TOOL_DECLARATIONS as viral_clipper_tools, jarvis_tool_cut_viral_clips`
  2. `TOOL_DECLARATIONS.extend(viral_clipper_tools)`
  3. `_execute_tool()` me: `elif name == "cut_viral_clips": result = jarvis_tool_cut_viral_clips(video_source=args["video_source"], num_clips=args.get("num_clips", 5))`
- **Yeh sabse pehle wire karni chahiye** — kaam ban chuka hai, sirf connect karna hai.

---

## Section 3 — Planned commands jo repo ki apni docs (`Ideas.md`, `Modules.md`) me likhi hain lekin abhi banaayi nahi gayin

Yeh repo ke andar `Ideas.md`/`Modules.md`/`Tasks.md` files me already documented hain (SPEC/PLANNED status). Voice-command angle se yeh naye tools banenge:

| Proposed command area | Kya karegi | Status in repo |
|---|---|---|
| `documents` skill | PDF/DOCX/XLSX/PPTX generate karna (trading report jaisa) | SPEC |
| `web_research` (deep) | Multi-source search → fetch → synthesize summary | SPEC |
| `calendar_reminders` (upgrade) | Proper alarm/reminder table + scheduling primitive (abhi sirf Task Scheduler wrapper hai) | SPEC |
| `image_search` | Unsplash/Pexels se images fetch karna | SPEC |
| `browser_automation` (upgrade) | Persistent browser session + domain allowlist + confirmation gating on form-submit | SPEC (basic version already LIVE as `browser_control`) |
| `system_control` (upgrade) | `computer_settings`/`computer_control` ko formal confirmation-gated system (shutdown/delete hamesha confirm) | PLANNED |
| `whatsapp_automation` (upgrade) | Scheduled send, broadcast, delivery-status wait, contact disambiguation | SPEC (basic send already LIVE as `send_message`) |
| `youtube_automation` (full pipeline) | Trigger full video pipeline (script→voice→broll→render→publish), job status, retry | SPEC |
| `tiktok_automation` | Repurpose YouTube video → vertical short → post/draft | PLANNED |
| `trading_data` (router-wrap) | MT5 read-only data ko standard tool interface me wrap karna | LIVE, wrapping SPEC |
| `memory` (formal skill) | `remember()`/`recall()`/`search_memory()` ko explicit tool banana (abhi sirf `save_memory` hai, `recall` command nahi hai) | SPEC |

---

## Section 4 — Gaps jo maine khud notice ki (repo scan ke baad) — consider karne layak

Yeh koi existing doc me nahi likhi, lekin code scan karte waqt yeh cheezein missing lagi:

- [ ] **`recall_memory` / "Jarvis, mujhe woh yaad hai jo maine bataya tha X ke baare me"** — `save_memory` hai lekin explicit "recall" tool nahi hai; Gemini ko system prompt/context se hi memory milti hai, on-demand query tool nahi.
- [ ] **Music/media control** — Spotify/YouTube Music jaisa koi dedicated skip/pause/volume-for-music command nahi (sirf generic `open_app` + `computer_settings` volume hai).
- [ ] **Email command** — koi `send_email`/`read_email` tool nahi hai (sirf WhatsApp/Telegram/generic messaging).
- [ ] **System info / battery / disk space quick-check** — `file_controller` me `disk_usage` hai lekin battery %, RAM usage, CPU temp jaisi cheezein kahin nahi.
- [ ] **Note-taking / quick capture** — koi standalone "note likh do" command nahi (sirf `file_controller.create_file` se manually ho sakta hai, dedicated nahi).
- [ ] **Translate (standalone)** — `file_processor` me `translate_hint` action hai lekin sirf uploaded file ke liye; plain "yeh sentence translate karo" ke liye dedicated tool nahi.
- [ ] **`viral_clipper` wiring** (already Section 2 me cover kiya) — sabse zaroori/quick win hai.

---

## Kaise decide karein konsi command pehle add karni hai

1. **Sabse pehle:** Section 2 (`cut_viral_clips`) — kaam ban chuka hai, sirf 3 lines wiring chahiye.
2. **Phir:** Section 4 ke gaps me se jo Dani ko roz kaam aaye (jaise recall_memory ya system info).
3. **Phir:** Section 3 ke bade SPEC items — yeh zyada kaam maangte hain, in par tabhi jao jab upar wale done ho jayein.

---

## Naya command add karte waqt checklist (copy-paste karo har baar)

- [ ] Handler function `actions/` me likh diya
- [ ] `TOOL_DECLARATIONS` me naya entry add kiya (`main.py`)
- [ ] `_execute_tool()` me `elif` branch add kiya (`main.py`)
- [ ] Agar overlap-prone hai to `core/prompt.txt` me routing rule likhi
- [ ] Voice se test kiya — sahi tool call hoti hai, sahi result aata hai
- [ ] Agar destructive/irreversible action hai (delete, shutdown, send) → confirmation flow check kiya
