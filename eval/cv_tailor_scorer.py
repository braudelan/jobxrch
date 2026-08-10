# eval/cv_tailor_scorer.py
"""Scorer for cv_tailor first-shot generations.

Implements the rubric in cv_tailor_quality_contract.md: profile section
extraction, the Tier 1/2/3 checks, and assembly of the Section 8 output
record per evaluation unit (one Bullet, Summary, or SkillCategory).

Reads its inputs from a single raw_llm_log row (task_type='cv_tailor');
does not itself query the database — that's the log-reader/pipeline layer
(next-steps item 4), still pending the job_id-in-raw_llm_log prerequisite
(item 3). This module is the part of the architecture that's cv_tailor-
specific; eval/judge.py is the reusable scoring primitive it calls into.
"""
import json
from typing import Optional

from eval.judge import judge

_GROUNDING_QUESTION = "Does the claim follow from the reference?"
_RELEVANCE_QUESTION = "Does the claim directly address a requirement stated in the reference?"


def extract_profile_sections(profile_text: str) -> dict[str, str]:
    """Split a master profile on '## ' headers into {section_name: section_text}."""
    sections: dict[str, str] = {}
    current_name: Optional[str] = None
    current_lines: list[str] = []
    for line in profile_text.splitlines():
        if line.startswith("## "):
            if current_name is not None:
                sections[current_name] = "\n".join(current_lines).strip()
            current_name = line[3:].strip()
            current_lines = []
        elif current_name is not None:
            current_lines.append(line)
    if current_name is not None:
        sections[current_name] = "\n".join(current_lines).strip()
    return sections


def _tier1_check(source_sections: list[str], profile_sections: dict[str, str]) -> tuple[Optional[str], list[str]]:
    """Returns (label, missing_sections). label is None if both checks pass."""
    if not source_sections:
        return "uncited", []
    missing = [s for s in source_sections if s not in profile_sections]
    if missing:
        return "invalid_citation", missing
    return None, []


def _build_reference(source_sections: list[str], profile_sections: dict[str, str]) -> str:
    """Concatenate cited section texts in citation order, per the contract's premise-length decision."""
    return "\n\n".join(profile_sections[s] for s in source_sections)


def _bucket(score: float, labels: tuple[str, str, str]) -> str:
    high, mid, low = labels
    if score >= 0.7:
        return high
    if score >= 0.4:
        return mid
    return low


def score_grounding(reference: str, claim: str) -> tuple[float, str]:
    """Tier 2: does the bullet follow from its cited profile sections?"""
    result = judge(reference, claim, _GROUNDING_QUESTION)
    return result.score, _bucket(result.score, ("supported", "unverified", "hallucinated"))


def score_relevance(claim: str, job_description: str) -> tuple[float, str]:
    """Tier 3: does the bullet serve the job description?"""
    result = judge(job_description, claim, _RELEVANCE_QUESTION)
    return result.score, _bucket(result.score, ("highly_relevant", "partially_relevant", "irrelevant"))


def _iter_units(output_payload: dict):
    """Yield (context, title, text, source_sections) for each scoreable unit in a CVTailorResult payload."""
    summary = output_payload.get("summary") or {}
    if summary.get("text", "").strip():
        yield "summary", "Summary", summary["text"], summary.get("source_sections", [])

    for skill in output_payload.get("skills", []):
        yield f"skills:{skill['category']}", skill["category"], skill["items"], skill.get("source_sections", [])

    for exp in output_payload.get("experience", []):
        for bullet in exp.get("bullets", []):
            yield f"experience:{exp['company']}", bullet["title"], bullet["text"], bullet.get("source_sections", [])


def score_log_entry(log_entry: dict, *, max_tier: int = 3) -> list[dict]:
    """Score every evaluation unit in one raw_llm_log row (task_type='cv_tailor').

    `max_tier` caps how far scoring proceeds: 1 = deterministic checks only,
    2 = + grounding, 3 = + relevance. Lets callers validate tier by tier —
    Tier 1 against historical log data at zero judge-call cost, then Tier 2
    once trusted, then Tier 3 — rather than spending judge calls on tiers
    not yet validated.

    `log_entry` is a dict from raw_llm_log (e.g. dict(sqlite3.Row)). `job_id`
    is read defensively via .get() since the column doesn't exist until the
    item-3 prerequisite migration lands.
    """
    input_payload = json.loads(log_entry["input_payload"])
    output_payload = json.loads(log_entry["output_payload"])
    profile_sections = extract_profile_sections(input_payload["master_profile"])
    job_description = input_payload.get("job_description", "")

    records = []
    for context, title, text, source_sections in _iter_units(output_payload):
        record = {
            "run_id": log_entry["run_id"],
            "log_id": log_entry["id"],
            "job_id": log_entry.get("job_id"),
            "timestamp": log_entry["timestamp"],
            "model": log_entry["model"],
            "context": context,
            "bullet_title": title,
            "bullet_text": text,
            "source_sections": source_sections,
            "missing_sections": [],
            "reference": None,
            "grounding_score": None,
            "grounding_label": "uncited",
            "relevance_score": None,
            "relevance_label": None,
        }

        tier1_label, missing = _tier1_check(source_sections, profile_sections)
        if tier1_label:
            record["grounding_label"] = tier1_label
            record["missing_sections"] = missing
            records.append(record)
            continue

        reference = _build_reference(source_sections, profile_sections)
        record["reference"] = reference

        if max_tier >= 2:
            record["grounding_score"], record["grounding_label"] = score_grounding(reference, text)

        if max_tier >= 3:
            record["relevance_score"], record["relevance_label"] = score_relevance(text, job_description)

        records.append(record)

    return records
