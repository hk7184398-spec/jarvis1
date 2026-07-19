"""
Generates a draft proposal for a given job lead using the Anthropic API.
Requires ANTHROPIC_API_KEY environment variable to be set.
"""
import os
import anthropic

YOUR_PROFILE = """
I'm a Python developer specializing in automation, algorithmic trading systems
(MetaTrader 5 Expert Advisors in MQL5), and AI assistant development. I build
reliable, tested tools and communicate clearly on scope, timelines, and pricing.
"""  # Edit this to describe your own skills/experience


def generate_proposal(job_title, job_summary):
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return "[ERROR] Set ANTHROPIC_API_KEY environment variable to enable AI proposal drafting."

    client = anthropic.Anthropic(api_key=api_key)

    prompt = f"""Write a short, personalized freelance proposal (120-160 words) for this job posting.

Job title: {job_title}
Job description: {job_summary}

My background:
{YOUR_PROFILE}

Keep it direct, no generic filler, mention one specific relevant skill, and end with a
clear call to action (e.g., asking a clarifying question about scope)."""

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=400,
        messages=[{"role": "user", "content": prompt}]
    )
    return message.content[0].text
