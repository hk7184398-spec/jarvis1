# actions/tiktok_pipeline/stage1_niche_script.py
# Stage 1 of the TikTok Automation pipeline: niche -> analysis -> script -> scene prompts.
#
# Every LLM call here is content generation only (per Jarvis architecture
# rules). None of these functions decide whether the workflow proceeds —
# that's the caller's job, gated on human approval before publish.

from or_client import client


def analyze_niche(niche: str) -> dict:
    """
    Analyzes a content niche and returns structure Jarvis can use to steer
    script generation: target audience, tone, hook style, typical video
    length, and 3-5 content angle ideas.
    """
    prompt = (
        f"Analyze this TikTok content niche: \"{niche}\".\n\n"
        "Return JSON with exactly these keys:\n"
        '  "audience": short description of the target audience,\n'
        '  "tone": recommended tone/voice (e.g. energetic, calm, comedic),\n'
        '  "hook_style": what kind of opening hook works best for this niche,\n'
        '  "ideal_length_seconds": integer, ideal video length in seconds (15-60),\n'
        '  "angles": array of 3-5 short content angle ideas within this niche.'
    )
    return client.chat_json(
        prompt,
        system=(
            "You are the niche-analysis stage of a TikTok content pipeline. "
            "Return ONLY valid JSON, no markdown fences, no commentary."
        ),
    )


def generate_script(niche: str, analysis: dict) -> str:
    """
    Generates a short-form vertical video script (voiceover text) tailored
    to the niche analysis. Plain text, no scene markers — scene splitting
    happens in generate_scene_prompts.
    """
    prompt = (
        f"Write a TikTok voiceover script for the niche: \"{niche}\".\n\n"
        f"Target audience: {analysis.get('audience', 'general')}\n"
        f"Tone: {analysis.get('tone', 'engaging')}\n"
        f"Hook style: {analysis.get('hook_style', 'strong opening line')}\n"
        f"Target length: ~{analysis.get('ideal_length_seconds', 30)} seconds "
        "of spoken narration.\n\n"
        "Write ONLY the spoken narration text, as plain sentences. "
        "Start with a strong hook in the first sentence. "
        "No scene directions, no timestamps, no formatting — just the words "
        "to be spoken."
    )
    return client.chat(
        prompt,
        system=(
            "You are the scriptwriting stage of a TikTok content pipeline. "
            "Write natural, spoken-language narration — short sentences, "
            "punchy, no filler."
        ),
        max_tokens=800,
    )


def generate_scene_prompts(script: str, niche: str) -> list[dict]:
    """
    Splits the script into scenes and generates an image-generation prompt
    for each scene, matched to the narration for that scene.
    """
    prompt = (
        f"Split this TikTok script into 4-8 scenes for a niche of \"{niche}\", "
        "and for each scene provide the narration slice and a detailed "
        "AI image-generation prompt that visually matches it.\n\n"
        f"SCRIPT:\n{script}\n\n"
        "Return JSON with key \"scenes\": an array of objects, each with:\n"
        '  "scene_number": integer,\n'
        '  "narration": the exact slice of narration for this scene,\n'
        '  "image_prompt": a detailed visual description suitable for an '
        "AI image generator (style, subject, composition, lighting)."
    )
    result = client.chat_json(
        prompt,
        system=(
            "You are the scene-planning stage of a TikTok content pipeline. "
            "Return ONLY valid JSON, no markdown fences, no commentary."
        ),
    )
    return result.get("scenes", [])


def run_stage1(niche: str) -> dict:
    """
    Runs the full Stage 1 sequence and returns everything needed for the
    human approval gate. Raises on failure — the caller (dispatch layer)
    is responsible for catching and recording the error in workflow state.
    """
    analysis = analyze_niche(niche)
    script   = generate_script(niche, analysis)
    scenes   = generate_scene_prompts(script, niche)

    return {
        "analysis": analysis,
        "script": script,
        "scenes": scenes,
    }
