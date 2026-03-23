# src/llm_utils/providers/anthropic.py
import os
import anthropic

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    return _client


def complete(prompt: str) -> str:
    message = _get_client().messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


def chat(system: str, messages: list) -> str:
    message = _get_client().messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=system,
        messages=messages,
    )
    return message.content[0].text


def _tool_loop(messages: list, tools: list, search_fn, system: str = None) -> str:
    """Shared agentic tool-use loop. Returns the final text reply."""
    kwargs = {"system": system} if system else {}

    while True:
        response = _get_client().messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            tools=tools,
            messages=messages,
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
            result = search_fn(block.input.get("query", ""))
            tool_results.append(
                {"type": "tool_result", "tool_use_id": block.id, "content": result}
            )

        messages = messages + [
            {"role": "assistant", "content": response.content},
            {"role": "user", "content": tool_results},
        ]


def complete_with_tools(prompt: str, tools: list, search_fn) -> str:
    return _tool_loop([{"role": "user", "content": prompt}], tools, search_fn)


def chat_with_tools(system: str, messages: list, tools: list, search_fn) -> str:
    return _tool_loop(messages, tools, search_fn, system=system)
