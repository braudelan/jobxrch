import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from unittest.mock import patch, MagicMock

from src.llm_utils.chat import chat_reply



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


def _tool_use_response(tool_id: str, tool_name: str, tool_input: dict):
    block = MagicMock()
    block.type = "tool_use"
    block.name = tool_name
    block.id = tool_id
    block.input = tool_input
    resp = MagicMock()
    resp.stop_reason = "tool_use"
    resp.content = [block]
    return resp


_NO_JOBS = []
_FAKE_JOBS = [{"id": 1, "job_title": "SWE", "company": "Acme", "score": 8, "status": "saved"}]


# --- basic ---

def test_chat_reply_returns_text_from_mock():
    with patch("src.llm_utils.providers.anthropic._get_client", return_value=_mock_client("Here is my advice.")):
        with patch("src.llm_utils.chat.get_all_jobs", return_value=_NO_JOBS):
            with patch("src.llm_utils.chat.get_profile", return_value=""):
                result = chat_reply([{"role": "user", "content": "What should I do?"}])
    assert result == "Here is my advice."


def test_chat_reply_forwards_messages():
    messages = [{"role": "user", "content": "tell me about job X"}]
    client = _mock_client("ok")
    with patch("src.llm_utils.providers.anthropic._get_client", return_value=client):
        with patch("src.llm_utils.chat.get_all_jobs", return_value=_NO_JOBS):
            with patch("src.llm_utils.chat.get_profile", return_value=""):
                chat_reply(messages)
    assert client.messages.create.call_args[1]["messages"] == messages


def test_chat_reply_registers_job_list_tool():
    """get_job_list tool should always be registered."""
    client = _mock_client("ok")
    with patch("src.llm_utils.providers.anthropic._get_client", return_value=client):
        with patch("src.llm_utils.chat.get_all_jobs", return_value=_FAKE_JOBS):
            with patch("src.llm_utils.chat.get_profile", return_value=""):
                chat_reply([{"role": "user", "content": "hi"}])
    tools_passed = client.messages.create.call_args[1]["tools"]
    tool_names = [t["name"] for t in tools_passed]
    assert "get_job_list" in tool_names
    assert "get_job_details" in tool_names


# --- search integration (mocked Anthropic, real search contract) ---

def test_chat_reply_no_search_when_no_keys(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)

    with patch("src.llm_utils.providers.anthropic._get_client", return_value=_mock_client("ok")):
        with patch("src.llm_utils.chat.get_all_jobs", return_value=_NO_JOBS):
            with patch("src.llm_utils.chat.get_profile", return_value=""):
                chat_reply([{"role": "user", "content": "hi"}])


def test_chat_reply_calls_search_fn(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    search_fn = MagicMock(return_value="Stripe is a payments company.")

    client = MagicMock()
    client.messages.create.side_effect = [
        _tool_use_response("t1", "search_web", {"query": "Stripe company info"}),
        _mock_client("Stripe processes payments.").messages.create.return_value,
    ]

    with patch("src.llm_utils.providers.anthropic._get_client", return_value=client):
        with patch("src.llm_utils.chat.get_all_jobs", return_value=_NO_JOBS):
            with patch("src.llm_utils.chat.get_profile", return_value=""):
                with patch("src.llm_utils.chat.get_search_fn", return_value=search_fn):
                    result = chat_reply([{"role": "user", "content": "Tell me about Stripe"}])

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
        _tool_use_response("t2", "search_web", {"query": "Stripe history"}),
        final_resp,
    ]

    with patch("src.llm_utils.providers.anthropic._get_client", return_value=client):
        with patch("src.llm_utils.chat.get_all_jobs", return_value=_NO_JOBS):
            with patch("src.llm_utils.chat.get_profile", return_value=""):
                with patch("src.llm_utils.chat.get_search_fn", return_value=search_fn):
                    chat_reply([{"role": "user", "content": "Tell me about Stripe"}])

    second_messages = client.messages.create.call_args_list[1][1]["messages"]
    tool_result_turn = second_messages[-1]
    assert tool_result_turn["role"] == "user"
    assert any(
        b.get("content") == "Founded 2010 in San Francisco."
        for b in tool_result_turn["content"]
    )


# --- full end-to-end (real Anthropic + real Tavily) ---

# @pytest.mark.skipif(
#     not (os.environ.get("ANTHROPIC_API_KEY") and os.environ.get("TAVILY_API_KEY")),
#     reason="ANTHROPIC_API_KEY and TAVILY_API_KEY must both be set",
# )
# def test_chat_reply_real_search_integration():
#     result = chat_reply(
#         [{"role": "user", "content": "Search the web and tell me what Stripe does."}],
#     )
#     assert isinstance(result, str)
#     assert len(result) > 50
