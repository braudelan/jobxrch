# jobXrch

A local-first job search intelligence tool built around a defined set of LLM-powered operations. It provides a **grammar for interacting with language models over job search activity** — ingesting postings, evaluating fit, tailoring CVs, and reasoning about your search through structured, traceable outputs.

Everything runs locally on SQLite and localhost. No cloud, no SaaS dependency.

---

## Design Philosophy

Job searching is high-volume, low-signal, and deeply personal. jobXrch treats AI not as a chat novelty but as an execution layer for well-defined operations: evaluate this posting, tailor this CV, distill these preferences, score this output.

The tool is organized around two ideas:

**A shared data model.** A master profile, a job database, and a structured log of every LLM call form the backbone. Every feature reads from and writes to this shared foundation. The master profile is the single source of truth about the candidate — used by evaluation, CV tailoring, chat, and any future operation.

**Distinct, composable features.** Each LLM-powered function is a standalone module with its own input/output contract. They share infrastructure (profile, DB, provider abstraction, logging) but are otherwise independent. This makes each feature testable, replaceable, and evaluable in isolation.

### Principles

- **Structured output over prose** — LLM outputs are validated JSON artifacts, not free text. Downstream features (rendering, evaluation) operate on structure.
- **Log everything, evaluate later** — every LLM call writes full input, output, and prompt to `raw_llm_log`. llmEV reads this log to score output quality without instrumenting individual features. Each feature defines its own quality unit and scoring function.
- **Living profile** — the master profile evolves through use. Goals, constraints, and preferences are distilled from conversation, not maintained by hand.
- **Local-first** — SQLite, localhost, no external state. Run entirely offline with Ollama.
- **Source agnosticism** — the pipeline doesn't care where a job came from. LinkedIn scraper, manual URL paste, or direct entry all feed the same DB.

---

## Architecture

```
src/
├── cv_tailor.py          # CV tailoring pipeline
├── db/                   # SQLite layer — jobs, profile, CV versions, LLM log
├── llm_utils/
│   ├── providers/        # LLM provider abstraction (Anthropic, Gemini, Ollama)
│   ├── evaluate.py       # JD evaluation
│   ├── chat.py           # Career coach chat
│   ├── profile.py        # Master profile management
│   ├── context.py        # Shared formatting utilities
│   └── search.py         # Web search integration
├── scraper/              # LinkedIn scraper + JD fetcher
├── pipelines/            # Orchestration (LinkedIn pipeline)
└── web/                  # FastAPI dashboard + UI
```

> **Note:** The current layout is transitional. `cv_tailor.py` sits at the `src/` root while other main features (`evaluate`, `chat`) live under `llm_utils/`. As the feature set grows, main features will likely move into dedicated top-level packages under `src/` (e.g. `src/cv_tailor/`, `src/evaluate/`), with `llm_utils/` reduced to shared provider and utility code.

### Shared infrastructure

| Resource | Purpose |
| --- | --- |
| `user_profile` | Master profile — shared input to all LLM features |
| `jobs` + `evaluations` | Job DB with scored assessments |
| `cv_versions` | Versioned CV documents, linked to jobs |
| `raw_llm_log` | Full record of every LLM call (input, output, prompt, model, latency) |
| Provider abstraction | Swap Anthropic / Gemini / Ollama via `LLM_PROVIDER` env var |

---

## Features

### JD Evaluation
Scores a job posting 1–10 against the master profile with a full coaching assessment. Optional web search for company context. Evaluations are hashed against the profile version — re-scoring is always opt-in.

### CV Tailoring
Single-shot generation of a fully structured CV tailored to a specific job description. Fixed fields (company names, dates, education) are pre-populated from a static template; the LLM fills summaries, skill categories, taglines, and bullets. Every generated field cites its source section in the master profile, enabling factual entailment checking by llmEV. Output is a validated JSON artifact rendered to markdown via Jinja.

### Chat
Context-aware career coach with live read access to the job DB, CV versions, and web search. Fetches context on demand via tools — no eager loading. Profile preferences are distilled from conversation back into the master profile.

### Profile Management
The master profile is a structured markdown document merging raw CV and stated goals. It is the shared input to evaluation, CV tailoring, and chat. Built once via `build_master_profile()`, updated through conversation and distillation.

### Ingest Pipeline
LinkedIn scraper (Playwright-based), manual URL paste with async background fetching, and direct manual entry. All sources normalize to the same job schema.

### LLM Evaluation (llmEV) *(in design)*
Reads `raw_llm_log` to score first-shot output quality over time. NLI entailment per section against the master profile is the scoring function. Operates independently of the features that generate the logs.

---

## Stack

- **Python** — FastAPI, Jinja2, Click, Pydantic
- **SQLite** — all local persistence
- **Playwright** — LinkedIn browser automation
- **Anthropic Claude** (default), **Gemini**, or **Ollama** (local) — selectable via `LLM_PROVIDER`

---

## Usage

```bash
# Scrape LinkedIn saved jobs, fetch JDs, and store
python main.py pipeline

# Evaluate all unevaluated jobs against current profile
python main.py evaluate-all

# Start the web dashboard (default: localhost:8000)
python main.py dashboard
python main.py dashboard --port 8080
```

### Setup

```bash
pip install -r requirements.txt
playwright install chromium

cp .env.example .env
# Fill in ANTHROPIC_API_KEY (or GEMINI_API_KEY / configure Ollama)
```

To run fully offline with Ollama:
```bash
ollama pull qwen2.5:7b
# Set in .env: LLM_PROVIDER=ollama
```
