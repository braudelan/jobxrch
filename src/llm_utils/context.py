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


def format_cv_list(versions: list[dict]) -> str:
    if not versions:
        return "No CV versions saved yet."
    lines = [
        "| ID | Label | Created | Job ID |",
        "| --- | --- | --- | --- |",
    ]
    for v in versions:
        job_id = str(v["job_id"]) if v.get("job_id") else "—"
        lines.append(f"| {v['id']} | {v['label']} | {v['created_at'][:10]} | {job_id} |")
    return "\n".join(lines)


def format_cv(version: dict) -> str:
    header = f"**CV: {version['label']}** (id: {version['id']}, created: {version['created_at'][:10]})"
    return f"{header}\n\n{version['content']}"
