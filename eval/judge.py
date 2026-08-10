# eval/judge.py
"""Generic LLM-as-judge scoring primitive.

The swappable scoring engine described in cv_tailor_quality_contract.md
section 5/12: given a reference text and a claim, returns a score in
[0.0, 1.0] plus a short rationale answering a specific question about their
relationship. Implementation is LLM-as-judge; a local NLI model is a
documented fallback (not implemented here) — callers only depend on the
judge() signature, not on how the score is computed.

Naming is deliberately neutral rather than NLI's premise/hypothesis: this
primitive serves both an entailment-style question (Tier 2 grounding) and a
relevance-style question (Tier 3) that isn't actually entailment, and the
shared function shouldn't imply otherwise.

Knows nothing about CVs, bullets, or profiles — reusable by any feature's
scorer, not just cv_tailor's.
"""
import os
import importlib
import json_repair
from pydantic import BaseModel, ValidationError


class JudgeResult(BaseModel):
    score: float
    rationale: str


def _load_provider():
    provider_name = os.environ.get("LLM_PROVIDER", "anthropic")
    return importlib.import_module(f"src.llm_utils.providers.{provider_name}")


_JUDGE_PROMPT = """You are a strict, literal-minded evaluator. Answer only the question asked — do not reward style, confidence, or plausibility.

Question: {question}

Reference:
{reference}

Claim:
{claim}

Respond with JSON only — no markdown, no text outside the JSON:
{{
  "score": <float between 0.0 and 1.0>,
  "rationale": "<one sentence justifying the score>"
}}"""


def judge(reference: str, claim: str, question: str) -> JudgeResult:
    """Ask an LLM judge `question` about how `claim` relates to `reference`.

    Returns a score in [0.0, 1.0] with a short rationale. The same primitive
    serves both Tier 2 grounding (reference = cited profile sections) and
    Tier 3 relevance (reference = job description) — bucketing the score
    into tier-specific labels is the caller's job, not this function's.
    """
    provider = _load_provider()
    prompt = _JUDGE_PROMPT.format(question=question, reference=reference, claim=claim)
    raw = provider.complete(prompt)
    try:
        result = JudgeResult.model_validate(json_repair.loads(raw.strip()))
        result.score = max(0.0, min(1.0, result.score))
        return result
    except (ValidationError, Exception):
        return JudgeResult(score=0.0, rationale=f"Judge response parse failed: {raw[:200]}")
