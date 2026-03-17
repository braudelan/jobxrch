# src/evaluator/evaluator.py
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
    module = importlib.import_module(f"src.evaluator.providers.{provider_name}")
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


def _parse_response(raw: str) -> EvaluationResult:
    try:
        return EvaluationResult.model_validate(json.loads(raw))
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


def chat_reply(messages: list[dict], db_context: str) -> str:
    """Send conversation history + DB context to the LLM, return assistant reply."""
    import anthropic as _anthropic
    import os as _os

    system = f"""You are a helpful career coach assistant for a job seeker. You have access to their current job list.

Here is the current state of their job search (live snapshot):
{db_context}

Help them think through their job search, discuss specific roles, and give honest career advice.
When they ask about specific jobs, reference the data above. Be direct, specific, and conversational."""

    client = _anthropic.Anthropic(api_key=_os.environ["ANTHROPIC_API_KEY"])
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=system,
        messages=messages,
    )
    return response.content[0].text


def distill_profile(existing_profile: str, messages: list[dict]) -> str:
    """Distill preference signals from conversation into an updated profile."""
    import anthropic as _anthropic
    import os as _os

    conversation_text = "\n".join(
        f"{m['role'].upper()}: {m['content']}" for m in messages
    )

    prompt = f"""You are updating a candidate's career profile based on a recent conversation.

Current profile:
{existing_profile if existing_profile.strip() else "(empty)"}

Recent conversation:
{conversation_text}

Extract any new preferences, constraints, goals, or signals from the conversation and merge them into the profile.
- Preserve all existing content
- Add or refine based on what you learned from the conversation
- Be specific and concrete — avoid vague language
- Write in first person from the candidate's perspective
- Keep it concise (aim for 3-6 sentences or bullet points)

Return only the updated profile text, nothing else."""

    client = _anthropic.Anthropic(api_key=_os.environ["ANTHROPIC_API_KEY"])
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text.strip()
