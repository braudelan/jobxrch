import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import json
from unittest.mock import MagicMock, patch

from src.llm_utils.providers.ollama import _to_openai_tools, complete, chat


# --- helpers ---

def _text_response(text: str):
    msg = MagicMock()
    msg.content = text
    msg.tool_calls = None
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    return resp


def _tool_call_response(tool_id: str, tool_name: str, tool_args: dict):
    call = MagicMock()
    call.id = tool_id
    call.function.name = tool_name
    call.function.arguments = json.dumps(tool_args)
    msg = MagicMock()
    msg.content = None
    msg.tool_calls = [call]
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    return resp


def _mock_client(reply_text: str):
    client = MagicMock()
    client.chat.completions.create.return_value = _text_response(reply_text)
    return client


# --- _to_openai_tools ---

def test_to_openai_tools_converts_schema():
    tools = [{
        "name": "get_job_list",
        "description": "Get all jobs.",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    }]
    result = _to_openai_tools(tools)
    assert len(result) == 1
    assert result[0]["type"] == "function"
    fn = result[0]["function"]
    assert fn["name"] == "get_job_list"
    assert fn["description"] == "Get all jobs."
    assert fn["parameters"]["properties"]["query"]["type"] == "string"
    assert fn["parameters"]["required"] == ["query"]


def test_to_openai_tools_no_input_schema():
    result = _to_openai_tools([{"name": "ping", "description": "Ping."}])
    assert result[0]["function"]["parameters"] == {"type": "object", "properties": {}}


def test_to_openai_tools_empty():
    assert _to_openai_tools([]) == []


# --- complete ---

def test_complete_returns_text():
    with patch("src.llm_utils.providers.ollama._get_client", return_value=_mock_client("Hello!")):
        assert complete("Say hello.") == "Hello!"


def test_complete_sends_user_message():
    client = _mock_client("ok")
    with patch("src.llm_utils.providers.ollama._get_client", return_value=client):
        complete("my prompt")
    msgs = client.chat.completions.create.call_args[1]["messages"]
    assert msgs == [{"role": "user", "content": "my prompt"}]


def test_complete_tool_loop():
    search_fn = MagicMock(return_value="Stripe info.")
    client = MagicMock()
    client.chat.completions.create.side_effect = [
        _tool_call_response("t1", "search_web", {"query": "Stripe"}),
        _text_response("Stripe is a payments company."),
    ]
    tool = {
        "name": "search_web",
        "description": "Search.",
        "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}},
    }
    with patch("src.llm_utils.providers.ollama._get_client", return_value=client):
        result = complete(
            "Tell me about Stripe.",
            tools=[tool],
            tool_handlers={"search_web": lambda inp: search_fn(inp["query"])},
        )
    assert result == "Stripe is a payments company."
    search_fn.assert_called_once_with("Stripe")


# --- chat ---

def test_chat_returns_text():
    with patch("src.llm_utils.providers.ollama._get_client", return_value=_mock_client("Great advice!")):
        assert chat("You are helpful.", [{"role": "user", "content": "Help me."}]) == "Great advice!"


def test_chat_prepends_system_message():
    client = _mock_client("ok")
    with patch("src.llm_utils.providers.ollama._get_client", return_value=client):
        chat("Be concise.", [{"role": "user", "content": "hi"}])
    msgs = client.chat.completions.create.call_args[1]["messages"]
    assert msgs[0] == {"role": "system", "content": "Be concise."}
    assert msgs[1] == {"role": "user", "content": "hi"}


def test_chat_tool_result_forwarded():
    search_fn = MagicMock(return_value="Result data.")
    client = MagicMock()
    client.chat.completions.create.side_effect = [
        _tool_call_response("t2", "search_web", {"query": "OpenAI"}),
        _text_response("Done."),
    ]
    tool = {
        "name": "search_web",
        "description": "Search.",
        "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}},
    }
    with patch("src.llm_utils.providers.ollama._get_client", return_value=client):
        chat(
            "You are helpful.",
            [{"role": "user", "content": "search OpenAI"}],
            tools=[tool],
            tool_handlers={"search_web": lambda inp: search_fn(inp["query"])},
        )
    second_call_msgs = client.chat.completions.create.call_args_list[1][1]["messages"]
    tool_result = second_call_msgs[-1]
    assert tool_result["role"] == "tool"
    assert tool_result["tool_call_id"] == "t2"
    assert tool_result["content"] == "Result data."


def test_chat_unknown_tool_returns_error_string():
    """LLM calls a tool not in tool_handlers — should pass 'Unknown tool' back."""
    dummy_tool = {
        "name": "known_tool",
        "description": "A tool.",
        "input_schema": {"type": "object", "properties": {}},
    }
    client = MagicMock()
    client.chat.completions.create.side_effect = [
        _tool_call_response("t3", "nonexistent_tool", {}),
        _text_response("ok"),
    ]
    with patch("src.llm_utils.providers.ollama._get_client", return_value=client):
        chat("sys", [{"role": "user", "content": "hi"}], tools=[dummy_tool], tool_handlers={})
    second_msgs = client.chat.completions.create.call_args_list[1][1]["messages"]
    tool_result = second_msgs[-1]
    assert "Unknown tool" in tool_result["content"]
