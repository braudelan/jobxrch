from unittest.mock import MagicMock, patch
from src.llm_utils.providers.anthropic import complete, chat


# --- helpers ---
def _text_message(text: str):
    block = MagicMock()
    block.type = "text"
    block.text = text
    msg = MagicMock()
    msg.content = [block]
    msg.stop_reason = "end_turn"
    return msg


def _tool_use_message(tool_id: str, name: str, input_: dict):
    block = MagicMock()
    block.type = "tool_use"
    block.id = tool_id
    block.name = name
    block.input = input_
    msg = MagicMock()
    msg.content = [block]
    msg.stop_reason = "tool_use"
    return msg


def _mock_client(reply_text: str):
    client = MagicMock()
    client.messages.create.return_value = _text_message(reply_text)
    return client


# --- complete ---
def test_complete_returns_text():
    with patch("src.llm_utils.providers.anthropic._get_client", return_value=_mock_client("Hello!")):
        assert complete("Say hello.") == "Hello!"


def test_complete_sends_user_message():
    client = _mock_client("ok")
    with patch("src.llm_utils.providers.anthropic._get_client", return_value=client):
        complete("my prompt")
    msgs = client.messages.create.call_args[1]["messages"]
    assert msgs == [{"role": "user", "content": "my prompt"}]


def test_complete_tool_loop():
    search_fn = MagicMock(return_value="Stripe info.")
    client = MagicMock()
    client.messages.create.side_effect = [
        _tool_use_message("t1", "search_web", {"query": "Stripe"}),
        _text_message("Stripe is a payments company."),
    ]
    tool = {
        "name": "search_web",
        "description": "Search.",
        "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}},
    }
    with patch("src.llm_utils.providers.anthropic._get_client", return_value=client):
        result = complete(
            "Tell me about Stripe.",
            tools=[tool],
            tool_handlers={"search_web": lambda inp: search_fn(inp["query"])},
        )
    assert result == "Stripe is a payments company."
    search_fn.assert_called_once_with("Stripe")


# --- chat ---
def test_chat_returns_text():
    with patch("src.llm_utils.providers.anthropic._get_client", return_value=_mock_client("Great advice!")):
        assert chat("You are helpful.", [{"role": "user", "content": "Help me."}]) == "Great advice!"


def test_chat_passes_system_prompt():
    client = _mock_client("ok")
    with patch("src.llm_utils.providers.anthropic._get_client", return_value=client):
        chat("Be concise.", [{"role": "user", "content": "hi"}])
    kwargs = client.messages.create.call_args[1]
    assert kwargs["system"] == "Be concise."
    assert kwargs["messages"] == [{"role": "user", "content": "hi"}]


def test_chat_tool_result_forwarded():
    search_fn = MagicMock(return_value="Result data.")
    client = MagicMock()
    client.messages.create.side_effect = [
        _tool_use_message("t2", "search_web", {"query": "OpenAI"}),
        _text_message("Done."),
    ]
    tool = {
        "name": "search_web",
        "description": "Search.",
        "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}},
    }
    with patch("src.llm_utils.providers.anthropic._get_client", return_value=client):
        result = chat(
            "You are helpful.",
            [{"role": "user", "content": "search OpenAI"}],
            tools=[tool],
            tool_handlers={"search_web": lambda inp: search_fn(inp["query"])},
        )
    assert result == "Done."
    second_call_msgs = client.messages.create.call_args_list[1][1]["messages"]
    tool_result_msg = second_call_msgs[-1]
    assert tool_result_msg["role"] == "user"
    assert tool_result_msg["content"] == [
        {"type": "tool_result", "tool_use_id": "t2", "content": "Result data."}
    ]


def test_chat_unknown_tool_skipped():
    """LLM calls a tool not in tool_handlers — result is skipped, loop continues."""
    dummy_tool = {
        "name": "known_tool",
        "description": "A tool.",
        "input_schema": {"type": "object", "properties": {}},
    }
    client = MagicMock()
    client.messages.create.side_effect = [
        _tool_use_message("t3", "nonexistent_tool", {}),
        _text_message("ok"),
    ]
    with patch("src.llm_utils.providers.anthropic._get_client", return_value=client):
        result = chat("sys", [{"role": "user", "content": "hi"}], tools=[dummy_tool], tool_handlers={})
    assert result == "ok"
    second_call_msgs = client.messages.create.call_args_list[1][1]["messages"]
    tool_result_msg = second_call_msgs[-1]
    assert tool_result_msg["content"] == []


def test_chat_tool_loop_exceeds_max_iterations():
    tool = {
        "name": "search_web",
        "description": "Search.",
        "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}},
    }
    client = MagicMock()
    client.messages.create.side_effect = lambda **_kwargs: _tool_use_message("t", "search_web", {"query": "x"})
    with patch("src.llm_utils.providers.anthropic._get_client", return_value=client):
        result = chat(
            "sys",
            [{"role": "user", "content": "hi"}],
            tools=[tool],
            tool_handlers={"search_web": lambda _inp: "result"},
        )
    assert result == "[Error: tool loop exceeded max iterations]"
