"""
actions/tiktok_pipeline/ — TikTok Content Automation, V1 Stage 1.

Creates a brand-new TikTok video concept from just a topic/niche (no
existing video needed): analyzes the niche, writes a voiceover script,
splits it into scene-by-scene image prompts, then stops for human
approval. Does NOT yet generate video/animation/audio or publish —
that's later stages. Different from cut_viral_clips, which extracts
clips from an existing video the user already has.
"""

# actions/tiktok_pipeline/__init__.py
#
# Jarvis module: TikTok Content Automation — V1, Stage 1 only
# (niche -> analysis -> script -> scene prompts, then STOP for human
# approval before anything downstream — image gen, TTS, video, publish —
# is built).
#
# Wire-up (in main.py):
#   from actions.tiktok_pipeline import TOOL_DECLARATIONS as tiktok_tools
#   from actions.tiktok_pipeline import start_tiktok_workflow, get_tiktok_status
#   TOOL_DECLARATIONS.extend(tiktok_tools)
#   ...
#   elif name == "start_tiktok_workflow":
#       r = await loop.run_in_executor(None, lambda: start_tiktok_workflow(parameters=args, player=self.ui))
#   elif name == "get_tiktok_status":
#       r = await loop.run_in_executor(None, lambda: get_tiktok_status(parameters=args, player=self.ui))
#
# Architecture note: this module NEVER auto-proceeds past scene_prompts.
# The workflow sits at stage "awaiting_approval" until the user explicitly
# confirms — matching Jarvis's "no confirmation without verified success,
# no publish without human approval" rule.

from actions.tiktok_pipeline import state
from actions.tiktok_pipeline.stage1_niche_script import run_stage1

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
            "review. It does NOT yet generate actual video, animation, images, "
            "or audio, and does NOT publish anything — say so plainly if the "
            "user asks for the finished video, rather than refusing the "
            "request outright. Always call this tool immediately once a "
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
