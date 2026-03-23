# src/llm_utils/chat.py
import anthropic
import os
from typing import Callable, Optional

from src.llm_utils.search import get_search_fn


_SEARCH_TOOL = {
    "name": "search_web",
    "description": (
        "Search the web for up-to-date information about companies, roles, industries, "
        "or anything else that would help give better career advice. "
        "Use this whenever the user asks about a specific company you're unfamiliar with."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query to run.",
            }
        },
        "required": ["query"],
    },
}


def chat_reply(
    messages: list[dict],
    db_context: str,
    profile: str = "",
    search_fn: Optional[Callable[[str], str]] = None,
) -> str:
    """Send conversation history + DB context to the LLM, return assistant reply.

    search_fn: optional callable (query: str) -> str. Defaults to whichever
    provider is configured via environment variables. Pass None explicitly to
    disable search entirely.
    """
    if search_fn is None:
        search_fn = get_search_fn()

    tools = [_SEARCH_TOOL] if search_fn else []

    profile_section = f"Here is what you know about the candidate:\n{profile.strip()}\n" if profile.strip() else ""
    search_instruction = "If you need more context about a company or role, use the search_web tool." if search_fn else ""
    system = f"""
You are a helpful career coach assistant for a job seeker. You have access to their current job list.
{profile_section}
Here is the current state of their job search (live snapshot):
{db_context}

In the job list above: score is an AI-assessed fit rating (1–10); a missing score (—) means the job hasn't been evaluated yet. Status is set manually by the user.

Help them think through their job search, discuss specific roles, and give honest career advice.
When they ask about specific jobs, reference the data above. Be direct, specific, and conversational.
{search_instruction}"""

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"]) 
    working_messages = list(messages)

    while True:
        kwargs = {"tools": tools} if tools else {}
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=system,
            messages=working_messages,
            **kwargs,
        )

        if response.stop_reason != "tool_use":
            for block in response.content:
                if hasattr(block, "text"):
                    return block.text
            return ""

        tool_results = []
        for block in response.content:
            if block.type != "tool_use" or block.name != "search_web":
                continue
            query = block.input.get("query", "")
            result = search_fn(query)
            tool_results.append(
                {"type": "tool_result", "tool_use_id": block.id, "content": result}
            )

        working_messages = working_messages + [
            {"role": "assistant", "content": response.content},
            {"role": "user", "content": tool_results},
        ]
