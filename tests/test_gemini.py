from unittest.mock import MagicMock, patch
from google.genai import types
from src.llm_utils.providers.gemini import _to_google_tools, _to_google_contents, complete, chat


# --- helpers ---
def _text_response(text: str):
    part = types.Part(text=text)
    content = MagicMock()
    content.parts = [part]
    candidate = MagicMock()
    candidate.content = content
    resp = MagicMock()
    resp.candidates = [candidate]
    resp.text = text
    return resp


def _tool_call_response(name: str, args: dict):
    part = types.Part(function_call=types.FunctionCall(name=name, args=args))
    content = MagicMock()
    content.parts = [part]
    candidate = MagicMock()
    candidate.content = content
    resp = MagicMock()
    resp.candidates = [candidate]
    return resp


def _mock_client(reply_text: str):
    client = MagicMock()
    client.models.generate_content.return_value = _text_response(reply_text)
    return client


# --- _to_google_tools ---
def test_to_google_tools_converts_schema():
    tools = [{
        "name": "get_job_list",
        "description": "Get all jobs.",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "A query."}},
            "required": ["query"],
        },
    }]
    result = _to_google_tools(tools)
    assert len(result) == 1
    decl = result[0].function_declarations[0]
    assert decl.name == "get_job_list"
    assert decl.description == "Get all jobs."
    assert decl.parameters.properties["query"].type == types.Type.STRING
    assert decl.parameters.required == ["query"]


def test_to_google_tools_no_properties():
    result = _to_google_tools([{"name": "ping", "description": "Ping."}])
    decl = result[0].function_declarations[0]
    assert decl.parameters is None


# --- _to_google_contents ---
def test_to_google_contents_maps_roles():
    messages = [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello"},
    ]
    result = _to_google_contents(messages)
    assert [c.role for c in result] == ["user", "model"]
    assert result[0].parts[0].text == "hi"
    assert result[1].parts[0].text == "hello"


# --- complete ---
def test_complete_returns_text():
    with patch("src.llm_utils.providers.gemini._get_client", return_value=_mock_client("Hello!")):
        assert complete("Say hello.") == "Hello!"


def test_complete_tool_loop():
    search_fn = MagicMock(return_value="Stripe info.")
    client = MagicMock()
    client.models.generate_content.side_effect = [
        _tool_call_response("search_web", {"query": "Stripe"}),
        _text_response("Stripe is a payments company."),
    ]
    tool = {
        "name": "search_web",
        "description": "Search.",
        "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}},
    }
    with patch("src.llm_utils.providers.gemini._get_client", return_value=client):
        result = complete(
            "Tell me about Stripe.",
            tools=[tool],
            tool_handlers={"search_web": lambda inp: search_fn(inp["query"])},
        )
    assert result == "Stripe is a payments company."
    search_fn.assert_called_once_with("Stripe")


# --- chat ---
def test_chat_returns_text():
    with patch("src.llm_utils.providers.gemini._get_client", return_value=_mock_client("Great advice!")):
        assert chat("You are helpful.", [{"role": "user", "content": "Help me."}]) == "Great advice!"


def test_chat_sets_system_instruction():
    client = _mock_client("ok")
    with patch("src.llm_utils.providers.gemini._get_client", return_value=client):
        chat("Be concise.", [{"role": "user", "content": "hi"}])
    config = client.models.generate_content.call_args[1]["config"]
    assert config.system_instruction == "Be concise."


def test_chat_tool_result_forwarded():
    search_fn = MagicMock(return_value="Result data.")
    client = MagicMock()
    client.models.generate_content.side_effect = [
        _tool_call_response("search_web", {"query": "OpenAI"}),
        _text_response("Done."),
    ]
    tool = {
        "name": "search_web",
        "description": "Search.",
        "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}},
    }
    with patch("src.llm_utils.providers.gemini._get_client", return_value=client):
        result = chat(
            "You are helpful.",
            [{"role": "user", "content": "search OpenAI"}],
            tools=[tool],
            tool_handlers={"search_web": lambda inp: search_fn(inp["query"])},
        )
    assert result == "Done."
    second_call_contents = client.models.generate_content.call_args_list[1][1]["contents"]
    tool_response_part = second_call_contents[-1].parts[0]
    assert tool_response_part.function_response.name == "search_web"
    assert tool_response_part.function_response.response == {"result": "Result data."}


def test_chat_unknown_tool_returns_error_string():
    """LLM calls a tool not in tool_handlers — should pass 'Unknown tool' back."""
    dummy_tool = {
        "name": "known_tool",
        "description": "A tool.",
        "input_schema": {"type": "object", "properties": {}},
    }
    client = MagicMock()
    client.models.generate_content.side_effect = [
        _tool_call_response("nonexistent_tool", {}),
        _text_response("ok"),
    ]
    with patch("src.llm_utils.providers.gemini._get_client", return_value=client):
        chat("sys", [{"role": "user", "content": "hi"}], tools=[dummy_tool], tool_handlers={})
    second_call_contents = client.models.generate_content.call_args_list[1][1]["contents"]
    tool_response_part = second_call_contents[-1].parts[0]
    assert tool_response_part.function_response.response == {"result": "Unknown tool: nonexistent_tool"}


def test_chat_tool_loop_exceeds_max_iterations():
    tool = {
        "name": "search_web",
        "description": "Search.",
        "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}},
    }
    client = MagicMock()
    client.models.generate_content.side_effect = lambda **_kwargs: _tool_call_response("search_web", {"query": "x"})
    with patch("src.llm_utils.providers.gemini._get_client", return_value=client):
        result = chat(
            "sys",
            [{"role": "user", "content": "hi"}],
            tools=[tool],
            tool_handlers={"search_web": lambda _inp: "result"},
        )
    assert result == "[Error: tool loop exceeded max iterations]"
