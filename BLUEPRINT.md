# Job Evaluator — Blueprint

## What is it?

A local job evaluation dashboard — a personal tool that scrapes job postings, scores them via LLM, and helps track and prioritize applications.

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
| **Evaluate** | Run job + criteria through LLM, return structured JSON (score, summary, assessment) | In progress |
| **Store** | Persist job data and evaluation output to DB | Done |

### Pipeline Modes (future)

- `fetch-evaluate` — full pipeline, default mode
- `fetch` — ingest + fetch only, no evaluation
- `evaluate` — evaluate already-fetched jobs, no fetch
- Batch/cross-record LLM operations — actions performed across multiple stored records rather than per-job (e.g. `batch-prioritize`, `batch-summarize`).

---

## Input Sources

### Current
- **LinkedIn saved jobs scraper** — crawls saved jobs list, extracts basic card data, fetches JDs via Playwright

### Planned
- **Web dashboard** — paste a URL directly into the dashboard to trigger the full fetch-evaluate pipeline
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
- Criteria file — a plain text document describing your ideal role, skills, priorities, and dealbreakers (user-maintained)

### Output
Structured JSON with three fields:
- **score** — numeric 1–10 fit score
- **summary** — 2 sentence max, for list views
- **assessment** — full reasoning

Parse failures fall back gracefully: score 0, raw response preserved.

> Note: score reliability requires prompt engineering iteration — scores should not be trusted for sorting until the prompt is validated.

### Re-evaluation
- Supported manually (e.g. `re-evaluate` command or dashboard button)
- Triggered when criteria change or explicitly requested
- Each evaluation is versioned — old evaluations are not overwritten

### Batch Prioritization
- LLM ranks a set of jobs comparatively, not in isolation
- Results are cached with a timestamp
- Cache invalidated when scores or criteria change
- Not a replacement for per-job evaluation — a complementary view

### LLM
- Provider-agnostic — swap via `LLM_PROVIDER` env var
- Currently: Anthropic Claude
- Model and prompt configurable

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
| `deleted` | INTEGER | Soft delete flag (0/1) |
| `scraped_at` | TEXT | ISO 8601 UTC |

### `evaluations` table
| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER PK | |
| `job_id` | INTEGER FK | References `jobs.id` |
| `criteria_hash` | TEXT | Hash of criteria file at evaluation time |
| `score` | INTEGER | 1–10 |
| `summary` | TEXT | 2-sentence max |
| `assessment` | TEXT | Full LLM reasoning |
| `evaluated_at` | TEXT | ISO 8601 UTC |

---

## Dashboard

**Stack:** FastAPI + Jinja2 + vanilla JS + Pico.css. No build step, localhost only.

### Views & Routes

| View | Route | Purpose |
|---|---|---|
| Main list | `GET /` | Sortable table of jobs by score |
| Evaluate | `POST /jobs/evaluate` | Submit URL → fetch → score → persist |
| Detail | `GET /jobs/<id>` | Full assessment + metadata |
| Prioritize | `POST /jobs/prioritize` | Cached LLM batch ranking |
| Status update | `POST /jobs/<id>/status` | Inline status change |
| Delete/Restore | `POST /jobs/<id>/delete` + `/restore` | Soft delete management |

### Job Lifecycle
Status flows linearly: `saved → applied → in-process → offer | rejected`
- No arbitrary jumping forward
- One step back allowed (misclick protection)
- Deleted jobs hidden by default, recoverable via toggle

### UI Principles
- Pinned "evaluate a job" URL input bar at top of list view
- Prioritize button triggers batch ranking
- Click-to-expand rows for summary → full assessment
- Minimal, functional — no JS framework, no Tailwind

---

## Project Structure

```
job-scraper/
├── main.py                  # CLI pipeline entry point
├── criteria.txt             # User-maintained evaluation criteria
├── data/
│   └── jobs.db              # SQLite database
├── src/
│   ├── scraper/             # LinkedIn crawler + card parser
│   ├── fetcher/             # JD fetcher (Playwright)
│   ├── db/                  # DB init, read, write
│   ├── evaluator/           # LLM evaluation logic + providers
│   └── dashboard/           # FastAPI app + templates (planned)
└── tests/
```

---

## Immediate Next Steps

1. Update evaluator to return structured JSON (score, summary, assessment)
2. Update DB schema — add score, summary to evaluations; status, deleted to jobs
3. Build FastAPI dashboard

---

## Future Directions

- Chrome extension as a convenience ingest layer
- Staleness-based re-fetch (jobs older than N days)
- Criteria versioning and diff
- Multi-criteria profiles (e.g. "dream job" vs "acceptable")
