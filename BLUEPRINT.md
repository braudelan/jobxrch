# jobXrch — A job search helper: Design Blueprint

## What is it?

A local job evaluation and tracking dashboard — a personal tool that scrapes job postings, scores them via LLM, and helps track and prioritize applications.

---

## Core Principles

- **Robustness over features** — build a solid backbone first, elaborate later
- **Source agnosticism** — the pipeline should not care where a job came from
- **Separation of concerns** — ingest (*basic_data* and *link*), fetch (*job_description*), evaluate, and store are independent stages
- **Extensibility** — every component should be replaceable or augmentable without breaking others

---

## Pipeline

```
[Source] → [Ingest] → [Fetch] → [Evaluate] → [Store]
```

- **Possible future extension**: LLM actions performed on a batch of stored records.

### Stages

| Stage | Responsibility | Status |
|---|---|---|
| **Ingest** | Receive raw job data (title, company, location, link) from any source | Partial (LinkedIn scraper only) |
| **Fetch** | Given a link, retrieve the full job description | Done (LinkedIn only) |
| **Evaluate** | Run job + criteria through LLM, return structured JSON (score, summary, assessment) | Done |
| **Store** | Persist job data and evaluation output to DB | Done |

### Pipeline Modes (future)

- `fetch-evaluate` — full pipeline, default mode
- `fetch` — ingest + fetch only, no evaluation
- `evaluate` — evaluate already-fetched jobs, no fetch
- Batch/cross-record LLM operations — actions performed across multiple stored records rather than per-job (e.g. `batch-prioritize`, `batch-summarize`).

---

## Entry Points

Two entry points via `main.py` (click CLI):

| Command | Description |
|---|---|
| `python main.py pipeline` | Runs the LinkedIn batch pipeline — crawl → fetch → evaluate → save |
| `python main.py dashboard` | Starts the web dashboard on localhost:8000 |

---

## Input Sources

### Current
- **LinkedIn saved jobs scraper** — `src/pipelines/linkedin.py` crawls saved jobs list, fetches JDs via Playwright, evaluates, and saves to DB
- **Web dashboard** — paste any job URL into the dashboard to trigger fetch → evaluate → save

### Planned
- **Additional scrapers** — for other job boards and sources
- **Chrome extension** — one-click evaluation from any job posting page (convenience layer on top of the dashboard ingest)

> All ingest sources are adapters — regardless of origin, they must produce a normalized job object conforming to the design contract below before entering the pipeline.

### Design Contract

All sources must produce a normalized job object before entering the pipeline:

```json
{
  "job_title": "string",
  "company":   "string",
  "location":  "string",
  "link":      "string | N/A",
  "description": "string | null"
}
```

If `description` is null and `link` is provided, the Fetch stage runs. If both are present, Fetch is skipped.

---

## Evaluation

### Input
- Normalized job object (with full JD)
- `criteria.txt` — plain text file describing ideal role, skills, priorities, and dealbreakers (user-maintained)

### Output
Structured JSON parsed into a Pydantic `EvaluationResult` model:
- **score** — numeric 1–10 fit score
- **summary** — 2 sentence max, for list views
- **assessment** — full reasoning

Parse failures fall back gracefully: score 0, raw response preserved.

> Note: score reliability requires prompt engineering iteration — treat scores as directional until the prompt is validated.

### Re-evaluation
- Supported manually via dashboard button (planned)
- Each evaluation is versioned by `criteria_hash` — old evaluations are never overwritten

### Batch Prioritization
- LLM ranks a set of jobs comparatively, not in isolation
- Results cached with a timestamp; invalidated when scores or criteria change
- Planned feature — not yet built

### LLM
- Provider-agnostic — swap via `LLM_PROVIDER` env var
- Currently: Anthropic Claude (`claude-sonnet-4-6`)
- Model and prompt configurable per provider

---

## Database Schema

### `jobs` table
| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER PK | |
| `job_title` | TEXT | |
| `company` | TEXT | |
| `location` | TEXT | |
| `link` | TEXT UNIQUE | Natural dedup key |
| `description` | TEXT | Full JD |
| `source` | TEXT | e.g. `linkedin`, `manual`, `extension` |
| `status` | TEXT | `saved` → `applied` → `in-process` → `offer` / `rejected` |
| `deleted` | INTEGER | Soft delete flag (0/1), default 0 |
| `scraped_at` | TEXT | ISO 8601 UTC |

### `evaluations` table
| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER PK | |
| `job_id` | INTEGER FK | References `jobs.id` |
| `criteria_hash` | TEXT | SHA-256 (12 chars) of `criteria.txt` at evaluation time |
| `score` | INTEGER | 1–10, 0 on parse failure |
| `summary` | TEXT | 2-sentence max |
| `assessment` | TEXT | Full LLM reasoning |
| `evaluated_at` | TEXT | ISO 8601 UTC |

---

## Dashboard

**Stack:** FastAPI + Jinja2 + vanilla JS + Pico.css. No build step, localhost only.

### Routes

| Status | Route | Purpose |
|---|---|---|
| WIP | `GET /` | Job list sorted by score, colour-coded |
| WIP | `POST /jobs/evaluate` | Submit URL → fetch → evaluate → persist → redirect |
| Planned | `GET /jobs/<id>` | Full assessment + metadata detail view |
| Planned | `POST /jobs/prioritize` | Cached LLM batch ranking |
| Planned | `POST /jobs/<id>/status` | Inline status change |
| Planned | `POST /jobs/<id>/delete` + `/restore` | Soft delete management |

### Job Lifecycle
Status flows linearly: `saved → applied → in-process → offer | rejected`
- No arbitrary jumping forward
- One step back allowed (misclick protection)
- Deleted jobs hidden by default, recoverable via toggle

### UI Principles
- Click-to-expand rows for summary → full assessment (planned)
- Minimal, functional — no JS framework, no Tailwind

---

## Project Structure

```
jobxrch/
├── main.py                  # CLI entry point (click) — pipeline + dashboard commands
├── criteria.txt             # User-maintained evaluation criteria
├── data/
│   └── jobs.db              # SQLite database
├── src/
│   ├── scraper/             # LinkedIn crawler + card parser
│   ├── fetcher/             # JD fetcher (Playwright)
│   ├── db/                  # DB init, read, write
│   ├── evaluator/           # LLM evaluation logic + provider abstraction
│   ├── pipelines/           # One module per ingest source (linkedin.py, ...)
│   └── dashboard/           # FastAPI app + Jinja2 templates
└── tests/
```

---

## Future Directions

- Detail view for full assessment per job
- Inline status updates and soft delete from dashboard
- Browser extension as a convenience ingest layer
- Batch prioritization (cross-job LLM ranking)
- Job offer age indication in dashboard
- Criteria versioning and diff
- Free form AI chat interface: 
  1. Allows natural language querying of DB.
  2. Feedback loop for improving AI knowledge and understanding of user goals and preferences. 

