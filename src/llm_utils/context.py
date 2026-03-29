# src/llm_utils/context.py


def format_job_list(jobs: list[dict]) -> str:
    if not jobs:
        return "No jobs saved yet."
    lines = [
        "| ID | Title | Company | Score | Status |",
        "| --- | --- | --- | --- | --- |",
    ]
    for j in jobs:
        score = str(j["score"]) if j.get("score") else "—"
        lines.append(
            f"| {j['id']} | {j['job_title']} | {j['company']} | {score} | {j['status']} |"
        )
    return "\n".join(lines)


def format_job(job: dict) -> str:
    parts = [
        f"**{job['job_title']} @ {job['company']}** (score: {job.get('score') or 'N/A'}, status: {job['status']})"
    ]
    if job.get("description"):
        parts.append(f"\n### Description\n{job['description']}")
    if job.get("assessment"):
        parts.append(f"\n### AI Assessment\n{job['assessment']}")
    return "\n".join(parts)
