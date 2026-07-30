"""
actions/claude_agent.py

Jarvis module: lets Jarvis call the Claude API (Anthropic) as a sub-agent
for deep reasoning, coding, debugging, code review, or analysis tasks —
same idea as actions/website_builder.py's use of Claude, generalized into
a reusable "ask_claude" tool instead of one fixed website-building pipeline.

DESIGN PRINCIPLE (per Jarvis architecture rules):
    - Claude is used ONLY for content/reasoning generation here — it has
      no direct execution power (no file writes, no shell commands). Jarvis's
      voice layer decides what to do with the returned text (speak a summary
      of it, save it via save_memory, or pass it into another action like
      file_processor).
    - For anything that needs deterministic file writes / build verification
      (like generating a full project), build a dedicated action instead of
      overloading this general-purpose reasoning tool.

Wire-up (already done in main.py):
    - from actions.claude_agent import TOOL_DECLARATIONS as claude_agent_tools
    - from actions.claude_agent import ask_claude_action
    - TOOL_DECLARATIONS.extend(claude_agent_tools)
    - dispatch: elif name == "ask_claude": ...

Requirements on the host machine:
    - ANTHROPIC_API_KEY set in the environment
    - `pip install anthropic --break-system-packages` in the jarvis venv
      (also required by actions/website_builder.py — now listed in
      requirements.txt so both modules are covered by one install)
"""

import os
import anthropic

MODEL = "claude-sonnet-4-6"
MAX_TOKENS_DEFAULT = 4096

# ---------------------------------------------------------------------------
# Tool declaration — Gemini Live schema (matches main.py's own inline
# TOOL_DECLARATIONS convention: "parameters" key, uppercase JSON-schema types)
# ---------------------------------------------------------------------------

TOOL_DECLARATIONS = [
    {
        "name": "ask_claude",
        "description": (
            "Sends a task to the Claude API (Anthropic) for deep reasoning, "
            "coding help, debugging, code review, writing, or detailed "
            "analysis that needs more depth than a quick spoken answer. Use "
            "this when the user asks Jarvis to 'ask Claude', wants code "
            "written or reviewed, wants an error debugged, or wants detailed "
            "research/analysis synthesized. Returns Claude's text response — "
            "Jarvis should summarize it naturally when speaking rather than "
            "reading it verbatim if it's long."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "task": {
                    "type": "STRING",
                    "description": (
                        "What to ask Claude to do, in full detail. E.g. "
                        "'Review this Python function for bugs', 'Write a "
                        "regex that matches emails', 'Explain the tradeoffs "
                        "between REST and GraphQL'."
                    ),
                },
                "context": {
                    "type": "STRING",
                    "description": (
                        "Optional extra context — file contents, error "
                        "messages, code snippets, prior conversation. Leave "
                        "empty if not needed."
                    ),
                },
                "max_tokens": {
                    "type": "INTEGER",
                    "description": (
                        "Max response length. Defaults to 4096. Use higher "
                        "(8000-16000) for long code generation tasks."
                    ),
                },
            },
            "required": ["task"],
        },
    }
]


# ---------------------------------------------------------------------------
# Public entry point — this is what the dispatch table calls
# ---------------------------------------------------------------------------

def ask_claude_action(parameters: dict, player=None) -> str:
    """
    Dispatch entry point. Jarvis's main.py calls this inside a thread
    executor (the Anthropic SDK call below is synchronous/blocking).
    """
    task = (parameters.get("task") or "").strip()
    context = (parameters.get("context") or "").strip()
    max_tokens = parameters.get("max_tokens") or MAX_TOKENS_DEFAULT

    if not task:
        msg = "Sir, Claude ko kya task dena hai woh clear nahi hai."
        _log(msg, player)
        return msg

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        msg = "Sir, ANTHROPIC_API_KEY environment variable set nahi hai."
        _log(msg, player)
        return msg

    prompt = task if not context else f"{task}\n\n---\nContext:\n{context}"

    client = anthropic.Anthropic(api_key=api_key)
    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=int(max_tokens),
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as e:
        msg = f"Sir, Claude API call fail ho gayi: {e}"
        _log(msg, player)
        return msg

    text = "".join(
        block.text for block in response.content if block.type == "text"
    ).strip()

    if not text:
        msg = "Sir, Claude ne khaali response diya."
        _log(msg, player)
        return msg

    _log(f"[Claude] {text[:200]}{'...' if len(text) > 200 else ''}", player)
    return text


def _log(message: str, player=None):
    if player:
        try:
            player.write_log(f"CLAUDE: {message}")
        except Exception as e:
            print(f"[ClaudeAgent] ⚠️ Could not write to UI log: {e}")
