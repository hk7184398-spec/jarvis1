"""
actions/screen_recorder.py
--------------------------------------------------------
Jarvis module: Screen Recorder

Kya karta hai:
  1. "Jarvis, screen record start karo" -> background thread me continuous
     frames leta hai (mss), cv2.VideoWriter se .mp4 me encode karta hai.
  2. Optional: saath me microphone audio bhi record karta hai (sounddevice),
     aur stop hone par ffmpeg se video+audio mux kar deta hai.
  3. "Jarvis, recording band karo" -> file save ho kar path return karta hai.
  4. "Jarvis, recording chal rahi hai?" -> status + elapsed time batata hai.

Setup (ek baar):
    pip install mss opencv-python numpy sounddevice soundfile --break-system-packages
    sudo apt install ffmpeg      # sirf audio+video mux ke liye zaroori

Limits (design decisions, jaan-bujh kar simple rakha hai):
  - Ek waqt me sirf ek recording (global single session) — do parallel
    recordings allowed nahi, confusion se bachne ke liye.
  - MAX_RECORDING_SECONDS safety cap hai (default 30 min) — agar "stop"
    bolna bhool jao to khud-ba-khud ruk kar save ho jayegi, disk na bhare.
  - Sirf MICROPHONE audio record hota hai, system/desktop audio nahi —
    desktop-audio loopback OS-specific hota hai (WASAPI/PulseAudio alag alag)
    aur abhi scope se bahar rakha hai. Future upgrade note niche hai.

Standalone test:
    python screen_recorder.py --seconds 5 --out test.mp4

Jarvis me wire karne ke liye niche "JARVIS INTEGRATION" section dekho.
--------------------------------------------------------
"""

import os
import time
import shutil
import argparse
import threading
import subprocess
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
import mss

# ------------------------------------------------------------------
# CONFIG
# ------------------------------------------------------------------
DEFAULT_OUTPUT_DIR    = os.environ.get("SCREEN_RECORDINGS_DIR", str(Path.home() / "JARVIS_Recordings"))
DEFAULT_FPS            = 12
MIN_FPS, MAX_FPS       = 5, 30
DEFAULT_MONITOR        = 1          # mss.monitors[1] = first physical monitor (matches screen_processor.py convention)
MAX_RECORDING_SECONDS  = 30 * 60    # safety cap: auto-stop after 30 minutes


def _has_ffmpeg() -> bool:
    return shutil.which("ffmpeg") is not None


# ------------------------------------------------------------------
# GLOBAL STATE -- ek waqt me sirf ek recording session
# ------------------------------------------------------------------
class _RecorderState:
    def __init__(self):
        self.lock          = threading.Lock()
        self.active        = False
        self.video_thread  = None
        self.audio_thread  = None
        self.stop_event    = None
        self.video_path    = None
        self.final_path    = None
        self.include_audio = False
        self.audio_frames  = []
        self.samplerate    = 44100
        self.started_at    = None


_state = _RecorderState()


# ------------------------------------------------------------------
# CAPTURE LOOPS (background threads)
# ------------------------------------------------------------------
def _video_capture_loop(monitor_index: int, fps: int, stop_event: threading.Event, video_path: str):
    with mss.mss() as sct:
        monitors = sct.monitors
        idx = monitor_index if 0 <= monitor_index < len(monitors) else DEFAULT_MONITOR
        mon = monitors[idx]
        width, height = mon["width"], mon["height"]

        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(video_path, fourcc, fps, (width, height))
        frame_interval = 1.0 / fps

        try:
            while not stop_event.is_set():
                t0 = time.time()
                shot  = sct.grab(mon)
                frame = cv2.cvtColor(np.array(shot), cv2.COLOR_BGRA2BGR)
                writer.write(frame)
                sleep_time = frame_interval - (time.time() - t0)
                if sleep_time > 0:
                    time.sleep(sleep_time)
        except Exception as e:
            print(f"[screen_recorder] ⚠️ Video capture error: {e}")
        finally:
            writer.release()


def _audio_capture_loop(stop_event: threading.Event, samplerate: int, frames_out: list):
    try:
        import sounddevice as sd
    except ImportError:
        print("[screen_recorder] ⚠️ 'sounddevice' not installed — recording video without audio.")
        return

    def _callback(indata, frames, time_info, status):
        frames_out.append(indata.copy())

    try:
        with sd.InputStream(samplerate=samplerate, channels=1, callback=_callback):
            while not stop_event.is_set():
                time.sleep(0.1)
    except Exception as e:
        print(f"[screen_recorder] ⚠️ Audio capture error: {e}")


# ------------------------------------------------------------------
# PUBLIC ACTIONS
# ------------------------------------------------------------------
def start_recording(parameters: dict, player=None) -> str:
    with _state.lock:
        if _state.active:
            return "Recording pehle se chal rahi hai, sir — pehle usse stop karo."

        include_audio = bool((parameters or {}).get("include_audio", False))
        monitor_index = int((parameters or {}).get("monitor", DEFAULT_MONITOR))
        fps           = int((parameters or {}).get("fps", DEFAULT_FPS))
        fps           = max(MIN_FPS, min(fps, MAX_FPS))

        out_dir = Path(DEFAULT_OUTPUT_DIR)
        out_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")

        video_path = str(out_dir / f"recording_{ts}_video.mp4")
        final_path = str(out_dir / f"recording_{ts}.mp4")

        stop_event   = threading.Event()
        audio_frames = []
        samplerate   = 44100

        video_thread = threading.Thread(
            target=_video_capture_loop,
            args=(monitor_index, fps, stop_event, video_path),
            daemon=True,
        )
        video_thread.start()

        audio_thread = None
        if include_audio:
            audio_thread = threading.Thread(
                target=_audio_capture_loop,
                args=(stop_event, samplerate, audio_frames),
                daemon=True,
            )
            audio_thread.start()

        _state.active        = True
        _state.video_thread  = video_thread
        _state.audio_thread  = audio_thread
        _state.stop_event    = stop_event
        _state.video_path    = video_path
        _state.final_path    = final_path
        _state.include_audio = include_audio
        _state.audio_frames  = audio_frames
        _state.samplerate    = samplerate
        _state.started_at    = time.time()

        def _watchdog(bound_event=stop_event):
            time.sleep(MAX_RECORDING_SECONDS)
            if _state.active and _state.stop_event is bound_event:
                print("[screen_recorder] ⏱️ Max duration reached — auto-stopping.")
                stop_recording({}, player=player)

        threading.Thread(target=_watchdog, daemon=True).start()

    audio_note = " (audio ke saath)" if include_audio else ""
    return f"Screen recording shuru ho gayi{audio_note}, sir. Rokne ke liye bolo 'recording band karo'."


def stop_recording(parameters: dict = None, player=None) -> str:
    with _state.lock:
        if not _state.active:
            return "Koi recording chal hi nahi rahi, sir."

        _state.stop_event.set()
        video_thread  = _state.video_thread
        audio_thread  = _state.audio_thread
        video_path    = _state.video_path
        final_path    = _state.final_path
        include_audio = _state.include_audio
        audio_frames  = _state.audio_frames
        samplerate    = _state.samplerate
        duration      = time.time() - _state.started_at
        _state.active = False

    video_thread.join(timeout=10)
    if audio_thread:
        audio_thread.join(timeout=10)

    if not os.path.exists(video_path) or os.path.getsize(video_path) < 1024:
        return "Recording save karte waqt kuch ghalat ho gaya, sir — video file khali/corrupt hai."

    if include_audio and audio_frames:
        try:
            import soundfile as sf
            audio_path = video_path.replace("_video.mp4", "_audio.wav")
            audio_data = np.concatenate(audio_frames, axis=0)
            sf.write(audio_path, audio_data, samplerate)

            if _has_ffmpeg():
                mux = subprocess.run(
                    [
                        "ffmpeg", "-y",
                        "-i", video_path,
                        "-i", audio_path,
                        "-c:v", "copy", "-c:a", "aac",
                        "-shortest",
                        final_path,
                    ],
                    capture_output=True, text=True, timeout=120,
                )
                if mux.returncode == 0:
                    os.remove(video_path)
                    os.remove(audio_path)
                else:
                    print(f"[screen_recorder] ⚠️ ffmpeg mux failed: {mux.stderr[:300]}")
                    os.rename(video_path, final_path)
                    os.remove(audio_path) if os.path.exists(audio_path) else None
            else:
                print("[screen_recorder] ⚠️ ffmpeg not found — saving video without audio (install ffmpeg to fix).")
                os.rename(video_path, final_path)
        except ImportError:
            print("[screen_recorder] ⚠️ 'soundfile' not installed — saving video without audio.")
            os.rename(video_path, final_path)
        except Exception as e:
            print(f"[screen_recorder] ⚠️ Audio mux error: {e}")
            os.rename(video_path, final_path)
    else:
        os.rename(video_path, final_path)

    mins, secs = divmod(int(duration), 60)
    return f"Recording save ho gayi, sir — {mins}m {secs}s, file: {final_path}"


def get_recording_status(parameters: dict = None, player=None) -> str:
    with _state.lock:
        if not _state.active:
            return "Koi recording active nahi hai, sir."
        elapsed = time.time() - _state.started_at
    mins, secs = divmod(int(elapsed), 60)
    return f"Recording chal rahi hai, sir — {mins}m {secs}s ho chuke hain."


# ------------------------------------------------------------------
# Standalone test
# ------------------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--seconds", type=int, default=5)
    parser.add_argument("--audio", action="store_true")
    args = parser.parse_args()

    print(start_recording({"include_audio": args.audio}))
    time.sleep(args.seconds)
    print(stop_recording({}))


# ------------------------------------------------------------------
# JARVIS INTEGRATION -- main.py ke TOOL_DECLARATIONS me wire karo
# ------------------------------------------------------------------
TOOL_DECLARATIONS = [
    {
        "name": "start_screen_recording",
        "description": (
            "Starts recording the screen to a video file. Use whenever the user asks to "
            "record the screen, start a screencast/screen recording, or capture what's "
            "happening on screen over time (not a single screenshot)."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "include_audio": {
                    "type": "BOOLEAN",
                    "description": "Also record microphone audio alongside the video. Default false.",
                },
                "monitor": {
                    "type": "INTEGER",
                    "description": "Which monitor to record: 1 = first monitor (default), 2 = second, etc.",
                },
                "fps": {
                    "type": "INTEGER",
                    "description": "Frames per second, 5-30. Default 12.",
                },
            },
            "required": [],
        },
    },
    {
        "name": "stop_screen_recording",
        "description": (
            "Stops the currently active screen recording and saves it to a video file. "
            "Use whenever the user asks to stop, end, or finish the recording."
        ),
        "parameters": {"type": "OBJECT", "properties": {}, "required": []},
    },
    {
        "name": "get_screen_recording_status",
        "description": "Reports whether a screen recording is currently active and how long it has been running.",
        "parameters": {"type": "OBJECT", "properties": {}, "required": []},
    },
]
