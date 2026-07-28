from core.config import get_gemini_key

DEFAULT_MODEL = "gemini-2.5-flash"


def get_generative_model(model_name: str = DEFAULT_MODEL, **kwargs):
    """`google.generativeai` model configured with the stored Gemini key."""
    import google.generativeai as genai

    genai.configure(api_key=get_gemini_key())
    return genai.GenerativeModel(model_name=model_name, **kwargs)


def get_genai_client(api_version: str | None = None):
    """`google.genai` client configured with the stored Gemini key."""
    from google import genai

    if api_version:
        return genai.Client(
            api_key=get_gemini_key(),
            http_options={"api_version": api_version},
        )
    return genai.Client(api_key=get_gemini_key())
