title: Viral Clip Extractor project: jarvis module: actions/viral_clipper.py status: active type: feature-note created: 2026-07-25 tags: [jarvis, mark-xxxix-or, video, ai, automation, youtube]
Viral Clip Extractor
Kya karta hai
Bas video ka link bolo (ya file path do) — Jarvis khud:
Video download/load karta hai
Poori video transcribe karta hai (faster-whisper, local, free)
AI se transcript analyze karke viral-worthy moments dhundta hai
Har moment ko original quality/voice preserve karte hue clip me cut karta hai
Clips ek folder me ready rakhta hai — seedha download/use
Isme kuch bhi manual nahi karna — dependencies, ffmpeg, sab khud check/install ho jata hai pehli baar chalne pe.
[!success] Autonomous behavior Ek baar wiring ho jaye (niche "One-Time Setup" section), uske baad sirf voice command: "Jarvis, is link se 5 viral clips nikaal do" — bas. Naya video ho, naya link ho, kabhi dobara touch nahi karna.
Pipeline (khud-ba-khud chalta hai)
Stage
Kya hota hai
Manual intervention?
0. Self-check
Missing pip packages + ffmpeg khud detect + install
❌ Nahi
1. Source resolve
URL ho to yt-dlp se download, file ho to seedha use
❌ Nahi
2. Transcribe
faster-whisper se timestamped transcript
❌ Nahi
3. AI highlight detection
OpenRouter se viral moments (start/end/title/hook)
❌ Nahi
4. Cut
ffmpeg CRF 17 re-encode — original jaisi quality/audio
❌ Nahi
5. Save
jarvis_viral_clips/ folder me ready, filename me title
❌ Nahi
One-Time Setup
Ye sirf ek baar karna hai — uske baad system permanently autonomous hai.
1. File jagah pe rakho
cp viral_clipper.py /home/dani/Downloads/jarvis1/actions/
2. OpenRouter key (already Jarvis me hai, dobara set nahi karni agar already hai)
export OPENROUTER_API_KEY="sk-or-..."
Ya config_manager.py se load ho raha ho to viral_clipper.py ke top wali OPENROUTER_API_KEY = os.environ.get(...) line ko us loader se replace kar dena.
3. main.py me wire karo (ek dafa)
from actions.viral_clipper import TOOL_DECLARATIONS as viral_clipper_tools
from actions.viral_clipper import jarvis_tool_cut_viral_clips

TOOL_DECLARATIONS.extend(viral_clipper_tools)

if tool_name == "cut_viral_clips":
    result = jarvis_tool_cut_viral_clips(
        video_source=args["video_source"],
        num_clips=args.get("num_clips", 5),
    )
Bas itna hi. Ye 3 steps ek baar. Ispe ke baad kabhi requirements.txt, pip install, ya ffmpeg ke baare me sochna nahi padega — module khud ensure_dependencies() se check karta hai aur missing cheez khud install kar leta hai jab bhi first time chale.
Roz ka use (voice se)
"Jarvis, is video se viral clips nikaal do" (link bolo/paste karo)
"Jarvis, 3 clips bana do is file se"
Jarvis reply karega clip titles + folder path ke saath
Quality note
Default mode precise: CRF 17 re-encode, exact timestamp cut — dekhne/sunne me original jaisa hi, farq pakadna mushkil hai.
mode="fast" chahiye ho (bit-perfect original, thoda imprecise cut) to jarvis_tool_cut_viral_clips call me mode param add kar sakte ho.
Auto-handled dependencies
yt-dlp, faster-whisper, requests — pip se khud install
ffmpeg / ffprobe — apt se khud install (agar passwordless sudo nahi hai to ek baar manually sudo apt install -y ffmpeg chalana padega, uske baad hamesha ke liye theek)
Related
[[Jarvis YouTube Automation Pipeline]]
[[Mark-XXXIX-OR Architecture]]
Open items
[ ] Better viral-detection model try karna agar free-tier llama weak lage (OPENROUTER_MODEL env var se switch: google/gemini-2.0-flash-exp:free)
[ ] Long videos (1hr+) ke liye whisper model size auto-scale karna
[ ] WhatsApp module se clips auto-forward karne ka option