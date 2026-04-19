# src/cv_tailor.py
import os
import json
import time
import uuid
import importlib
from pathlib import Path
from typing import Optional
from pydantic import BaseModel
from jinja2 import Template


# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class Bullet(BaseModel):
    title: str
    text: str
    source_sections: list[str]


class ExperienceEntry(BaseModel):
    company: str
    title: Optional[str]
    period: str
    tagline: str
    bullets: list[Bullet]
    source_sections: list[str]


class SkillCategory(BaseModel):
    category: str
    items: str
    source_sections: list[str]


class Summary(BaseModel):
    text: str
    source_sections: list[str]


class CVTailorResult(BaseModel):
    header: dict
    summary: Summary
    skills: list[SkillCategory]
    experience: list[ExperienceEntry]
    education: list[dict]


# ============================================================================
# UTILITIES
# ============================================================================

def _load_provider():
    provider_name = os.environ.get("LLM_PROVIDER", "anthropic")
    return importlib.import_module(f"src.llm_utils.providers.{provider_name}")


def _complete(prompt: str, tools: list = None, tool_handlers: dict = None) -> str:
    provider = _load_provider()
    if tools:
        return provider.complete(prompt, tools, tool_handlers)
    return provider.complete(prompt)


def _load_cv_template() -> dict:
    """Load the static CV template from data/cv_template.json."""
    template_path = Path(__file__).parent.parent / "data" / "cv_template.json"
    with open(template_path) as f:
        return json.load(f)


def _build_prompt(
    job_description: str, master_profile: str, template: dict, preferences: str = ""
) -> str:
    """
    Build the prompt for CV tailoring generation.

    Args:
        job_description: The job description to tailor for
        master_profile: The candidate's consolidated master profile
        template: The static CV template with <generated> markers
        preferences: Learned user preferences to inject into the prompt (empty by default)

    Returns:
        Formatted prompt ready for LLM completion
    """
    preferences_section = (
        f"\nLearned Preferences:\n{preferences}\n" if preferences.strip() else ""
    )

    prompt = f"""You are an expert resume writer tailoring a candidate's CV for a specific job.

You have:
1. The candidate's comprehensive master profile (with clear section headers)
2. A job description they're applying for
3. A CV template with static (fixed) and generated (variable) fields
{preferences_section}
Your task: Fill ALL <generated> fields in the template with content optimized for the job.

CRITICAL RULES:
- Keep ALL fixed fields exactly as provided (company names, titles, periods, all education)
- Generate variable numbers of skill categories and bullets per role — the template shows examples, but you should generate as many as appropriate for the job
- For EVERY generated field, cite specific named section headers from the master profile in source_sections
- Never invent facts not present in the master profile
- Ensure bullets are specific, quantified, and directly relevant to the job
- Return ONLY valid JSON conforming to the template structure — no markdown, no prose

Master Profile:
{master_profile}

Job Description:
{job_description}

CV Template (fill in <generated> fields):
{json.dumps(template, indent=2)}

Return only the completed CV JSON object (valid JSON, no backticks, no markdown):"""
    return prompt


# ============================================================================
# PUBLIC API
# ============================================================================

def generate_cv_tailor(
    job_description: str, job_id: Optional[int] = None
) -> CVTailorResult:
    """
    Generate a tailored CV for a specific job description.

    Takes the current master profile from the database and fills the static CV template
    with LLM-generated content optimized for the job. All generated fields are annotated
    with source_sections referencing the master profile.

    Saves the rendered CV to cv_versions (linked to job_id if provided) and logs the
    full call to raw_llm_log.
    """
    from src.db.database import log_llm_call, get_profile, get_job, save_cv_version

    run_id = str(uuid.uuid4())
    start_time = time.time()

    # Fetch master profile from DB
    master_profile = get_profile()
    if not master_profile.strip():
        raise ValueError("Master profile is empty. Set a profile before generating CV tailors.")

    # Load template
    template = _load_cv_template()

    # Build and execute prompt
    prompt = _build_prompt(job_description, master_profile, template)
    raw_output = _complete(prompt)
    latency_ms = int((time.time() - start_time) * 1000)

    # Parse and validate
    try:
        parsed = json.loads(raw_output)
        result = CVTailorResult.model_validate(parsed)
    except Exception as e:
        raise ValueError(f"Failed to parse CV tailor output: {e}\nRaw output:\n{raw_output}")

    # Save rendered CV to cv_versions
    rendered = render_cv(result)
    label = "Tailored CV"
    if job_id:
        job = get_job(job_id)
        if job:
            label = f"{job['company']} — {job['job_title']}"
    save_cv_version(label, rendered, job_id=job_id)

    # Log the call
    log_llm_call(
        run_id=run_id,
        task_type="cv_tailor",
        input_payload=json.dumps(
            {
                "job_description": job_description,
                "master_profile": master_profile,
            }
        ),
        output_payload=json.dumps(result.model_dump()),
        prompt_content=prompt,
        model=os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6"),
        latency_ms=latency_ms,
    )

    return result


def render_cv(result: CVTailorResult) -> str:
    """
    Render a CVTailorResult into a markdown CV document.

    Structure:
    - Header: name, title, contact
    - Summary
    - Skills: grouped by category
    - Experience: by company, with bullets
    - Education: static entries

    Note: source_sections fields are used by llmEV only and are not rendered.
    """
    lines = []

    # Header
    header = result.header
    lines.append(f"# {header['name']}")
    lines.append(f"{header['title']}")
    lines.append("")
    lines.append(f"📧 {header['email']} | 📱 {header['phone']} | 🔗 {header['linkedin']}")
    lines.append("")

    # Summary
    if result.summary and result.summary.text.strip():
        lines.append("## Summary")
        lines.append(result.summary.text)
        lines.append("")

    # Skills
    if result.skills:
        lines.append("## Skills")
        for skill in result.skills:
            lines.append(f"**{skill.category}:** {skill.items}")
        lines.append("")

    # Experience
    if result.experience:
        lines.append("## Experience")
        for exp in result.experience:
            # Company header
            company_line = f"### {exp.company}"
            if exp.title:
                company_line += f" — {exp.title}"
            lines.append(company_line)
            lines.append(f"*{exp.period}*")
            lines.append("")

            # Tagline
            if exp.tagline.strip():
                lines.append(f"{exp.tagline}")
                lines.append("")

            # Bullets
            for bullet in exp.bullets:
                bullet_line = f"- **{bullet.title}** — {bullet.text}"
                lines.append(bullet_line)
            lines.append("")

    # Education
    if result.education:
        lines.append("## Education")
        for edu in result.education:
            degree = edu.get("degree", "")
            institution = edu.get("institution", "")
            year = edu.get("year", "")
            note = edu.get("note", "")

            edu_line = f"- **{degree}** — {institution} ({year})"
            if note:
                edu_line += f" — {note}"
            lines.append(edu_line)
        lines.append("")

    return "\n".join(lines).strip()
