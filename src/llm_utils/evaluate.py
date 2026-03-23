# src/llm_utils/evaluate.py
import os
import json
import hashlib
import importlib
from dotenv import load_dotenv
from pydantic import BaseModel, ValidationError

load_dotenv(override=True)


class EvaluationResult(BaseModel):
    score: int
    summary: str
    assessment: str


def _load_provider():
    provider_name = os.environ.get("LLM_PROVIDER", "anthropic")
    module = importlib.import_module(f"src.llm_utils.providers.{provider_name}")
    return module.complete


def _build_prompt(job: dict, profile: str) -> str:
    profile_section = profile.strip() if profile.strip() else "(No profile set — evaluate on general merit.)"
    return f"""You are a career coach evaluating a job on behalf of a candidate you know well.

Here is everything you know about the candidate:
{profile_section}

Here is the job posting:
Job Title: {job['job_title']}
Company: {job['company']}
Location: {job['location']}
Description:
{job['description']}

Evaluate this job as a trusted advisor — honest about fit and gaps, direct but not harsh.
Address the candidate as "you".

Respond with JSON only — no markdown wrapper, no text outside the JSON:
{{
  "score": <integer 1-10>,
  "summary": "<1-2 sentences max — concise fit verdict for quick scanning>",
  "assessment": "<full coaching evaluation — use markdown: prose paragraphs, bold headers, bullet points where appropriate>"
}}"""


def _strip_fences(raw: str) -> str:
    s = raw.strip()
    if s.startswith("```"):
        s = s.split("\n", 1)[1] if "\n" in s else s[3:]
    if s.endswith("```"):
        s = s.rsplit("```", 1)[0]
    return s.strip()


def _parse_response(raw: str) -> EvaluationResult:
    try:
        return EvaluationResult.model_validate(json.loads(_strip_fences(raw)))
    except (json.JSONDecodeError, ValidationError):
        return EvaluationResult(score=0, summary="Parse failed.", assessment=raw)


def profile_hash(profile: str) -> str:
    return hashlib.sha256(profile.encode()).hexdigest()[:12]


def evaluate_job(job: dict) -> tuple[EvaluationResult, str]:
    """Returns (EvaluationResult, profile_hash)."""
    from src.db.database import get_profile
    profile = get_profile()
    if not profile.strip():
        import warnings
        warnings.warn("User profile is empty — evaluation will be generic.")
    prompt = _build_prompt(job, profile)
    complete = _load_provider()
    raw = complete(prompt)
    return _parse_response(raw), profile_hash(profile)
