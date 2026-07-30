# actions/tiktok_pipeline/stage2_media.py
# Stage 2 of the TikTok Automation pipeline: scene images + voice-over (TTS).
#
# Runs ONLY after the user has explicitly approved Stage 1's output (script +
# scene prompts) via continue_tiktok_workflow. Generates:
#   - one image per scene, using Gemini's image generation model
#   - one voice-over audio file for the full script, using edge-tts
#     (free, no API key required)
# Then the caller advances the workflow to a second gate ("media_ready") for
# human review before video assembly (Stage 3, not yet built) touches
# anything.
#
# Design principle (per Jarvis architecture rules, same as Stage 1):
#   - Every function here only GENERATES content — it never decides the
#     workflow should proceed. The caller (__init__.py) advances state only
#     after a function has verifiably succeeded (a real file written to
#     disk), never speculatively.
#   - A failure on any one scene stops the whole stage and reports exactly
#     which scene failed — no silent partial results.

import asyncio
from pathlib import Path

from core.gemini import get_genai_client
from actions.tiktok_pipeline.state import STATE_DIR

IMAGE_MODEL = "gemini-2.5-flash-image"
DEFAULT_VOICE = "en-US-GuyNeural"  # edge-tts voice — swap per niche/language as needed


def _assets_dir(workflow_id: str) -> Path:
    """Each workflow gets its own folder for generated images/audio,
    alongside the existing <workflow_id>.json state file."""
    d = STATE_DIR / workflow_id
    d.mkdir(parents=True, exist_ok=True)
    return d


# ---------------------------------------------------------------------------
# Images — one per scene
# ---------------------------------------------------------------------------

def generate_scene_image(prompt: str, out_path: Path) -> dict:
    """Generates a single scene image from its image_prompt and saves it as PNG."""
    client = get_genai_client()
    try:
        response = client.models.generate_content(
            model=IMAGE_MODEL,
            contents=prompt,
        )
    except Exception as e:
        return {"success": False, "error": f"Image generation API call failed: {e}"}

    image_bytes = None
    for candidate in getattr(response, "candidates", None) or []:
        content = getattr(candidate, "content", None)
        for part in getattr(content, "parts", None) or []:
            inline = getattr(part, "inline_data", None)
            if inline is not None and getattr(inline, "data", None):
                image_bytes = inline.data
                break
        if image_bytes:
            break

    if not image_bytes:
        return {"success": False, "error": "No image data in the model's response"}

    out_path.write_bytes(image_bytes)
    return {"success": True, "path": str(out_path)}


def generate_scene_images(scenes: list, workflow_id: str) -> dict:
    """Generates one image per scene, in order. Stops at the FIRST failure
    and reports which scene failed — never silently skips a scene, since a
    missing/wrong image would silently break video assembly later."""
    assets = _assets_dir(workflow_id)
    results = []

    for i, scene in enumerate(scenes, start=1):
        scene_num = scene.get("scene_number", i)
        out_path = assets / f"scene_{scene_num:02d}.png"
        r = generate_scene_image(scene.get("image_prompt", ""), out_path)
        r["scene_number"] = scene_num
        results.append(r)
        if not r["success"]:
            return {
                "success": False,
                "failed_scene": scene_num,
                "error": r["error"],
                "results": results,
            }

    return {"success": True, "results": results}


# ---------------------------------------------------------------------------
# Voice-over — full script, one audio file (edge-tts, free/offline)
# ---------------------------------------------------------------------------

async def _tts_save(text: str, out_path: Path, voice: str):
    import edge_tts
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(str(out_path))


def generate_voiceover(script: str, workflow_id: str, voice: str = DEFAULT_VOICE) -> dict:
    """Generates the full voice-over audio from the script. Runs the async
    edge-tts call synchronously via asyncio.run() — safe here because this
    function is always invoked from a worker thread (main.py's
    run_in_executor), never from Jarvis's own asyncio event loop."""
    assets = _assets_dir(workflow_id)
    out_path = assets / "voiceover.mp3"

    try:
        asyncio.run(_tts_save(script, out_path, voice))
    except Exception as e:
        return {"success": False, "error": f"TTS generation failed: {e}"}

    if not out_path.exists() or out_path.stat().st_size == 0:
        return {"success": False, "error": "TTS produced an empty or missing audio file"}

    return {"success": True, "path": str(out_path)}
