import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from unittest.mock import patch, MagicMock

from src.llm_utils.chat import chat_reply


def _mock_anthropic(reply_text: str):
    """Return a mock anthropic.Anthropic client that always replies with reply_text."""
    content_block = MagicMock()
    content_block.text = reply_text

    response = MagicMock()
    response.content = [content_block]

    client = MagicMock()
    client.messages.create.return_value = response
    return client


# --- chat_reply ---

def test_chat_reply_returns_text_from_mock():
    client = _mock_anthropic("Here is my advice.")
    with patch("anthropic.Anthropic", return_value=client):
        result = chat_reply([{"role": "user", "content": "What should I do?"}], "No jobs yet.")
    assert result == "Here is my advice."


def test_chat_reply_system_contains_db_context():
    client = _mock_anthropic("ok")
    db_ctx = "| SWE | Acme | 8 | saved |"
    with patch("anthropic.Anthropic", return_value=client):
        chat_reply([{"role": "user", "content": "hi"}], db_ctx)

    call_kwargs = client.messages.create.call_args[1]
    assert db_ctx in call_kwargs["system"]


def test_chat_reply_forwards_messages():
    client = _mock_anthropic("ok")
    messages = [{"role": "user", "content": "tell me about job X"}]
    with patch("anthropic.Anthropic", return_value=client):
        chat_reply(messages, "ctx")

    call_kwargs = client.messages.create.call_args[1]
    assert call_kwargs["messages"] == messages
