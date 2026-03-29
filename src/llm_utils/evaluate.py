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


_SEARCH_TOOL = {
    "name": "search_web",
    "description": (
        "Search the web for information about a company — its industry, size, culture, "
        "products, or recent news — to inform a more accurate job evaluation."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "The search query to run."}
        },
        "required": ["query"],
    },
}


def _load_provider():
    provider_name = os.environ.get("LLM_PROVIDER", "anthropic")
    return importlib.import_module(f"src.llm_utils.providers.{provider_name}")


def _complete(prompt: str, search_fn=None) -> str:
    provider = _load_provider()
    if search_fn:
        return provider.complete(prompt, [_SEARCH_TOOL], {"search_web": lambda inp: search_fn(inp["query"])})
    return provider.complete(prompt)


def _build_prompt(job: dict, profile: str, with_search: bool = False) -> str:
    profile_section = profile.strip() if profile.strip() else "(No profile set — evaluate on general merit.)"
    web_search_instruction = (
        "\nIf you are unfamiliar with the company or need more context about it, "
        "use the search_web tool before evaluating.\n"
        if with_search else ""
    )
    return f"""You are a career coach evaluating a job on behalf of a candidate you know well.
{web_search_instruction}
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
    from src.llm_utils.search import get_search_fn

    profile = get_profile()
    if not profile.strip():
        import warnings
        warnings.warn("User profile is empty — evaluation will be generic.")

    search_fn = get_search_fn()
    prompt = _build_prompt(job, profile, with_search=bool(search_fn))
    raw = _complete(prompt, search_fn)
    return _parse_response(raw), profile_hash(profile)
