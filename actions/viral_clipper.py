"""
actions/viral_clipper.py
--------------------------------------------------------
Jarvis AI - Lite module: Viral Clip Extractor

Kya karta hai:
  1. Video source lo -> YouTube/kisi bhi video URL (yt-dlp) YA local file path
  2. Puri video transcribe karo (faster-whisper, local/free, koi API cost nahi)
  3. AI (OpenRouter) se transcript analyze karwa ke "viral-worthy" moments
     dhundo (hooks, punchlines, emotional/funny/shocking lines, etc.)
  4. Har moment ko ffmpeg se cut karo -- quality/audio mode "precise" me
     original ke barabar (visually lossless CRF) rakhta hai, ya "fast" mode
     me stream-copy (bit-perfect, thoda kam accurate timestamps).
  5. Clips ek output folder me save hote hain, download seedha wahan se
     ho jata hai (Jarvis WhatsApp module se bhi bhej sakta hai agar chaho).

Setup (ek baar):
    pip install -r requirements_viral_clipper.txt --break-system-packages
    sudo apt install ffmpeg          # agar already nahi hai
    export OPENROUTER_API_KEY="sk-or-..."   # ya .env / config_manager me daal do

Standalone test:
    python viral_clipper.py --url "https://youtube.com/watch?v=XXXX" --clips 5
    python viral_clipper.py --file "/path/to/video.mp4" --clips 3

Jarvis me wire karne ke liye niche "JARVIS INTEGRATION" section dekho.
--------------------------------------------------------
"""

import os
import re
import sys
import json
import shutil
import importlib
import subprocess
import argparse
from datetime import datetime

# ------------------------------------------------------------------
# CONFIG -- apne config_manager.py se bhi ye values la sakte ho
# ------------------------------------------------------------------
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL", "meta-llama/llama-3.1-8b-instruct:free")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

WHISPER_MODEL_SIZE = os.environ.get("WHISPER_MODEL_SIZE", "small")  # tiny/base/small/medium
DEFAULT_OUTPUT_DIR = os.environ.get("VIRAL_CLIPS_DIR", "jarvis_viral_clips")

MIN_CLIP_SECONDS = 15
MAX_CLIP_SECONDS = 90

REQUIRED_PACKAGES = {
    "yt_dlp": "yt-dlp",
    "faster_whisper": "faster-whisper",
    "requests": "requests",
}

_DEPS_CHECKED = False  # ek run me baar-baar check na ho, is liye cache


# ------------------------------------------------------------------
# 0. SELF-HEALING SETUP -- Dani ko kuch manually install nahi karna
# ------------------------------------------------------------------
def ensure_dependencies() -> None:
    """
    Pehli call pe khud check karta hai ke sab pip packages aur ffmpeg
    maujood hain ya nahi. Missing ho to khud install kar deta hai.
    Isse Dani ko kabhi 'pip install' ya 'apt install' manually nahi
    chalana padta -- bas video link bolo, baaki Jarvis sambhal lega.
    """
    global _DEPS_CHECKED
    if _DEPS_CHECKED:
        return

    missing = []
    for module_name, pip_name in REQUIRED_PACKAGES.items():
        try:
            importlib.import_module(module_name)
        except ImportError:
            missing.append(pip_name)

    if missing:
        print(f"[viral_clipper] Missing packages mil gayi: {missing} -- auto-install ho raha hai...")
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "--break-system-packages", *missing],
            check=True,
        )
        importlib.invalidate_caches()
        print("[viral_clipper] Packages install ho gayi.")

    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        print("[viral_clipper] ffmpeg missing hai -- auto-install try kar raha hoon...")
        try:
            subprocess.run(["sudo", "apt-get", "update"], check=True,
                            capture_output=True, timeout=180)
            subprocess.run(["sudo", "apt-get", "install", "-y", "ffmpeg"], check=True,
                            capture_output=True, timeout=300)
            print("[viral_clipper] ffmpeg install ho gaya.")
        except Exception as e:
            raise RuntimeError(
                "ffmpeg auto-install nahi ho paya (shayad sudo password chahiye ho, "
                "ya Jarvis passwordless sudo ke bina chal raha hai). Ek baar manually "
                "chala do: sudo apt install -y ffmpeg -- uske baad ye dobara zarurat "
                "nahi padegi."
            ) from e

    _DEPS_CHECKED = True


# ------------------------------------------------------------------
# 1. VIDEO SOURCE -- URL download ya local file
# ------------------------------------------------------------------
def is_url(source: str) -> bool:
    return source.strip().lower().startswith(("http://", "https://"))


def download_video(url: str, out_dir: str) -> str:
    """yt-dlp se best quality video+audio download karke mp4 bana ke path deta hai."""
    import yt_dlp

    os.makedirs(out_dir, exist_ok=True)
    ydl_opts = {
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "outtmpl": os.path.join(out_dir, "%(id)s.%(ext)s"),
        "merge_output_format": "mp4",
        "quiet": True,
        "no_warnings": True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        raw_path = ydl.prepare_filename(info)

    base, _ = os.path.splitext(raw_path)
    mp4_path = base + ".mp4"
    return mp4_path if os.path.exists(mp4_path) else raw_path


def get_local_video(source: str, out_dir: str) -> str:
    """URL ho to download, warna direct local path use karo."""
    if is_url(source):
        print("[viral_clipper] URL detect hua, download ho raha hai...")
        return download_video(source, out_dir)
    if not os.path.exists(source):
        raise FileNotFoundError(f"Video file nahi mili: {source}")
    return source


# ------------------------------------------------------------------
# 2. FFPROBE -- original video ki quality info nikalne ke liye
# ------------------------------------------------------------------
def probe_video(path: str) -> dict:
    cmd = [
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_format", "-show_streams", path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    data = json.loads(result.stdout)

    v_stream = next((s for s in data["streams"] if s["codec_type"] == "video"), {})
    a_stream = next((s for s in data["streams"] if s["codec_type"] == "audio"), {})

    return {
        "duration": float(data.get("format", {}).get("duration", 0)),
        "video_codec": v_stream.get("codec_name"),
        "audio_codec": a_stream.get("codec_name"),
        "audio_bitrate": a_stream.get("bit_rate"),
        "width": v_stream.get("width"),
        "height": v_stream.get("height"),
    }


# ------------------------------------------------------------------
# 3. TRANSCRIPTION -- faster-whisper (local, free, timestamps ke saath)
# ------------------------------------------------------------------
def transcribe(path: str, model_size: str = WHISPER_MODEL_SIZE) -> list:
    from faster_whisper import WhisperModel

    print(f"[viral_clipper] Transcribe ho raha hai (model={model_size})...")
    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    segments_iter, _info = model.transcribe(path, beam_size=5, vad_filter=True)

    segments = []
    for seg in segments_iter:
        segments.append({
            "start": seg.start,
            "end": seg.end,
            "text": seg.text,
        })
    print(f"[viral_clipper] {len(segments)} segments mile.")
    return segments


# ------------------------------------------------------------------
# 4. AI SE VIRAL MOMENTS DHUNDNA
# ------------------------------------------------------------------
def call_ai(prompt: str, system: str = None) -> str:
    import requests

    if not OPENROUTER_API_KEY:
        raise RuntimeError(
            "OPENROUTER_API_KEY set nahi hai. export OPENROUTER_API_KEY=... karo "
            "ya config_manager.py se load karo."
        )

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {"model": OPENROUTER_MODEL, "messages": messages, "temperature": 0.4}

    resp = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=120)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def _clean_json_response(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.lower().startswith("json"):
            raw = raw[4:]
    return raw.strip()


def _chunk_segments(segments: list, chunk_seconds: float = 900.0) -> list:
    """Lambi video ho to ~15 min ke chunks me todo, taake AI prompt chota rahe."""
    if not segments:
        return []
    chunks, current, chunk_start = [], [], segments[0]["start"]
    for seg in segments:
        if seg["start"] - chunk_start > chunk_seconds and current:
            chunks.append(current)
            current, chunk_start = [], seg["start"]
        current.append(seg)
    if current:
        chunks.append(current)
    return chunks


def detect_viral_segments(segments: list, num_clips: int = 5) -> list:
    """Transcript AI ko dekar viral-worthy start/end timestamps nikalta hai."""
    system = (
        "Tum ek expert short-form video editor ho (Reels/Shorts/TikTok style). "
        "Diye gaye timestamped transcript me se sabse zyada 'viral' potential "
        "wale moments dhundo -- hooks, punchlines, funny/shocking/emotional lines, "
        "strong opinions, ya koi bhi cliffhanger jo scroll rokwa de. "
        "Har clip khud me complete/samajh aane wala hona chahiye."
    )

    chunks = _chunk_segments(segments)
    all_clips = []

    for chunk in chunks:
        transcript_text = "\n".join(
            f"[{s['start']:.1f}-{s['end']:.1f}] {s['text'].strip()}" for s in chunk
        )
        per_chunk_n = max(1, num_clips // max(1, len(chunks)) + 1)
        prompt = f"""Neeche timestamped transcript hai. Isme se {per_chunk_n} best
viral clip candidates dhundo. Har clip {MIN_CLIP_SECONDS}-{MAX_CLIP_SECONDS} seconds
ka hona chahiye, aur exact start/end second transcript ke timestamps se lo.

Sirf valid JSON array return karo, koi markdown ya explanation nahi:
[{{"start": <float seconds>, "end": <float seconds>, "title": "<catchy short title>", "hook": "<ye viral kyun hai, 1 line>"}}]

Transcript:
{transcript_text}
"""
        try:
            raw = call_ai(prompt, system)
            clips = json.loads(_clean_json_response(raw))
            all_clips.extend(clips)
        except Exception as e:
            print(f"[viral_clipper] Ek chunk skip hua AI/parse error ki wajah se: {e}")
            continue

    # duration filter + sort by (implicit) order, then trim to num_clips
    filtered = []
    for c in all_clips:
        try:
            dur = float(c["end"]) - float(c["start"])
        except (KeyError, TypeError, ValueError):
            continue
        if MIN_CLIP_SECONDS <= dur <= MAX_CLIP_SECONDS:
            filtered.append(c)

    return filtered[:num_clips]


# ------------------------------------------------------------------
# 5. FFMPEG CUT -- original quality/voice preserve karte hue
# ------------------------------------------------------------------
def cut_clip(source_path: str, start: float, end: float, out_path: str,
             mode: str = "precise", probe_info: dict = None) -> None:
    """
    mode="precise" -> re-encode with CRF 17 (visually lossless), exact timestamps.
                       Audio original codec/bitrate ke qareeb match karta hai.
    mode="fast"    -> stream copy (-c copy), bit-perfect original quality,
                       lekin cut sirf nearest keyframe par hoga (thoda imprecise).
    """
    duration = max(0.1, end - start)
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)

    if mode == "fast":
        cmd = [
            "ffmpeg", "-y",
            "-ss", str(start), "-i", source_path, "-t", str(duration),
            "-c", "copy", "-avoid_negative_ts", "make_zero",
            out_path,
        ]
    else:
        audio_bitrate = "192k"
        if probe_info and probe_info.get("audio_bitrate"):
            try:
                audio_bitrate = f"{int(probe_info['audio_bitrate']) // 1000}k"
            except (ValueError, TypeError):
                pass

        cmd = [
            "ffmpeg", "-y",
            "-ss", str(start), "-i", source_path, "-t", str(duration),
            "-c:v", "libx264", "-preset", "medium", "-crf", "17",
            "-c:a", "aac", "-b:a", audio_bitrate,
            "-movflags", "+faststart",
            out_path,
        ]

    subprocess.run(cmd, check=True, capture_output=True)


# ------------------------------------------------------------------
# 6. MAIN ORCHESTRATOR
# ------------------------------------------------------------------
def process_video(video_source: str, num_clips: int = 5, mode: str = "precise",
                   output_dir: str = DEFAULT_OUTPUT_DIR,
                   whisper_model_size: str = WHISPER_MODEL_SIZE) -> list:
    ensure_dependencies()  # khud check/install karega, Dani ko kuch nahi karna
    os.makedirs(output_dir, exist_ok=True)

    video_path = get_local_video(video_source, output_dir)
    probe_info = probe_video(video_path)
    segments = transcribe(video_path, whisper_model_size)

    if not segments:
        raise RuntimeError("Transcript empty aayi -- video me audio/speech check karo.")

    clips_meta = detect_viral_segments(segments, num_clips=num_clips)
    if not clips_meta:
        raise RuntimeError("AI ko koi viral moment nahi mila. Video ka content check karo.")

    results = []
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    for i, clip in enumerate(clips_meta, start=1):
        safe_title = re.sub(r"[^a-zA-Z0-9]+", "_", clip.get("title", "clip"))[:40].strip("_")
        out_name = f"clip{i}_{safe_title or 'viral'}_{timestamp}.mp4"
        out_path = os.path.join(output_dir, out_name)

        print(f"[viral_clipper] Cutting clip {i}/{len(clips_meta)}: "
              f"{clip['start']:.1f}s - {clip['end']:.1f}s -> {out_name}")
        cut_clip(video_path, float(clip["start"]), float(clip["end"]),
                  out_path, mode=mode, probe_info=probe_info)

        results.append({
            "path": os.path.abspath(out_path),
            "title": clip.get("title", "Untitled clip"),
            "hook": clip.get("hook", ""),
            "start": clip["start"],
            "end": clip["end"],
        })

    return results


# ------------------------------------------------------------------
# 7. JARVIS INTEGRATION -- main.py ke TOOL_DECLARATIONS me wire karo
# ------------------------------------------------------------------
TOOL_DECLARATIONS = [
    {
        "name": "cut_viral_clips",
        "description": (
            "Kisi bhi video (YouTube link ya local file) se AI-detected viral "
            "moments cut karke short clips banata hai, original quality/audio "
            "preserve karte hue. Download seedha output folder se hota hai."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "video_source": {
                    "type": "string",
                    "description": "Video URL (YouTube etc.) ya local file ka path",
                },
                "num_clips": {
                    "type": "integer",
                    "description": "Kitni clips chahiye (default 5)",
                    "default": 5,
                },
            },
            "required": ["video_source"],
        },
    }
]


def jarvis_tool_cut_viral_clips(video_source: str, num_clips: int = 5) -> str:
    """main.py se is function ko action handler ke taur pe register karo."""
    try:
        results = process_video(video_source, num_clips=num_clips)
        lines = [
            f"{i+1}. {r['title']}  ({r['start']:.0f}s-{r['end']:.0f}s)\n   -> {r['path']}"
            for i, r in enumerate(results)
        ]
        return "Ye viral clips ban gayi hain:\n" + "\n".join(lines)
    except Exception as e:
        return f"Clips banate waqt error aaya: {e}"


# ------------------------------------------------------------------
# 8. STANDALONE CLI -- testing ke liye
# ------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Jarvis Viral Clip Extractor")
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--url", help="Video URL (YouTube etc.)")
    src.add_argument("--file", help="Local video file path")
    parser.add_argument("--clips", type=int, default=5, help="Number of clips")
    parser.add_argument("--mode", choices=["precise", "fast"], default="precise")
    parser.add_argument("--out", default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    source = args.url or args.file
    results = process_video(source, num_clips=args.clips, mode=args.mode, output_dir=args.out)

    print("\n=== DONE ===")
    for i, r in enumerate(results, 1):
        print(f"{i}. {r['title']} [{r['start']:.0f}s-{r['end']:.0f}s] -> {r['path']}")


if __name__ == "__main__":
    main()
