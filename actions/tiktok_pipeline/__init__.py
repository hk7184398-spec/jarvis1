"""
actions/tiktok_pipeline/ — TikTok Content Automation, V1 Stages 1-2.

Stage 1: creates a brand-new TikTok video concept from just a topic/niche
(no existing video needed) — analyzes the niche, writes a voiceover script,
splits it into scene-by-scene image prompts, then stops for human approval.

Stage 2 (continue_tiktok_workflow, only after explicit approval): generates
one image per scene and a full voice-over audio file, then stops again at a
second gate before video assembly (Stage 3, not yet built).

Different from cut_viral_clips, which extracts clips from an existing video
the user already has.
"""

# actions/tiktok_pipeline/__init__.py
#
# Jarvis module: TikTok Content Automation — V1, Stages 1-2 only
# (niche -> analysis -> script -> scene prompts -> [human approval] ->
# scene images -> voice-over -> [human approval] -> STOP. Video assembly,
# SEO/hashtags, and publish are later stages, not yet built).
#
# Wire-up (in main.py):
#   from actions.tiktok_pipeline import TOOL_DECLARATIONS as tiktok_tools
#   from actions.tiktok_pipeline import start_tiktok_workflow, get_tiktok_status, continue_tiktok_workflow
#   TOOL_DECLARATIONS.extend(tiktok_tools)
#   ...
#   elif name == "start_tiktok_workflow":
#       r = await loop.run_in_executor(None, lambda: start_tiktok_workflow(parameters=args, player=self.ui))
#   elif name == "get_tiktok_status":
#       r = await loop.run_in_executor(None, lambda: get_tiktok_status(parameters=args, player=self.ui))
#   elif name == "continue_tiktok_workflow":
#       r = await loop.run_in_executor(None, lambda: continue_tiktok_workflow(parameters=args, player=self.ui))
#
# Architecture note: this module NEVER auto-proceeds past a human approval
# gate. The workflow sits at "awaiting_approval" (after Stage 1) or
# "media_ready" (after Stage 2) until the user explicitly confirms —
# matching Jarvis's "no confirmation without verified success, no publish
# without human approval" rule.

from actions.tiktok_pipeline import state
from actions.tiktok_pipeline.stage1_niche_script import run_stage1
from actions.tiktok_pipeline.stage2_media import generate_scene_images, generate_voiceover, DEFAULT_VOICE

TOOL_DECLARATIONS = [
    {
        "name": "start_tiktok_workflow",
        "description": (
            "Creates a brand-new TikTok video CONCEPT FROM SCRATCH, given only "
            "a topic/niche — no existing video needed. Use this whenever the "
            "user asks to 'banao'/'create'/'make' a new TikTok video about a "
            "topic (e.g. 'tiktok video banao vegetables pe', 'funny animated "
            "video banao cats pe'), NOT when the user gives an existing video "
            "URL or file to cut clips from (that's cut_viral_clips instead). "
            "This tool currently only completes Stage 1 of the pipeline: it "
            "analyzes the niche, writes a voiceover script, and splits it "
            "into scene-by-scene image prompts, then stops for the user's "
            "review. It does NOT generate images/audio or publish anything "
            "itself — after the user approves the script, call "
            "continue_tiktok_workflow to generate scene images and the "
            "voice-over (Stage 2). Video assembly and publishing are later "
            "stages, not yet built. Always call this tool immediately once a "
            "niche/topic is given; don't ask clarifying questions first "
            "unless no topic was given at all."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "niche": {
                    "type": "STRING",
                    "description": "The content niche/topic for this video, e.g. 'personal finance tips', 'stoic philosophy quotes', 'funny vegetables'"
                }
            },
            "required": ["niche"]
        }
    },
    {
        "name": "get_tiktok_status",
        "description": (
            "Reports the current stage/status of a TikTok content workflow. "
            "If no workflow_id is given, reports on the most recently "
            "started workflow."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "workflow_id": {
                    "type": "STRING",
                    "description": "Optional. The workflow ID to check. Omit to check the latest workflow."
                }
            },
            "required": []
        }
    },
    {
        "name": "continue_tiktok_workflow",
        "description": (
            "Approves a TikTok workflow's Stage 1 output (script + scene "
            "prompts) and proceeds to Stage 2: generates one image per scene "
            "and a full voice-over audio file from the script. ONLY call "
            "this when the user EXPLICITLY approves/confirms after reviewing "
            "the script from start_tiktok_workflow (e.g. user says 'haan "
            "aage badho', 'approved', 'ye theek hai, continue karo'). Never "
            "call this automatically right after start_tiktok_workflow — it "
            "requires explicit human approval first, per the workflow's "
            "approval gate. Does NOT yet assemble a final video or publish "
            "anything — that's a later stage, not yet built."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "workflow_id": {
                    "type": "STRING",
                    "description": "Optional. The workflow ID to continue. Omit to continue the most recent workflow."
                },
                "voice": {
                    "type": "STRING",
                    "description": "Optional edge-tts voice name, e.g. 'en-US-GuyNeural', 'en-US-JennyNeural'. Defaults to a natural US English voice."
                }
            },
            "required": []
        }
    },
]


def start_tiktok_workflow(parameters=None, response=None, player=None, session_memory=None) -> str:
    params = parameters or {}
    niche  = params.get("niche", "").strip()

    if not niche:
        return "What niche should this TikTok video be about, sir?"

    if player:
        player.write_log(f"[TikTok] Starting workflow — niche: {niche}")

    wf = state.new_workflow(niche)

    try:
        state.advance(wf, "niche_analysis")
        result = run_stage1(niche)

        state.advance(wf, "niche_analysis", result["analysis"])
        state.advance(wf, "script_generation", {"script": result["script"]})
        state.advance(wf, "scene_prompts", {"scenes": result["scenes"]})
        state.advance(wf, "awaiting_approval")

        if player:
            player.write_log(f"[TikTok] Workflow {wf['workflow_id']} ready for approval")

        scene_count = len(result["scenes"])
        preview     = result["script"][:200] + ("..." if len(result["script"]) > 200 else "")

        return (
            f"Script ready for the '{niche}' video, sir (workflow {wf['workflow_id']}). "
            f"{scene_count} scenes planned. Script preview: {preview} "
            f"This is waiting for your approval before I go any further — "
            f"nothing has been generated as video or published."
        )

    except Exception as e:
        state.mark_failed(wf, str(e))
        print(f"[TikTok] ❌ Stage 1 failed for workflow {wf['workflow_id']}: {e}")
        return (
            f"Stage 1 failed for the '{niche}' workflow, sir: {e}. "
            f"Workflow {wf['workflow_id']} has been marked as failed, not silently retried."
        )


def get_tiktok_status(parameters=None, response=None, player=None, session_memory=None) -> str:
    params      = parameters or {}
    workflow_id = params.get("workflow_id", "").strip()

    wf = state.load(workflow_id) if workflow_id else state.latest()

    if wf is None:
        return "No TikTok workflow found, sir." if not workflow_id else f"No workflow found with ID {workflow_id}, sir."

    status_line = f"Workflow {wf['workflow_id']} ('{wf['niche']}') — stage: {wf['stage']}, status: {wf['status']}"
    if wf.get("error"):
        status_line += f", error: {wf['error']}"

    return status_line


def continue_tiktok_workflow(parameters=None, response=None, player=None, session_memory=None) -> str:
    """Stage 2 dispatcher: runs ONLY after explicit human approval of Stage 1.
    Generates scene images, then the voice-over — advancing state after each
    verified success, and stopping at the FIRST failure without silently
    proceeding (same crash-safe pattern as start_tiktok_workflow)."""
    params      = parameters or {}
    workflow_id = params.get("workflow_id", "").strip()
    voice       = params.get("voice", "").strip() or DEFAULT_VOICE

    wf = state.load(workflow_id) if workflow_id else state.latest()

    if wf is None:
        return "No TikTok workflow found to continue, sir." if not workflow_id else f"No workflow found with ID {workflow_id}, sir."

    if wf["stage"] != "awaiting_approval":
        return (
            f"Workflow {wf['workflow_id']} is at stage '{wf['stage']}', not "
            f"awaiting approval — nothing to continue right now, sir."
        )

    scenes = wf["data"].get("scene_prompts", {}).get("scenes", [])
    script = wf["data"].get("script_generation", {}).get("script", "")

    if player:
        player.write_log(f"[TikTok] Approved — generating media for workflow {wf['workflow_id']}")

    try:
        image_result = generate_scene_images(scenes, wf["workflow_id"])
        if not image_result["success"]:
            state.mark_failed(wf, f"Scene {image_result.get('failed_scene')} image generation failed: {image_result.get('error')}")
            return (
                f"Image generation failed at scene {image_result.get('failed_scene')}, "
                f"sir: {image_result.get('error')}. Workflow {wf['workflow_id']} marked "
                f"as failed, not silently retried."
            )
        state.advance(wf, "image_generation", {"images": image_result["results"]})

        voice_result = generate_voiceover(script, wf["workflow_id"], voice)
        if not voice_result["success"]:
            state.mark_failed(wf, voice_result["error"])
            return (
                f"Voice-over generation failed for workflow {wf['workflow_id']}, sir: "
                f"{voice_result['error']}. Marked as failed, not silently retried."
            )
        state.advance(wf, "voiceover_generation", {"voiceover_path": voice_result["path"]})
        state.advance(wf, "media_ready")

        if player:
            player.write_log(f"[TikTok] Workflow {wf['workflow_id']} media ready for review")

        return (
            f"Media ready for workflow {wf['workflow_id']}, sir — "
            f"{len(image_result['results'])} scene images and the voice-over "
            f"are saved. Waiting for your review before video assembly, "
            f"which isn't built yet."
        )

    except Exception as e:
        state.mark_failed(wf, str(e))
        return (
            f"Stage 2 crashed for workflow {wf['workflow_id']}, sir: {e}. "
            f"Marked as failed, not silently retried."
        )
