# src/llm_utils/chat.py
import anthropic
import os


def chat_reply(messages: list[dict], db_context: str) -> str:
    """Send conversation history + DB context to the LLM, return assistant reply."""
    system = f"""You are a helpful career coach assistant for a job seeker. You have access to their current job list.

Here is the current state of their job search (live snapshot):
{db_context}

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
