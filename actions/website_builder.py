# actions/website_builder.py
# Wires JARVIS to Lovable's official "Build with URL" API
# Docs: https://docs.lovable.dev/integrations/build-with-url

from urllib.parse import quote

from actions.browser_control import browser_control

LOVABLE_BASE_URL = "https://lovable.dev/?autosubmit=true#"
MAX_PROMPT_CHARS = 50000        # Lovable's own documented limit
MAX_REFERENCE_IMAGES = 10        # Lovable's own documented limit


def _build_lovable_url(prompt: str, image_urls: list[str] | None = None) -> str:
    """Builds a Lovable 'Build with URL' link from a plain-text prompt
    (and optional public reference image URLs)."""
    prompt = prompt.strip()[:MAX_PROMPT_CHARS]
    url = f"{LOVABLE_BASE_URL}prompt={quote(prompt)}"

    if image_urls:
        for img in image_urls[:MAX_REFERENCE_IMAGES]:
            url += f"&images={quote(img, safe='')}"

    return url


def build_website(parameters: dict, player=None) -> str:
    """Entry point JARVIS calls to trigger a Lovable website/app build."""
    description = (parameters or {}).get("description", "").strip()
    image_urls  = (parameters or {}).get("reference_images", []) or []

    if not description:
        return "Website kaisi chahiye woh batao, sir — bina description ke Lovable kuch nahi bana sakta."

    lovable_url = _build_lovable_url(description, image_urls)

    if player:
        player.write_log(f"[website_builder] Opening Lovable build link ({len(description)} chars)")

    try:
        result = browser_control(
            parameters={"action": "go_to", "url": lovable_url},
            player=player,
        )
        return (
            result
            or "Lovable browser tab khol diya hai — agar login nahi ho to sign in kar lo, "
               "generation apne aap shuru ho jayega."
        )
    except Exception as e:
        return f"Lovable link kholte waqt error aaya, sir: {e}"


# ------------------------------------------------------------------
# JARVIS INTEGRATION -- main.py ke TOOL_DECLARATIONS me wire karo
# ------------------------------------------------------------------
TOOL_DECLARATIONS = [
    {
        "name": "build_website",
        "description": (
            "Builds a website or web app using Lovable's AI website builder. "
            "Use whenever the user asks to create, build, generate, or design "
            "a website, landing page, or web app. Opens Lovable in the browser "
            "and passes the user's description as the build prompt."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "description": {
                    "type": "STRING",
                    "description": (
                        "Full natural-language description of the website/app to build "
                        "(pages, style, features, colors, etc). Be as detailed as the user gave."
                    ),
                },
                "reference_images": {
                    "type": "ARRAY",
                    "items": {"type": "STRING"},
                    "description": "Optional public image URLs (JPEG/PNG/WebP) to use as design reference.",
                },
            },
            "required": ["description"],
        },
    }
]
