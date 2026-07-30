# actions/tiktok_pipeline/state.py
# Crash-safe JSON workflow state tracker for the TikTok Automation pipeline.
#
# Design principle (per Jarvis architecture rules):
#   - Every stage transition is written to disk atomically (write to a temp
#     file, then os.replace) so a crash mid-write never corrupts state.
#   - The Python layer controls the stage sequence deterministically.
#     The LLM is only ever used inside a stage to generate content — never
#     to decide whether a stage "succeeded". A stage is only marked
#     complete after its underlying function returns success=True.
#   - Nothing is published/confirmed to the user unless a human approval
#     gate for that stage has been explicitly passed (see PENDING_APPROVAL).

import json
import os
import time
import uuid
from pathlib import Path
from typing import Optional

STATE_DIR = Path.home() / ".jarvis" / "tiktok_workflows"
STATE_DIR.mkdir(parents=True, exist_ok=True)

# Canonical stage sequence for the V1 pipeline. Later stages (image gen,
# TTS, video assembly, SEO/hashtags, publish) get appended here as they're
# built — the state file format doesn't need to change.
STAGES = [
    "niche_input",
    "niche_analysis",
    "script_generation",
    "scene_prompts",
    "awaiting_approval",   # human approval gate — nothing proceeds past here automatically
]


def _path_for(workflow_id: str) -> Path:
    return STATE_DIR / f"{workflow_id}.json"


def new_workflow(niche: str) -> dict:
    """Creates a new workflow record and writes it to disk immediately."""
    workflow_id = uuid.uuid4().hex[:12]
    state = {
        "workflow_id": workflow_id,
        "niche": niche,
        "stage": "niche_input",
        "status": "in_progress",
        "created_at": time.time(),
        "updated_at": time.time(),
        "data": {},          # per-stage outputs accumulate here
        "error": None,
    }
    save(state)
    return state


def save(state: dict) -> None:
    """Atomic write: temp file + os.replace, so a crash never leaves a
    half-written state file behind."""
    state["updated_at"] = time.time()
    path    = _path_for(state["workflow_id"])
    tmp_path = path.with_suffix(".tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)
    os.replace(tmp_path, path)


def load(workflow_id: str) -> Optional[dict]:
    path = _path_for(workflow_id)
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def latest() -> Optional[dict]:
    """Returns the most recently updated workflow, if any — used when the
    user says 'what's the status' without naming a workflow id."""
    files = sorted(STATE_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        return None
    with open(files[0], "r", encoding="utf-8") as f:
        return json.load(f)


def advance(state: dict, stage: str, payload: Optional[dict] = None) -> dict:
    """Moves a workflow to a new stage and stores that stage's output.
    Only called after the stage's underlying function has verifiably
    succeeded — never speculatively."""
    state["stage"] = stage
    if payload is not None:
        state["data"][stage] = payload
    save(state)
    return state


def mark_failed(state: dict, error: str) -> dict:
    state["status"] = "failed"
    state["error"]  = error
    save(state)
    return state
