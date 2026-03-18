# src/llm_utils/chat.py
import anthropic
import os


def chat_reply(messages: list[dict], db_context: str, profile: str = "") -> str:
    """Send conversation history + DB context to the LLM, return assistant reply."""
    profile_section = f"Here is what you know about the candidate:\n{profile.strip()}\n" if profile.strip() else ""
    system = f"""
You are a helpful career coach assistant for a job seeker. You have access to their current job list.
{profile_section}
Here is the current state of their job search (live snapshot):
{db_context}

In the job list above: score is an AI-assessed fit rating (1–10); a missing score (—) means the job hasn't been evaluated yet. Status is set manually by the user.

Help them think through their job search, discuss specific roles, and give honest career advice.
When they ask about specific jobs, reference the data above. Be direct, specific, and conversational."""

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=system,
        messages=messages,
    )
    return response.content[0].text
