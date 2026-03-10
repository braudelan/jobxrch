# Job Evaluator — Blueprint

## North Star

A personal tool to quickly and efficiently evaluate job offers from any source against your aspirations, needs, and capabilities — powered by an LLM.

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
| **Fetch** | Given a link, retrieve the full job description | Done (Currently only works for Linkedin) |
| **Evaluate** | Run job + criteria through LLM, produce human-language assessment | Not started |
| **Store** | Persist job data and evaluation output to DB | Done (job data only) |

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
- **Additional scrapers** — for other job boards and sources
- **Chrome extension** — send basic job data + link directly to the pipeline from any job board
- **Manual paste** — CLI or UI input for job data without a link, or with a pre-known JD

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
- Human-language assessment of fit and misfit against criteria
- Stored alongside the job in the DB

### Re-evaluation
- Supported manually (e.g. `re-evaluate` command)
- Triggered when criteria change or when explicitly requested
- Each evaluation is versioned — old evaluations are not overwritten

### LLM
- Anthropic Claude (via API)
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
| `scraped_at` | TEXT | ISO 8601 UTC |

### `evaluations` table (planned)
| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER PK | |
| `job_id` | INTEGER FK | References `jobs.id` |
| `criteria_version` | TEXT | Hash or label of the criteria file used |
| `assessment` | TEXT | LLM output |
| `evaluated_at` | TEXT | ISO 8601 UTC |

---

## Project Structure

```
job-scraper/
├── main.py                  # Entry point, orchestrates the pipeline
├── criteria.txt             # User-maintained evaluation criteria
├── data/
│   └── jobs.db              # SQLite database
├── src/
│   ├── scraper/             # LinkedIn crawler + card parser
│   ├── fetcher/             # JD fetcher (Playwright)
│   ├── db/                  # DB init, read, write
│   └── evaluator/           # LLM evaluation logic (planned)
└── tests/
```

---

## Immediate Next Steps

1. Add `source` column to `jobs` table
2. Build `evaluator` module — criteria loading, prompt construction, LLM call
3. Wire evaluation into the main pipeline
4. Add `evaluations` table and persistence

---

## Future Directions

- Chrome extension as an ingest source
- Web UI / dashboard for browsing jobs and evaluations
- Staleness-based re-fetch (jobs older than N days)
- Criteria versioning and diff
- Multi-criteria profiles (e.g. "dream job" vs "acceptable")
- Application status tracking — add a `status` column to `jobs` with lifecycle: `saved` (default) → `applied` → `in-process` → `rejected` / `offer`
