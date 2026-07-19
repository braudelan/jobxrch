# src/llm_utils/providers/gemini.py
import os
from google import genai
from google.genai import types

_DEFAULT_MODEL = "gemini-2.0-flash"
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", _DEFAULT_MODEL)

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    return _client


def _get_model() -> str:
    try:
        from src.db.database import get_config
        return get_config("gemini_model") or GEMINI_MODEL
    except Exception:
        return GEMINI_MODEL


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
    tool_id_to_name: dict[str, str] = {}

    for msg in messages:
        role = "model" if msg["role"] == "assistant" else "user"
        content = msg["content"]

        if isinstance(content, str):
            result.append(types.Content(role=role, parts=[types.Part(text=content)]))
            continue

        if not isinstance(content, list):
            continue

        parts = []
        for block in content:
            btype = block.get("type")
            if btype == "text" and block.get("text"):
                parts.append(types.Part(text=block["text"]))
            elif btype == "tool_use":
                tool_id_to_name[block["id"]] = block["name"]
                parts.append(types.Part(
                    function_call=types.FunctionCall(
                        name=block["name"],
                        args=block.get("input", {}),
                    )
                ))
            elif btype == "tool_result":
                tool_use_id = block.get("tool_use_id", "")
                name = tool_id_to_name.get(tool_use_id, tool_use_id)
                tool_content = block.get("content", "")
                if isinstance(tool_content, list):
                    tool_content = " ".join(
                        b["text"] for b in tool_content
                        if isinstance(b, dict) and b.get("type") == "text" and b.get("text")
                    )
                parts.append(types.Part(
                    function_response=types.FunctionResponse(
                        name=name,
                        response={"result": tool_content},
                    )
                ))

        if parts:
            result.append(types.Content(role=role, parts=parts))

    return result


def complete(prompt: str, tools: list = None, tool_handlers: dict = None) -> str:
    """Single-turn completion with optional tool use."""
    if tools:
        contents = [types.Content(role="user", parts=[types.Part(text=prompt)])]
        config = types.GenerateContentConfig(tools=_to_google_tools(tools))
        return _tool_loop(contents, config, tool_handlers)

    response = _get_client().models.generate_content(
        model=_get_model(),
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
            model=_get_model(),
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
            model=_get_model(),
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
