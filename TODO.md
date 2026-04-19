# TODO

## Inbox

## Short-term

### Improve UI/UX
- Tool call visibility in chat: lightweight inline indicators showing what the LLM is doing in the background — e.g. "Fetched job: Senior Engineer at Stripe", "Listed all CV versions". Not verbose, just the main operations as they happen.
- Up arrow key to restore previous input in chat input box
- Better progress/status indication for the manual URL ingestion page.
- Thinking indication for chat.
- Control model choice from chat.

### App module structure
- A dedicated module for tool definitions - `_SEARCH_WEB_TOOL`, `_GET_JOB_DETAILS_TOOL`. These can then be imported into the chat.py,


### Conversations & job-scoped context
- Named, resumable conversations tied to specific job postings (accessible from job detail page)
- Persisted job context: store AI insights, user notes, and contacts per job
    - Surface context to LLM during chat
    - Display in job listing/detail views



## Long term 

### New features

#### Profiler - User profile drafting and refinement 

**Purpose**
A dedicated interface for building and maintaining the master profile as a high-quality LLM context document. The primary output is a structured, accurate, well-covering profile that LLM features (cv_tailor, evaluate, chat) rely on as their shared input.

**Core interface**
A guided drafting session. The LLM acts as a collaborative editor helping the user articulate — clearly and accurately — who they are, what they bring, and where they're going. Conversation is grounded in two sources of reality: what the user actually has (experience, skills, constraints, red lines) and what the market actually requires. Where user intent and market signal diverge, the LLM surfaces the tension without resolving it unilaterally.

The session has a defined lifecycle: **open → draft/refine → commit**. Commit triggers an explicit distillation step that writes the result to the master profile.

**Market grounding**
Two sources combined at session open:
- **Saved jobs DB** — pattern recognition across what the user has already engaged with (recurring requirements, score distributions, what high-scoring roles have in common)
- **Web search** — targeted queries for the user's stated or inferred target roles, run as a bounded upfront step to surface market requirements, terminology, and seniority signals beyond the user's existing saved set. Broader trend queries ("what do companies look for in X") add directional context.

Web search runs once at session open as an explicit context-building phase — not ad-hoc tool use throughout. Latency and query quality are known risks; queries are LLM-formulated but bounded in number.

**What makes it distinct from general chat**
Tighter system prompt scoped entirely to profile work. The LLM is not a career coach — it's a profile editor with market awareness. It helps the user find the most accurate and viable expression of their direction, grounded in real data from both sides.

**Relationship to existing code**
Builds on existing profile storage, the jobs DB, and the web search infrastructure. The specific functions and prompt patterns will be designed for this interface — existing utilities in `profile.py` and `chat.py` are a reference point, not a constraint.

---

#### CV Builder / Tailor feature (WIP)
- **CV page**: paste a pre-formatted CV seed, saved as base version
- **Version control**: `cv_versions` table — `id`, `created_at`, `label`, `content`, `job_id` (nullable), `parent_id` (nullable)
- **Tailor action**: from job detail page, LLM generates a tailored variant (child of base, linked to job)
- **Editor**: section-by-section editable UI
- **Export**: download as `.docx` (via `python-docx`) for smooth Google Docs import

### Project evolution document
A single document (name TBD — `DEVLOG.md`, `EVOLUTION.md`, or similar) with two sections: "Current State" (updated in place, deeper than README — captures *why* things are the way they are) and "Decision Log" (append-only, newest first — architectural, philosophical, and major implementation shifts). Audience: personal reference and GitHub readers who want to follow the project's evolution.

### Misc.
- Browser extension as a clip-from-anywhere ingest layer
- Job age/staleness indicators

### Tracking capabilities
- Track time-based metrics: application submission dates, response times, interview schedules, and follow-up reminders

### Application outcome feedback loop
Track application outcomes (callbacks, rejections, offers) and feed that data back into profile refinement — so the scoring model learns from real-world signal over time.

### Tool discoverability
- **Seed script** (`seed_demo.py`): populate a fresh DB with a realistic profile, 8-10 varied job postings (spanning score range + statuses), evaluations, and a sample chat history — so anyone who clones the repo can immediately see a populated app
- **Screen recording**: short demo walkthrough (dashboard → job detail → chat) using the seeded DB, embedded in README as a GIF or linked video
- **Live public demo** (future): deploy with seeded DB + rate-limited live LLM; open questions are cost/abuse guard and state reset across visitors; Fly.io/Railway are viable hosts
- **Docs**: expand README with fuller setup walkthrough, configuration options, and a usage guide covering the main workflows (pipeline, ingest, evaluate, chat, profile)
