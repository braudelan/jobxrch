import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import json
import pytest
from unittest.mock import patch, MagicMock

from src.llm_utils.evaluate import (
    _strip_fences, _parse_response, _build_prompt, profile_hash, evaluate_job,
    EvaluationResult,
)


# --- _strip_fences ---

def test_strip_fences_plain_json():
    raw = '{"score": 7, "summary": "ok", "assessment": "good"}'
    assert _strip_fences(raw) == raw


def test_strip_fences_json_fences():
    raw = '```json\n{"score": 7, "summary": "ok", "assessment": "good"}\n```'
    result = _strip_fences(raw)
    assert result == '{"score": 7, "summary": "ok", "assessment": "good"}'


def test_strip_fences_plain_fences():
    raw = '```\n{"score": 5, "summary": "mid", "assessment": "fine"}\n```'
    result = _strip_fences(raw)
    assert result == '{"score": 5, "summary": "mid", "assessment": "fine"}'


# --- _parse_response ---

_VALID = '{"score": 8, "summary": "Good fit.", "assessment": "## Strong match\\nYou have the skills."}'


def test_parse_response_valid_json():
    result = _parse_response(_VALID)
    assert isinstance(result, EvaluationResult)
    assert result.score == 8
    assert result.summary == "Good fit."


def test_parse_response_json_fences():
    raw = f"```json\n{_VALID}\n```"
    result = _parse_response(raw)
    assert result.score == 8


def test_parse_response_plain_fences():
    raw = f"```\n{_VALID}\n```"
    result = _parse_response(raw)
    assert result.score == 8


def test_parse_response_invalid_json():
    result = _parse_response("not json at all")
    assert result.score == 0
    assert result.summary == "Parse failed."
    assert result.assessment == "not json at all"


def test_parse_response_missing_required_field():
    raw = '{"score": 7, "summary": "ok"}'  # missing assessment
    result = _parse_response(raw)
    assert result.score == 0
    assert result.summary == "Parse failed."


# --- _build_prompt ---

def test_build_prompt_contains_job_fields():
    job = {
        "job_title": "Staff Engineer",
        "company": "Acme",
        "location": "Remote",
        "description": "Build things at scale.",
    }
    prompt = _build_prompt(job, "I love distributed systems.")
    assert "Staff Engineer" in prompt
    assert "Acme" in prompt
    assert "Remote" in prompt
    assert "Build things at scale." in prompt
    assert "I love distributed systems." in prompt


def test_build_prompt_no_profile():
    job = {"job_title": "SWE", "company": "X", "location": "NY", "description": "Code."}
    prompt = _build_prompt(job, "")
    assert "No profile set" in prompt


# --- profile_hash ---

def test_profile_hash_deterministic():
    assert profile_hash("hello") == profile_hash("hello")


def test_profile_hash_different_inputs():
    assert profile_hash("hello") != profile_hash("world")


# --- evaluate_job (mocked) ---

_VALID_RESPONSE = '{"score": 9, "summary": "Excellent match.", "assessment": "You are perfect."}'

_SAMPLE_JOB = {
    "job_title": "Data Engineer",
    "company": "Acme",
    "location": "NYC",
    "description": "Build pipelines.",
}


def test_evaluate_job_returns_result_and_hash(tmp_path, monkeypatch):
    monkeypatch.setattr("src.db.database.DB_PATH", str(tmp_path / "test.db"))
    from src.db.database import init_db, save_profile
    init_db()
    save_profile("I am a data engineer with 5 years experience.")

    with patch("src.llm_utils.evaluate._load_provider") as mock_load:
        mock_provider = MagicMock(spec=["complete"])
        mock_provider.complete.return_value = _VALID_RESPONSE
        mock_load.return_value = mock_provider
        result, chash = evaluate_job(_SAMPLE_JOB)

    assert isinstance(result, EvaluationResult)
    assert result.score == 9
    assert result.summary == "Excellent match."
    assert isinstance(chash, str)
    assert len(chash) == 12
