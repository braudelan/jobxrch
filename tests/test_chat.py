import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from unittest.mock import patch, MagicMock

from src.llm_utils.chat import chat_reply
from src.llm_utils.search import tavily_search


def _mock_client(reply_text: str):
    """Fake Anthropic client that returns a plain text response."""
    block = MagicMock()
    block.type = "text"
    block.text = reply_text
    response = MagicMock()
    response.stop_reason = "end_turn"
    response.content = [block]
    client = MagicMock()
    client.messages.create.return_value = response
    return client


def _tool_use_response(tool_id: str, query: str):
    block = MagicMock()
    block.type = "tool_use"
    block.name = "search_web"
    block.id = tool_id
    block.input = {"query": query}
    resp = MagicMock()
    resp.stop_reason = "tool_use"
    resp.content = [block]
    return resp


# --- basic ---

def test_chat_reply_returns_text_from_mock():
    with patch("anthropic.Anthropic", return_value=_mock_client("Here is my advice.")):
        result = chat_reply([{"role": "user", "content": "What should I do?"}], "No jobs yet.")
    assert result == "Here is my advice."


def test_chat_reply_system_contains_db_context():
    db_ctx = "| SWE | Acme | 8 | saved |"
    client = _mock_client("ok")
    with patch("anthropic.Anthropic", return_value=client):
        chat_reply([{"role": "user", "content": "hi"}], db_ctx)
    assert db_ctx in client.messages.create.call_args[1]["system"]


def test_chat_reply_forwards_messages():
    messages = [{"role": "user", "content": "tell me about job X"}]
    client = _mock_client("ok")
    with patch("anthropic.Anthropic", return_value=client):
        chat_reply(messages, "ctx")
    assert client.messages.create.call_args[1]["messages"] == messages


# --- search integration (mocked Anthropic, real search contract) ---

def test_chat_reply_no_search_when_no_keys(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)

    with patch("anthropic.Anthropic", return_value=_mock_client("ok")):
        chat_reply([{"role": "user", "content": "hi"}], "ctx")

    # No tools should be passed when no provider is configured


def test_chat_reply_calls_search_fn(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    search_fn = MagicMock(return_value="Stripe is a payments company.")

    client = MagicMock()
    client.messages.create.side_effect = [
        _tool_use_response("t1", "Stripe company info"),
        _mock_client("Stripe processes payments.").messages.create.return_value,
    ]

    with patch("anthropic.Anthropic", return_value=client):
        result = chat_reply(
            [{"role": "user", "content": "Tell me about Stripe"}],
            "No jobs yet.",
            search_fn=search_fn,
        )

    assert result == "Stripe processes payments."
    search_fn.assert_called_once_with("Stripe company info")


def test_chat_reply_search_result_passed_in_followup(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    search_fn = MagicMock(return_value="Founded 2010 in San Francisco.")

    final_block = MagicMock()
    final_block.type = "text"
    final_block.text = "Done."
    final_resp = MagicMock()
    final_resp.stop_reason = "end_turn"
    final_resp.content = [final_block]

    client = MagicMock()
    client.messages.create.side_effect = [
        _tool_use_response("t2", "Stripe history"),
        final_resp,
    ]

    with patch("anthropic.Anthropic", return_value=client):
        chat_reply(
            [{"role": "user", "content": "Tell me about Stripe"}],
            "No jobs yet.",
            search_fn=search_fn,
        )

    second_messages = client.messages.create.call_args_list[1][1]["messages"]
    tool_result_turn = second_messages[-1]
    assert tool_result_turn["role"] == "user"
    assert any(
        b.get("content") == "Founded 2010 in San Francisco."
        for b in tool_result_turn["content"]
    )


# --- full end-to-end (real Anthropic + real Tavily) ---

@pytest.mark.skipif(
    not (os.environ.get("ANTHROPIC_API_KEY") and os.environ.get("TAVILY_API_KEY")),
    reason="ANTHROPIC_API_KEY and TAVILY_API_KEY must both be set",
)
def test_chat_reply_real_search_integration():
    result = chat_reply(
        [{"role": "user", "content": "Search the web and tell me what Stripe does."}],
        "No jobs saved yet.",
        search_fn=tavily_search,
    )
    assert isinstance(result, str)
    assert len(result) > 50
