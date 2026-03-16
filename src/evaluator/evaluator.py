# src/evaluator/evaluator.py
import os
import json
import hashlib
import importlib
from dotenv import load_dotenv
from pydantic import BaseModel, ValidationError

load_dotenv(override=True)

CRITERIA_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "criteria.txt")


class EvaluationResult(BaseModel):
    score: int
    summary: str
    assessment: str


def _load_provider():
    provider_name = os.environ.get("LLM_PROVIDER", "anthropic")
    module = importlib.import_module(f"src.evaluator.providers.{provider_name}")
    return module.complete


def _load_criteria() -> str:
    if not os.path.exists(CRITERIA_PATH):
        raise FileNotFoundError(f"Criteria file not found at {CRITERIA_PATH}. Please create it.")
    with open(CRITERIA_PATH) as f:
        return f.read().strip()


def _build_prompt(job: dict, criteria: str) -> str:
    return f"""You are evaluating a job posting on behalf of a candidate.

Here are the candidate's criteria:
{criteria}

Here is the job posting:
Job Title: {job['job_title']}
Company: {job['company']}
Location: {job['location']}
Description:
{job['description']}

Evaluate how well this job matches the candidate's criteria.

Respond with a JSON object only — no markdown, no explanation outside the JSON. Use this exact structure:
{{
  "score": <integer 1-10>,
  "summary": "<2 sentences max summarising the fit>",
  "assessment": "<full reasoning of match and mismatch against each criterion>"
}}"""


def _parse_response(raw: str) -> EvaluationResult:
    try:
        return EvaluationResult.model_validate(json.loads(raw))
    except (json.JSONDecodeError, ValidationError):
        return EvaluationResult(score=0, summary="Parse failed.", assessment=raw)


def criteria_hash(criteria: str) -> str:
    return hashlib.sha256(criteria.encode()).hexdigest()[:12]


def evaluate_job(job: dict) -> tuple[EvaluationResult, str]:
    """Returns (EvaluationResult, criteria_hash)."""
    criteria = _load_criteria()
    prompt = _build_prompt(job, criteria)
    complete = _load_provider()
    raw = complete(prompt)
    return _parse_response(raw), criteria_hash(criteria)
