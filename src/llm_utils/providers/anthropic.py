# src/llm_utils/providers/anthropic.py
import os
import anthropic


ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")
_client = None

def _get_client():
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    return _client


def complete(prompt: str, tools: list = None, tool_handlers: dict = None) -> str:
    """Single-turn completion with optional tool use."""
    if tools:
        return _tool_loop([{"role": "user", "content": prompt}], tools, tool_handlers)
    message = _get_client().messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


def chat(system: str, messages: list, tools: list = None, tool_handlers: dict = None) -> str:
    """Multi-turn chat with optional tool use."""
    if tools:
        return _tool_loop(messages, tools, tool_handlers, system=system)
    message = _get_client().messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=2048,
        system=system,
        messages=messages,
    )
    return message.content[0].text


def _tool_loop(messages: list, tools: list, tool_handlers: dict, system: str = None) -> str:
    """Agentic tool-use loop. Returns the final text reply."""
    kwargs = {"system": system} if system else {}

    while True:
        response = _get_client().messages.create(
            model=ANTHROPIC_MODEL,
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
            if block.type != "tool_use" or block.name not in tool_handlers:
                continue
            result = tool_handlers[block.name](block.input)
            tool_results.append(
                {"type": "tool_result", "tool_use_id": block.id, "content": result}
            )

        messages = messages + [
            {"role": "assistant", "content": response.content},
            {"role": "user", "content": tool_results},
        ]


