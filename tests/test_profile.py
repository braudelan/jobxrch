import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from unittest.mock import patch, MagicMock

from src.llm_utils.profile import distill_profile


def _mock_anthropic(reply_text: str):
    """Return a mock anthropic.Anthropic client that always replies with reply_text."""
    content_block = MagicMock()
    content_block.text = reply_text

    response = MagicMock()
    response.content = [content_block]

    client = MagicMock()
    client.messages.create.return_value = response
    return client


# --- distill_profile ---

def test_distill_profile_prompt_contains_conversation():
    client = _mock_anthropic("Updated profile text.")
    messages = [
        {"role": "user", "content": "I want remote only."},
        {"role": "assistant", "content": "Got it."},
    ]
    with patch("anthropic.Anthropic", return_value=client):
        result = distill_profile("Old profile.", messages)

    assert result == "Updated profile text."
    call_kwargs = client.messages.create.call_args[1]
    prompt = call_kwargs["messages"][0]["content"]
    assert "I want remote only." in prompt
    assert "Old profile." in prompt


def test_distill_profile_empty_existing():
    client = _mock_anthropic("New profile.")
    with patch("anthropic.Anthropic", return_value=client):
        result = distill_profile("", [{"role": "user", "content": "I prefer startups."}])

    call_kwargs = client.messages.create.call_args[1]
    prompt = call_kwargs["messages"][0]["content"]
    assert "(empty)" in prompt
    assert result == "New profile."
