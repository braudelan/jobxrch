# jobXrch

A personal, local-first job search intelligence tool. It ingests job postings, evaluates them against your career profile using an LLM, and acts as a thinking partner for your search — not just a tracker.

Everything runs locally on SQLite and localhost. No cloud, no SaaS dependency.

---

## Philosophy

Job searching is high-volume and low-signal. The goal is to use AI not as a novelty but as a filter and a thinking partner — to surface what's worth your time and help you reason about your search strategically.

This tool has two distinct layers:

- **Pipeline layer** — scrape, fetch, evaluate, and store jobs with LLM-scored assessments
- **Coaching layer** — a chat interface with live DB access that helps reason about tradeoffs, and a persistent career profile that evolves through conversation and feeds back into evaluation

The profile replaces a static criteria file. Preferences are distilled from conversation, not maintained by hand.

### Design principles

- **Robustness over features** — solid backbone first, elaborate later
- **Source agnosticism** — the pipeline doesn't care where a job came from
- **Separation of concerns** — ingest, fetch, evaluate, and store are independent stages, each replaceable
- **Living profile over static criteria** — goals are shaped through dialogue, not manual editing
- **Local-first** — no cloud dependency; runs entirely on SQLite and localhost
- **Criteria versioning** — evaluations are hashed against the profile at eval time; re-scoring is always opt-in

---

## Stack

- **Python** + FastAPI, Jinja2, Click
- **SQLite** for local persistence
- **Playwright** for browser automation (LinkedIn scraper)
- **Claude** (default) or Gemini (selectable via `LLM_PROVIDER`) for evaluation and chat

---

## Features

### Done

- LinkedIn scraper with pagination (Playwright-based)
- Job description fetcher with LLM fallback for metadata extraction
- LLM evaluation: score 1–10, two-sentence summary, full markdown assessment
- Profile-versioned scoring — re-evaluation is always opt-in
- FastAPI dashboard: job list with filter/sort, job detail page, status tracking, soft delete
- Ingest page — paste job URLs, runs async in background with progress polling
- AI chat interface — career coach with live read access to the job DB
- Profile editor — DB-backed profile editable in UI, replaces static criteria file
- Profile distillation — extracts preference signals from chat back into the profile
- CLI: `pipeline`, `dashboard`, `evaluate-all` commands

### Near-term

- Named conversations and job-scoped chat — conversations tied to a specific posting ("chat about this job" from the detail page), saved and resumable.
- Browser extension as a clip-from-anywhere ingest layer
- Job age/staleness indicators

### Longer-term

- Application outcome data (what kinds of jobs led to callbacks?) feeding back into profile refinement

---

## Usage

```bash
# Run the LinkedIn scraper pipeline
python main.py pipeline

# Evaluate all unevaluated jobs
python main.py evaluate-all

# Start the web dashboard (default: localhost:8000)
python main.py dashboard
python main.py dashboard --port 8080
```

### Setup

```bash
pip install -r requirements.txt
playwright install chromium

# Copy and fill in API keys
cp .env.example .env
```

Required env vars: `ANTHROPIC_API_KEY`. Optional: `GEMINI_API_KEY` for fallback.
