"""
actions/website_builder.py

Jarvis module: generates a premium Next.js website (Framer Motion + shadcn/ui)
from a business brief, following the "Claude Code Website Mastery Blueprint"
prompt framework.

DESIGN PRINCIPLE (per Jarvis architecture rules):
    - The LLM (Claude Sonnet) is used ONLY for content/code generation.
    - All execution control (scaffolding, file writes, npm install, build
      verification) is deterministic Python. Nothing is "confirmed" to the
      user unless the underlying verified step actually returned
      success=True. Jarvis's voice layer must gate on result["success"].

Wire-up:
    - Add `from actions import website_builder` in the dispatch loader.
    - Merge `website_builder.TOOL_DECLARATIONS` into the master tool list.
    - Route calls to `jarvis_tool_generate_website(**args)` in the dispatch
      table, matching whatever key format the existing dispatcher expects
      (adjust the dict key in TOOL_DECLARATIONS' "name" field if your
      dispatcher expects a different naming convention, e.g. snake_case
      prefix).

Requirements on the host machine:
    - Node.js + npm + npx available on PATH
    - ANTHROPIC_API_KEY set in the environment (or wire in your existing
      key-loading utility instead of os.environ.get below)
    - `pip install anthropic --break-system-packages` in the jarvis venv
"""

import os
import re
import json
import shutil
import subprocess
from pathlib import Path
from typing import Optional

import anthropic

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 16000
SITES_ROOT = os.path.expanduser("~/Downloads/jarvis1/generated_sites")
SUBPROCESS_TIMEOUT = 420  # seconds, per npm step

DEFAULT_SECTIONS = [
    "Hero", "Social Proof", "Problem", "Solution",
    "Features", "Testimonials", "CTA", "Footer",
]

DEFAULT_STYLE = "Linear + Apple + Stripe inspired, premium SaaS aesthetic"

# ---------------------------------------------------------------------------
# Tool declaration (Anthropic tool-use schema)
# ---------------------------------------------------------------------------

TOOL_DECLARATIONS = [
    {
        "name": "generate_website",
        "description": (
            "Generate a full premium Next.js website (TypeScript, Tailwind, "
            "Framer Motion animations, shadcn/ui components) from a business "
            "brief. Scaffolds a real project on disk, writes AI-generated "
            "page/component code, installs dependencies, and runs a "
            "production build to verify the result compiles before "
            "reporting success."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "project_name": {
                    "type": "STRING",
                    "description": "Folder-safe project name, e.g. 'acme-agency'",
                },
                "business_type": {
                    "type": "STRING",
                    "description": "e.g. 'AI automation SaaS', 'creative agency', 'personal brand'",
                },
                "target_audience": {"type": "STRING"},
                "goal": {
                    "type": "STRING",
                    "description": "e.g. 'lead generation', 'authority + trust building'",
                },
                "style_reference": {
                    "type": "STRING",
                    "description": "Design style reference, defaults to Linear+Apple+Stripe",
                },
                "theme": {
                    "type": "STRING",
                    "enum": ["dark", "light"],
                    "description": "Defaults to dark",
                },
                "sections": {
                    "type": "ARRAY",
                    "items": {"type": "STRING"},
                    "description": "Ordered page sections. Defaults to the standard high-converting structure.",
                },
            },
            "required": ["project_name", "business_type", "goal"],
        },
    }
]


# ---------------------------------------------------------------------------
# Step 1 — deterministic scaffold (no LLM involved)
# ---------------------------------------------------------------------------

def _run(cmd: list, cwd: str, label: str) -> dict:
    """Run a subprocess step and report a verified pass/fail result."""
    try:
        proc = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True,
            timeout=SUBPROCESS_TIMEOUT,
        )
        return {
            "label": label,
            "success": proc.returncode == 0,
            "returncode": proc.returncode,
            "stdout": proc.stdout[-4000:],
            "stderr": proc.stderr[-4000:],
        }
    except subprocess.TimeoutExpired:
        return {"label": label, "success": False, "error": "timeout"}
    except FileNotFoundError as e:
        return {"label": label, "success": False, "error": str(e)}


def _scaffold_nextjs(project_dir: str) -> list:
    """Create the Next.js project + install Framer Motion + shadcn init.
    Returns a list of step results; caller checks all(success) before
    proceeding."""
    parent = str(Path(project_dir).parent)
    name = Path(project_dir).name
    os.makedirs(parent, exist_ok=True)

    steps = []

    if not shutil.which("npx"):
        return [{"label": "check_npx", "success": False,
                  "error": "npx not found on PATH — install Node.js first"}]

    steps.append(_run(
        ["npx", "--yes", "create-next-app@latest", name,
         "--typescript", "--tailwind", "--eslint", "--app",
         "--src-dir", "--import-alias", "@/*", "--no-turbopack",
         "--use-npm"],
        cwd=parent, label="create_next_app",
    ))
    if not steps[-1]["success"]:
        return steps

    steps.append(_run(
        ["npm", "install", "framer-motion", "lucide-react", "clsx"],
        cwd=project_dir, label="install_framer_motion",
    ))
    if not steps[-1]["success"]:
        return steps

    steps.append(_run(
        ["npx", "--yes", "shadcn@latest", "init", "-y", "-d"],
        cwd=project_dir, label="shadcn_init",
    ))
    # shadcn init failure is non-fatal — continue without it, LLM will fall
    # back to plain Tailwind components if shadcn isn't available.

    return steps


# ---------------------------------------------------------------------------
# Step 2 — golden prompt construction (blueprint framework)
# ---------------------------------------------------------------------------

def _build_golden_prompt(business_type, target_audience, goal,
                          style_reference, theme, sections) -> str:
    sections_str = "\n".join(f"- {s}" for s in sections)
    return f"""Create a premium {business_type} website.

Target audience: {target_audience or "general visitors"}
Goal: {goal}
Style: {style_reference}
Theme: {theme}

Requirements:
- {theme.capitalize()} theme, modern typography, generous white space
- Smooth Framer Motion animations (fade-ins, stagger reveals on scroll, hover
  micro-interactions, smooth section transitions)
- Fully responsive, mobile-first
- Premium SaaS-grade visual hierarchy and conversion-focused copy
- Use shadcn/ui components where suitable; otherwise plain Tailwind

Page structure, in this order:
{sections_str}

Every section must implicitly answer: why trust us, why care, why act now.

This is a Next.js 14+ App Router project (TypeScript, Tailwind already
configured, framer-motion already installed). Generate the actual
production-ready source files needed to implement this page — do not
describe the design, write the real code.

Respond with ONLY a JSON object, no markdown fences, no commentary, in
exactly this shape:
{{
  "files": [
    {{"path": "src/app/page.tsx", "content": "..."}},
    {{"path": "src/components/Hero.tsx", "content": "..."}}
  ],
  "summary": "one paragraph description of what was built"
}}

All paths must be relative and stay within src/. Do not touch package.json,
tailwind.config, or next.config."""


# ---------------------------------------------------------------------------
# Step 3 — call Claude for code (LLM used only for content generation)
# ---------------------------------------------------------------------------

def _generate_code(prompt: str) -> dict:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return {"success": False, "error": "ANTHROPIC_API_KEY not set"}

    client = anthropic.Anthropic(api_key=api_key)
    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as e:
        return {"success": False, "error": f"API call failed: {e}"}

    text = "".join(
        block.text for block in response.content if block.type == "text"
    ).strip()

    # Strip stray markdown fences if the model added them anyway.
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as e:
        return {"success": False, "error": f"Could not parse model output as JSON: {e}",
                "raw": text[:2000]}

    if "files" not in parsed or not isinstance(parsed["files"], list):
        return {"success": False, "error": "Model output missing 'files' array",
                "raw": text[:2000]}

    return {"success": True, "files": parsed["files"],
            "summary": parsed.get("summary", "")}


# ---------------------------------------------------------------------------
# Step 4 — deterministic, path-safe file writing
# ---------------------------------------------------------------------------

def _write_files(project_dir: str, files: list) -> dict:
    project_root = Path(project_dir).resolve()
    written = []
    for f in files:
        rel_path = f.get("path", "")
        content = f.get("content", "")
        if not rel_path or ".." in rel_path.split("/"):
            continue  # skip unsafe paths, never trust LLM-supplied paths blindly
        if not rel_path.startswith("src/"):
            continue  # enforce the src/-only boundary set in the prompt

        target = (project_root / rel_path).resolve()
        if project_root not in target.parents:
            continue  # extra guard against path traversal

        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        written.append(rel_path)

    return {"success": len(written) > 0, "written": written}


# ---------------------------------------------------------------------------
# Step 5 — verification build (the actual proof of success)
# ---------------------------------------------------------------------------

def _verify_build(project_dir: str) -> dict:
    return _run(["npm", "run", "build"], cwd=project_dir, label="npm_run_build")


# ---------------------------------------------------------------------------
# Public entry point — this is what the dispatch table calls
# ---------------------------------------------------------------------------

def jarvis_tool_generate_website(
    project_name: str,
    business_type: str,
    goal: str,
    target_audience: Optional[str] = None,
    style_reference: str = DEFAULT_STYLE,
    theme: str = "dark",
    sections: Optional[list] = None,
) -> dict:
    """
    Full pipeline: scaffold -> generate code -> write files -> verify build.
    Returns success=True ONLY if the generated project actually compiles.
    Jarvis's voice/confirmation layer must gate on result["success"].
    """
    safe_name = re.sub(r"[^a-z0-9-]", "-", project_name.lower()).strip("-")
    if not safe_name:
        return {"success": False, "stage": "validate_name",
                "error": "project_name produced an empty slug"}

    project_dir = os.path.join(SITES_ROOT, safe_name)
    if os.path.exists(project_dir):
        return {"success": False, "stage": "validate_name",
                "error": f"'{safe_name}' already exists at {project_dir}"}

    sections = sections or DEFAULT_SECTIONS

    # Step 1: scaffold (deterministic)
    scaffold_steps = _scaffold_nextjs(project_dir)
    if not all(s.get("success", True) for s in scaffold_steps
               if s["label"] != "shadcn_init"):
        return {"success": False, "stage": "scaffold", "steps": scaffold_steps}

    # Step 2/3: prompt + LLM code generation
    prompt = _build_golden_prompt(
        business_type, target_audience, goal, style_reference, theme, sections
    )
    gen_result = _generate_code(prompt)
    if not gen_result["success"]:
        return {"success": False, "stage": "code_generation", **gen_result,
                "project_path": project_dir}

    # Step 4: write files (deterministic, path-validated)
    write_result = _write_files(project_dir, gen_result["files"])
    if not write_result["success"]:
        return {"success": False, "stage": "write_files", **write_result,
                "project_path": project_dir}

    # Step 5: verify — the only step allowed to produce success=True
    build_result = _verify_build(project_dir)

    return {
        "success": build_result["success"],
        "stage": "build_verification",
        "project_path": project_dir,
        "files_written": write_result["written"],
        "summary": gen_result.get("summary", ""),
        "build_output": build_result,
    }
