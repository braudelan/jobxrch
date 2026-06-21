# src/llm_utils/providers/gemini.py
import os
from google import genai
from google.genai import types

GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    return _client


_JSON_TYPE_MAP = {
    "string": "string",
    "integer": "integer",
    "number": "number",
    "boolean": "boolean",
    "object": "object",
    "array": "array",
}


def _to_google_tools(tools: list[dict]) -> list[types.Tool]:
    """Convert Anthropic-style tool definitions to a Google Tool object."""
    declarations = []
    for tool in tools:
        schema = tool.get("input_schema", {})
        properties = {
            name: types.Schema(
                type=_JSON_TYPE_MAP.get(prop.get("type", "string"), "string"),
                description=prop.get("description", ""),
            )
            for name, prop in schema.get("properties", {}).items()
        }
        declarations.append(types.FunctionDeclaration(
            name=tool["name"],
            description=tool.get("description", ""),
            parameters=types.Schema(
                type="object",
                properties=properties,
                required=schema.get("required", []),
            ) if properties else None,
        ))
    return [types.Tool(function_declarations=declarations)]


def _to_google_contents(messages: list[dict]) -> list[types.Content]:
    """Convert Anthropic-style message dicts to Google Content objects."""
    result = []
    for msg in messages:
        role = "model" if msg["role"] == "assistant" else "user"
        content = msg["content"]
        if isinstance(content, str):
            result.append(types.Content(role=role, parts=[types.Part(text=content)]))
    return result


def complete(prompt: str, tools: list = None, tool_handlers: dict = None) -> str:
    """Single-turn completion with optional tool use."""
    if tools:
        contents = [types.Content(role="user", parts=[types.Part(text=prompt)])]
        config = types.GenerateContentConfig(tools=_to_google_tools(tools))
        return _tool_loop(contents, config, tool_handlers)

    response = _get_client().models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
    )
    return response.text


def chat(system: str, messages: list[dict], tools: list = None, tool_handlers: dict = None) -> str:
    """Multi-turn chat with optional tool use."""
    contents = _to_google_contents(messages)
    config = types.GenerateContentConfig(
        system_instruction=system,
        tools=_to_google_tools(tools) if tools else None,
    )

    if not tools:
        response = _get_client().models.generate_content(
            model=GEMINI_MODEL,
            contents=contents,
            config=config,
        )
        return response.text

    return _tool_loop(contents, config, tool_handlers)


_MAX_TOOL_ITERATIONS = 10


def _tool_loop(contents: list, config: types.GenerateContentConfig, tool_handlers: dict) -> str:
    """Agentic tool-use loop. Returns the final text reply."""
    for _ in range(_MAX_TOOL_ITERATIONS):
        response = _get_client().models.generate_content(
            model=GEMINI_MODEL,
            contents=contents,
            config=config,
        )

        parts = response.candidates[0].content.parts
        fn_call_parts = [p for p in parts if p.function_call]

        if not fn_call_parts:
            for part in parts:
                if part.text:
                    return part.text
            return ""

        contents.append(types.Content(role="model", parts=parts))

        tool_response_parts = []
        for part in fn_call_parts:
            name = part.function_call.name
            args = dict(part.function_call.args)
            result = tool_handlers[name](args) if name in tool_handlers else f"Unknown tool: {name}"
            tool_response_parts.append(types.Part(
                function_response=types.FunctionResponse(name=name, response={"result": result})
            ))

        contents.append(types.Content(role="user", parts=tool_response_parts))

    return "[Error: tool loop exceeded max iterations]"
