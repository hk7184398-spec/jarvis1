"""
actions/tiktok_pipeline/ — TikTok Content Automation, V1 Stages 1-4 (full pipeline).

Stage 1: creates a brand-new TikTok video concept from just a topic/niche
(no existing video needed) — analyzes the niche, writes a voiceover script,
splits it into scene-by-scene image prompts, then stops for human approval.

Stage 2 (continue_tiktok_workflow, only after explicit approval): generates
one image per scene and a full voice-over audio file, then stops again at a
second gate before video assembly.

Stage 3 + 4a (finalize_tiktok_video, only after explicit approval): assembles
the final vertical video (ffmpeg slideshow + captions + audio mux) and
generates SEO metadata (title/caption/hashtags), then stops at a THIRD gate
before anything is uploaded/posted anywhere.

Stage 4b (publish_tiktok_video, only after explicit approval of the exact
caption/hashtags): stages the video for posting via browser automation
(TikTok's Content Posting API needs app review, so this is the default
path — see stage4_publish.py). Never actually clicks "Post" unless
TIKTOK_AUTO_PUBLISH=true is set in .env.

Different from cut_viral_clips, which extracts clips from an existing video
the user already has.
"""

# actions/tiktok_pipeline/__init__.py
#
# Jarvis module: TikTok Content Automation — V1, full pipeline
# (niche -> analysis -> script -> scene prompts -> [human approval] ->
# scene images -> voice-over -> [human approval] -> video assembly ->
# SEO metadata -> [human approval] -> publish-staging (draft by default) ->
# [publish only if TIKTOK_AUTO_PUBLISH=true]).
#
# Wire-up (in main.py):
#   from actions.tiktok_pipeline import TOOL_DECLARATIONS as tiktok_tools
#   from actions.tiktok_pipeline import (
#       start_tiktok_workflow, get_tiktok_status, continue_tiktok_workflow,
#       finalize_tiktok_video, publish_tiktok_video,
#   )
#   TOOL_DECLARATIONS.extend(tiktok_tools)
#   ...
#   elif name == "start_tiktok_workflow":
#       r = await loop.run_in_executor(None, lambda: start_tiktok_workflow(parameters=args, player=self.ui))
#   elif name == "get_tiktok_status":
#       r = await loop.run_in_executor(None, lambda: get_tiktok_status(parameters=args, player=self.ui))
#   elif name == "continue_tiktok_workflow":
#       r = await loop.run_in_executor(None, lambda: continue_tiktok_workflow(parameters=args, player=self.ui))
#   elif name == "finalize_tiktok_video":
#       r = await loop.run_in_executor(None, lambda: finalize_tiktok_video(parameters=args, player=self.ui))
#   elif name == "publish_tiktok_video":
#       r = await loop.run_in_executor(None, lambda: publish_tiktok_video(parameters=args, player=self.ui))
#
# Architecture note: this module NEVER auto-proceeds past a human approval
# gate. The workflow sits at "awaiting_approval" (after Stage 1),
# "media_ready" (after Stage 2), or "ready_to_publish" (after Stage 3/4a)
# until the user explicitly confirms — matching Jarvis's "no confirmation
# without verified success, no publish without human approval" rule. Even
# with TIKTOK_AUTO_PUBLISH=true, publish_tiktok_video() still requires an
# explicit call after the user has seen the caption/hashtags (per
# JARVIS_SKILLS_MASTER_PROMPT.md section 10.4 — auto-publish mode still
# needs the caption confirmed, it only skips the *second* manual "click
# Post yourself" step).

from actions.tiktok_pipeline import state
from actions.tiktok_pipeline.stage1_niche_script import run_stage1
from actions.tiktok_pipeline.stage2_media import generate_scene_images, generate_voiceover, DEFAULT_VOICE
from actions.tiktok_pipeline.stage3_assembly import assemble_video
from actions.tiktok_pipeline.stage4_publish import generate_seo, stage_for_publish

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
    {
        "name": "finalize_tiktok_video",
        "description": (
            "Approves a TikTok workflow's Stage 2 media (scene images + "
            "voice-over) and proceeds to Stage 3+4a: assembles the final "
            "vertical video with ffmpeg (scene images timed to the "
            "voice-over, burned-in captions, audio muxed in) and generates "
            "SEO metadata (title, caption, hashtags). ONLY call this when "
            "the user EXPLICITLY approves the media from "
            "continue_tiktok_workflow (e.g. 'media theek hai, video bana "
            "do', 'approved, finalize karo'). Never call automatically "
            "right after continue_tiktok_workflow. Does NOT upload or post "
            "anything — stops at a third approval gate before "
            "publish_tiktok_video can be called."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "workflow_id": {
                    "type": "STRING",
                    "description": "Optional. The workflow ID to finalize. Omit to use the most recent workflow."
                },
                "burn_captions": {
                    "type": "BOOLEAN",
                    "description": "Whether to burn narration captions into the video. Defaults to true."
                }
            },
            "required": []
        }
    },
    {
        "name": "publish_tiktok_video",
        "description": (
            "Stages the finalized TikTok video for posting: opens TikTok's "
            "upload page in the browser, uploads the video, and fills the "
            "caption/hashtags. Does NOT click the final 'Post' button "
            "unless TIKTOK_AUTO_PUBLISH=true is set in .env — by default "
            "it stops with the post staged in the browser for the user to "
            "review and publish manually. ONLY call this when the user "
            "EXPLICITLY approves the exact title/caption/hashtags shown by "
            "finalize_tiktok_video (e.g. 'caption theek hai, publish kar "
            "do', 'ye hashtags use karo aur post karo'). If the user wants "
            "to change the caption or hashtags first, pass the edited "
            "values — do not silently use the AI-generated ones after the "
            "user asked for changes."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "workflow_id": {
                    "type": "STRING",
                    "description": "Optional. The workflow ID to publish. Omit to use the most recent workflow."
                },
                "caption": {
                    "type": "STRING",
                    "description": "Optional. Overrides the AI-generated caption with user-edited text."
                },
                "hashtags": {
                    "type": "ARRAY",
                    "items": {"type": "STRING"},
                    "description": "Optional. Overrides the AI-generated hashtags (without # symbols) with a user-edited list."
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
            f"are saved. Waiting for your review — call finalize_tiktok_video "
            f"once you approve, to assemble the final video."
        )

    except Exception as e:
        state.mark_failed(wf, str(e))
        return (
            f"Stage 2 crashed for workflow {wf['workflow_id']}, sir: {e}. "
            f"Marked as failed, not silently retried."
        )


def finalize_tiktok_video(parameters=None, response=None, player=None, session_memory=None) -> str:
    """Stage 3+4a dispatcher: runs ONLY after explicit human approval of
    Stage 2's media. Assembles the final video, then generates SEO
    metadata — advancing state after each verified success, stopping at
    the FIRST failure without silently proceeding."""
    params        = parameters or {}
    workflow_id   = params.get("workflow_id", "").strip()
    burn_captions = params.get("burn_captions", True)

    wf = state.load(workflow_id) if workflow_id else state.latest()

    if wf is None:
        return "No TikTok workflow found to finalize, sir." if not workflow_id else f"No workflow found with ID {workflow_id}, sir."

    if wf["stage"] != "media_ready":
        return (
            f"Workflow {wf['workflow_id']} is at stage '{wf['stage']}', not "
            f"media_ready — nothing to finalize right now, sir."
        )

    scenes = wf["data"].get("scene_prompts", {}).get("scenes", [])
    script = wf["data"].get("script_generation", {}).get("script", "")
    niche  = wf.get("niche", "")

    if player:
        player.write_log(f"[TikTok] Assembling final video for workflow {wf['workflow_id']}")

    try:
        assembly_result = assemble_video(wf["workflow_id"], scenes, burn_captions=burn_captions)
        if not assembly_result["success"]:
            state.mark_failed(wf, f"Video assembly failed: {assembly_result['error']}")
            return (
                f"Video assembly failed for workflow {wf['workflow_id']}, sir: "
                f"{assembly_result['error']}. Marked as failed, not silently retried."
            )
        state.advance(wf, "video_assembly", {"video_path": assembly_result["path"], "duration": assembly_result["duration"]})

        seo = generate_seo(niche, script)
        state.advance(wf, "seo_generation", {"seo": seo})
        state.advance(wf, "ready_to_publish")

        if player:
            player.write_log(f"[TikTok] Workflow {wf['workflow_id']} ready to publish")

        hashtags_preview = ", ".join(f"#{h}" for h in seo.get("hashtags", []))

        return (
            f"Final video assembled for workflow {wf['workflow_id']}, sir — "
            f"saved at {assembly_result['path']} ({assembly_result['duration']:.1f}s). "
            f"Suggested title: \"{seo.get('title', '')}\". "
            f"Suggested caption: \"{seo.get('caption', '')}\". "
            f"Suggested hashtags: {hashtags_preview}. "
            f"Nothing has been uploaded or posted — call publish_tiktok_video once "
            f"you approve this caption/hashtags (or give me edited ones)."
        )

    except Exception as e:
        state.mark_failed(wf, str(e))
        return (
            f"Stage 3/4a crashed for workflow {wf['workflow_id']}, sir: {e}. "
            f"Marked as failed, not silently retried."
        )


def publish_tiktok_video(parameters=None, response=None, player=None, session_memory=None) -> str:
    """Stage 4b dispatcher: runs ONLY after explicit human approval of the
    exact caption/hashtags. Stages the video for posting via browser
    automation and, by default, stops short of the final Post click (see
    stage4_publish.stage_for_publish for the TIKTOK_AUTO_PUBLISH guardrail)."""
    params      = parameters or {}
    workflow_id = params.get("workflow_id", "").strip()
    override_caption  = params.get("caption")
    override_hashtags = params.get("hashtags")

    wf = state.load(workflow_id) if workflow_id else state.latest()

    if wf is None:
        return "No TikTok workflow found to publish, sir." if not workflow_id else f"No workflow found with ID {workflow_id}, sir."

    if wf["stage"] not in ("ready_to_publish", "publish_staged"):
        return (
            f"Workflow {wf['workflow_id']} is at stage '{wf['stage']}', not "
            f"ready_to_publish — call finalize_tiktok_video first, sir."
        )

    video_path = wf["data"].get("video_assembly", {}).get("video_path", "")
    seo        = wf["data"].get("seo_generation", {}).get("seo", {})
    caption    = override_caption if override_caption is not None else seo.get("caption", "")
    hashtags   = override_hashtags if override_hashtags is not None else seo.get("hashtags", [])

    if not video_path:
        return f"No assembled video found for workflow {wf['workflow_id']}, sir — finalize_tiktok_video must complete first."

    if player:
        player.write_log(f"[TikTok] Staging publish for workflow {wf['workflow_id']}")

    try:
        result = stage_for_publish(wf["workflow_id"], video_path, caption, hashtags)
        if not result["success"]:
            return f"Publish staging failed for workflow {wf['workflow_id']}, sir: {result['error']}"

        state.advance(wf, "published" if result["published"] else "publish_staged", {
            "caption": caption, "hashtags": hashtags, "published": result["published"],
        })

        if player:
            player.write_log(f"[TikTok] Workflow {wf['workflow_id']}: {result['message']}")

        return f"{result['message']} (workflow {wf['workflow_id']})"

    except Exception as e:
        state.mark_failed(wf, str(e))
        return (
            f"Stage 4b crashed for workflow {wf['workflow_id']}, sir: {e}. "
            f"Marked as failed, not silently retried."
        )
