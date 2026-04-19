# src/llm_utils/providers/ollama.py
"""
Local LLM provider via Ollama's OpenAI-compatible API.

Setup:
  1. Install Ollama: https://ollama.com
  2. Pull a model with tool-calling support, e.g.:
       ollama pull qwen2.5:7b
  3. Set in .env:
       LLM_PROVIDER=ollama
       OLLAMA_MODEL=qwen2.5:7b      # optional, defaults to qwen2.5:7b
       OLLAMA_BASE_URL=http://localhost:11434/v1  # optional
"""
import json
import os
from openai import OpenAI

_client = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(
            base_url=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
            api_key="ollama",  # required by the OpenAI SDK but ignored by Ollama
        )
    return _client


def _model() -> str:
    return os.environ.get("OLLAMA_MODEL", "qwen2.5:7b")


def _to_openai_tools(
    tools: list,
) -> list:
    """Convert Anthropic-style tool schemas to OpenAI format."""
    result = []
    for t in tools:
        result.append({
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t.get("description", ""),
                "parameters": t.get("input_schema", {"type": "object", "properties": {}}),
            },
        })
    return result


def complete(
    prompt: str,
    tools: list = None,
    tool_handlers: dict = None,
) -> str:
    """Single-turn completion with optional tool use."""
    messages = [{"role": "user", "content": prompt}]
    if tools:
        return _tool_loop(messages, tools, tool_handlers)
    response = _get_client().chat.completions.create(
        model=_model(),
        messages=messages,
    )
    return response.choices[0].message.content


def chat(
    system: str,
    messages: list,
    tools: list = None,
    tool_handlers: dict = None,
) -> str:
    """Multi-turn chat with optional tool use."""
    full_messages = [{"role": "system", "content": system}] + messages
    if tools:
        return _tool_loop(full_messages, tools, tool_handlers)
    response = _get_client().chat.completions.create(
        model=_model(),
        messages=full_messages,
    )
    return response.choices[0].message.content


_MAX_TOOL_ITERATIONS = 10


def _tool_loop(
    messages: list,
    tools: list,
    tool_handlers: dict,
) -> str:
    """Agentic tool-use loop using OpenAI-compatible API."""
    oai_tools = _to_openai_tools(tools)

    for _ in range(_MAX_TOOL_ITERATIONS):
        response = _get_client().chat.completions.create(
            model=_model(),
            messages=messages,
            tools=oai_tools,
        )
        msg = response.choices[0].message

        if not msg.tool_calls:
            return msg.content or ""

        messages = messages + [msg]

        for call in msg.tool_calls:
            fn_name = call.function.name
            fn_args = json.loads(call.function.arguments)
            result = tool_handlers[fn_name](fn_args) if fn_name in tool_handlers else f"Unknown tool: {fn_name}"
            messages = messages + [{
                "role": "tool",
                "tool_call_id": call.id,
                "content": str(result),
            }]

    return "[Error: tool loop exceeded max iterations]"
