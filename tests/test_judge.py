from unittest.mock import patch, MagicMock
from eval.judge import judge


def _mock_provider(raw_response: str):
    provider = MagicMock()
    provider.complete.return_value = raw_response
    return provider


def test_judge_calls_complete_with_temperature_zero():
    provider = _mock_provider('{"score": 0.8, "rationale": "Supported."}')
    with patch("eval.judge._load_provider", return_value=provider):
        judge("reference text", "claim text", "Does the claim follow?")
    _, kwargs = provider.complete.call_args
    assert kwargs.get("temperature") == 0


def test_judge_returns_score_and_rationale():
    provider = _mock_provider('{"score": 0.75, "rationale": "Mostly supported."}')
    with patch("eval.judge._load_provider", return_value=provider):
        result = judge("reference", "claim", "question")
    assert result.score == 0.75
    assert result.rationale == "Mostly supported."


def test_judge_clamps_score_above_one():
    provider = _mock_provider('{"score": 1.5, "rationale": "Over the top."}')
    with patch("eval.judge._load_provider", return_value=provider):
        result = judge("ref", "claim", "q")
    assert result.score == 1.0


def test_judge_returns_zero_on_parse_failure():
    provider = _mock_provider("not json at all")
    with patch("eval.judge._load_provider", return_value=provider):
        result = judge("ref", "claim", "q")
    assert result.score == 0.0
    assert "parse failed" in result.rationale.lower()
