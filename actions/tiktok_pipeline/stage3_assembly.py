# actions/tiktok_pipeline/stage3_assembly.py
# Stage 3 of the TikTok Automation pipeline: video assembly.
#
# Runs ONLY after Stage 2's media (scene images + voice-over) has been
# reviewed and the workflow is at "media_ready". Combines the scene images
# into a vertical (1080x1920) slideshow timed to the voice-over, burns in
# per-scene narration as captions, and muxes the audio — producing the
# final .mp4 ready for Stage 4 (SEO + publish staging).
#
# Design principle (per Jarvis architecture rules, same as Stages 1-2):
#   - This module only GENERATES a file. It never decides the workflow
#     should proceed — the caller (__init__.py) advances state only after
#     ffmpeg has verifiably produced a non-empty output file.
#   - Uses subprocess + ffmpeg directly (same pattern as actions/viral_clipper.py),
#     not a Python video library, to stay consistent with the rest of the
#     codebase and avoid a heavy new dependency.

import json
import shutil
import subprocess
from pathlib import Path

from actions.tiktok_pipeline.state import STATE_DIR

VERTICAL_WIDTH = 1080
VERTICAL_HEIGHT = 1920


def _assets_dir(workflow_id: str) -> Path:
    return STATE_DIR / workflow_id


def ensure_ffmpeg() -> dict:
    """Checks ffmpeg/ffprobe are on PATH. Returns a success dict rather than
    raising, so the caller can report a clean error instead of a crash."""
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        return {
            "success": False,
            "error": (
                "ffmpeg/ffprobe not found on PATH. Install with "
                "'sudo apt install -y ffmpeg' (Linux) or from ffmpeg.org (Windows)."
            ),
        }
    return {"success": True}


def probe_duration(path: Path) -> float:
    """Returns the duration (seconds) of an audio/video file via ffprobe."""
    cmd = [
        "ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", str(path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    data = json.loads(result.stdout)
    return float(data.get("format", {}).get("duration", 0.0))


def _scene_durations(scenes: list, total_duration: float) -> list:
    """
    Splits total_duration across scenes proportionally to each scene's
    narration length (character count) — since the voice-over is one
    continuous audio file for the whole script, not per-scene clips, this
    is the closest approximation of when each scene's narration is being
    spoken without re-running TTS per scene. Every scene gets a floor of
    0.5s so no image flashes by unreadably fast.
    """
    lengths = [max(1, len((s.get("narration") or "").strip())) for s in scenes]
    total_chars = sum(lengths)
    if total_chars == 0 or total_duration <= 0:
        # Fallback: split evenly.
        n = max(1, len(scenes))
        return [total_duration / n] * n

    raw = [total_duration * (length / total_chars) for length in lengths]
    floor = 0.5
    raw = [max(floor, d) for d in raw]

    # Renormalize so the durations still sum to total_duration after the
    # floor was applied (otherwise short scenes could push the total over).
    scale = total_duration / sum(raw) if sum(raw) > 0 else 1.0
    return [d * scale for d in raw]


def _escape_drawtext(text: str) -> str:
    """Escapes text for ffmpeg's drawtext filter (colons, quotes,
    backslashes, percent signs all need escaping inside the filter arg)."""
    text = text.replace("\\", "\\\\")
    text = text.replace(":", "\\:")
    text = text.replace("'", "\u2019")  # swap straight quotes for a typographic one — avoids breaking the filter string
    text = text.replace("%", "\\%")
    text = text.replace("\n", " ")
    return text


def _find_caption_font() -> str:
    """Picks a bold system font for burned-in captions if one is available,
    else falls back to ffmpeg's built-in default (no fontfile= arg)."""
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    ]
    for c in candidates:
        if Path(c).exists():
            return c
    return ""


def assemble_video(workflow_id: str, scenes: list, burn_captions: bool = True) -> dict:
    """
    Builds the final vertical video for a workflow whose Stage 2 media
    (scene images + voiceover.mp3) already exists on disk.

    Returns {"success": True, "path": "..."} or
            {"success": False, "error": "..."}.
    """
    check = ensure_ffmpeg()
    if not check["success"]:
        return check

    assets = _assets_dir(workflow_id)
    voiceover_path = assets / "voiceover.mp3"
    if not voiceover_path.exists():
        return {"success": False, "error": f"voiceover.mp3 not found in {assets} — Stage 2 must complete first."}

    image_paths = []
    for i, scene in enumerate(scenes, start=1):
        scene_num = scene.get("scene_number", i)
        img_path = assets / f"scene_{scene_num:02d}.png"
        if not img_path.exists():
            return {"success": False, "error": f"Missing scene image: {img_path.name} — Stage 2 must complete first."}
        image_paths.append((scene_num, img_path, (scene.get("narration") or "").strip()))

    try:
        total_duration = probe_duration(voiceover_path)
    except (subprocess.CalledProcessError, json.JSONDecodeError, ValueError) as e:
        return {"success": False, "error": f"Could not read voice-over duration: {e}"}

    if total_duration <= 0:
        return {"success": False, "error": "Voice-over duration reported as 0 — file may be corrupt."}

    durations = _scene_durations([s for s in scenes], total_duration)

    # 1. Build an ffmpeg concat-demuxer list file — one entry per scene
    #    image with its computed duration. Each image is scaled/cropped to
    #    fill the vertical frame (center-crop, no letterboxing).
    concat_list_path = assets / "concat_list.txt"
    with open(concat_list_path, "w", encoding="utf-8") as f:
        for (scene_num, img_path, _narration), dur in zip(image_paths, durations):
            f.write(f"file '{img_path.as_posix()}'\n")
            f.write(f"duration {dur:.3f}\n")
        # ffmpeg's concat demuxer requires the last file repeated without a
        # duration line, or the final image gets truncated to ~0s.
        f.write(f"file '{image_paths[-1][1].as_posix()}'\n")

    silent_video_path = assets / "slideshow_silent.mp4"
    scale_filter = (
        f"scale={VERTICAL_WIDTH}:{VERTICAL_HEIGHT}:force_original_aspect_ratio=increase,"
        f"crop={VERTICAL_WIDTH}:{VERTICAL_HEIGHT},setsar=1"
    )

    cmd_slideshow = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0", "-i", str(concat_list_path),
        "-vf", scale_filter,
        "-r", "30",
        "-pix_fmt", "yuv420p",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        str(silent_video_path),
    ]
    try:
        subprocess.run(cmd_slideshow, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        return {"success": False, "error": f"ffmpeg slideshow assembly failed: {e.stderr[-500:] if e.stderr else e}"}

    # 2. Optionally burn in per-scene narration captions as a second pass —
    #    kept as a separate pass (rather than one giant filter graph) so a
    #    caption-drawing failure doesn't also blow up the slideshow itself.
    captioned_video_path = assets / "slideshow_captioned.mp4"
    video_for_mux = silent_video_path

    if burn_captions:
        font = _find_caption_font()
        drawtext_filters = []
        cursor = 0.0
        for (scene_num, _img_path, narration), dur in zip(image_paths, durations):
            start_t = cursor
            end_t = cursor + dur
            cursor = end_t
            if not narration:
                continue
            text = _escape_drawtext(narration)
            font_arg = f"fontfile='{font}':" if font else ""
            drawtext_filters.append(
                f"drawtext={font_arg}text='{text}':fontcolor=white:fontsize=54:"
                f"box=1:boxcolor=black@0.55:boxborderw=20:"
                f"x=(w-text_w)/2:y=h-th-160:line_spacing=8:"
                f"enable='between(t,{start_t:.3f},{end_t:.3f})'"
            )

        if drawtext_filters:
            cmd_captions = [
                "ffmpeg", "-y",
                "-i", str(silent_video_path),
                "-vf", ",".join(drawtext_filters),
                "-c:v", "libx264", "-preset", "medium", "-crf", "18",
                "-pix_fmt", "yuv420p",
                str(captioned_video_path),
            ]
            try:
                subprocess.run(cmd_captions, check=True, capture_output=True, text=True)
                video_for_mux = captioned_video_path
            except subprocess.CalledProcessError as e:
                # Non-fatal — fall back to the silent (caption-free) video
                # rather than failing the whole assembly over a text overlay.
                print(f"[tiktok_pipeline] ⚠️ Caption burn-in failed, continuing without captions: "
                      f"{e.stderr[-300:] if e.stderr else e}")
                video_for_mux = silent_video_path

    # 3. Mux the voice-over audio onto the (captioned or silent) video.
    final_path = assets / "final_video.mp4"
    cmd_mux = [
        "ffmpeg", "-y",
        "-i", str(video_for_mux),
        "-i", str(voiceover_path),
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest",
        "-movflags", "+faststart",
        str(final_path),
    ]
    try:
        subprocess.run(cmd_mux, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        return {"success": False, "error": f"ffmpeg audio mux failed: {e.stderr[-500:] if e.stderr else e}"}

    if not final_path.exists() or final_path.stat().st_size == 0:
        return {"success": False, "error": "ffmpeg reported success but produced an empty/missing output file."}

    # Clean up intermediate files — keep only what Stage 4 / the user needs.
    for tmp in (silent_video_path, captioned_video_path, concat_list_path):
        try:
            if tmp.exists() and tmp != final_path:
                tmp.unlink()
        except OSError:
            pass

    return {"success": True, "path": str(final_path), "duration": total_duration}
