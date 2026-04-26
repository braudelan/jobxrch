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

### Chat-centric UI redesign

A major shift in the app's design philosophy: the chat interface becomes the primary surface, with the structured grammar operations (evaluate, tailor CV, company overview) surfaced as first-class actions from within it.

**The idea**
Rather than the current tab-per-feature layout, the chat panel is the center of the page. Grammar operations are invokable from alongside it — as buttons, a command palette, slash commands, or natural language. Results render inline in the chat thread, where they can be immediately discussed or acted on.

**Interaction models to explore**
- **Hybrid** (preferred direction): explicit action buttons/shortcuts for discoverability, also invokable through chat. The thread becomes a unified history of conversation and operation outputs.
- **Chat-only**: no buttons — all operations triggered via natural language or slash commands (e.g. `/tailor 42`). Lower UI complexity, higher discoverability barrier.
- **Chat + action toolbar**: grammar operations live in a persistent toolbar or side panel adjacent to the chat.

**Why this matters**
The current layout (chat as one tab among many) undersells the grammar framing. Making chat central and operations accessible from it makes the tool's model explicit: these are named, composable operations on your job search data, not isolated pages.

**Open questions**
- Where does the job list live in this layout?
- How are operation results persisted and revisitable in the thread?
- Does each job still have its own detail page, or does that collapse into the chat?

---

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

#### Company Overview *(grammar component)*

A dedicated LLM operation — `company_overview(company_name, job_description?) → structured brief` — that synthesizes a structured snapshot of a company from web search results. A first-class member of the grammar alongside evaluate, cv_tailor, and chat.

**Output** — validated JSON artifact: what the company does, size/stage, tech stack, culture signals, recent news, potential red flags. Rendered on demand, not free prose.

**How it works** — web search is the primary input. The operation formulates targeted queries, fetches results, and synthesizes them into structure. Builds directly on the existing `search.py` infrastructure.

**Where it surfaces** — no dedicated page needed. Natural fit as an on-demand section on the job detail page, and as a callable tool from chat. Could also be consumed by evaluation (replacing its ad-hoc company search) as a shared upstream artifact.

**Caching** — results should be stored per company with a timestamp so repeated views don't re-fetch. Worth designing for from the start even if deferred.

---

#### CV Builder / Tailor feature (WIP)
- **CV page**: paste a pre-formatted CV seed, saved as base version
- **Version control**: `cv_versions` table — `id`, `created_at`, `label`, `content`, `job_id` (nullable), `parent_id` (nullable)
- **Tailor action**: from job detail page, LLM generates a tailored variant (child of base, linked to job)
- **Editor**: section-by-section editable UI
- **Export**: download as `.docx` (via `python-docx`) for smooth Google Docs import

### Project evolution document
A single document (name TBD — `DEVLOG.md`, `EVOLUTION.md`, or similar) with two sections: "Current State" (updated in place, deeper than README — captures *why* things are the way they are) and "Decision Log" (append-only, newest first — architectural, philosophical, and major implementation shifts). Audience: personal reference and GitHub readers who want to follow the project's evolution.

### Manual job ordering and priority override

Two complementary ways for the user to assert their own judgment over the job list ranking:

**Manual reorder** — drag-and-drop (or up/down controls) to set an explicit `sort_order` on jobs. Once any manual ordering exists, it takes precedence over LLM-score-based sorting. New jobs (null `sort_order`) appear at the top so the user can slot them in.

**Score override** — an inline editable field on the score badge in the list and detail views. The user's score replaces the LLM score for display and sorting purposes without deleting the original evaluation. Stored as `score_override` on the job.

**Why this matters** — LLM scores reflect profile fit, but the user has context the model doesn't: insider knowledge of a company, a referral, or a gut feeling. The list should be theirs to shape.

---

### Misc.
- Browser extension as a clip-from-anywhere ingest layer
- Job age/staleness indicators

### Job lifecycle management

The current model treats jobs as static records with a single overwritten status field. A complete system needs to capture the full lifecycle of an application.

**Timeline / audit trail** — a `job_events` table of timestamped events per job (`saved`, `applied`, `interview_scheduled`, `rejected`, `offer_received`, etc.) rather than a single mutable status. Preserves history, enables time-based metrics: how long between save and apply, how long in progress, when was it rejected.

**Application context** — per-job metadata that doesn't fit the schema: applied via LinkedIn / direct / referral, who referred you, which CV version was sent, cover letter notes.

**Archiving** — distinguish between `deleted` (noise, irrelevant) and `archived` (considered, deliberately parked for later). Archived jobs remain visible but out of the active pipeline.

**Staleness indicators** — surface job age visually. A posting saved 3 months ago with no action is very different from one saved yesterday.

**Pipeline view** — stage-grouped or kanban view of active applications for a scannable overview of the current search state.

---

#### Application response parsing *(grammar component)*

A dedicated LLM operation — `parse_application_response(email_text) → job event` — that reads an email, identifies the job, classifies the event type, and writes a timestamped entry to the job's event timeline.

**What the LLM does** — classification and extraction: is this a rejection, interview request, offer, or generic acknowledgement? What's the next step? When is the interview? Output is a validated structured event, not free text.

**v1 — manual paste** (no OAuth): a "log response" action on the job detail page where you paste email text. LLM classifies and logs the event. Same operation, zero infrastructure risk.

**v2 — Gmail integration**: OAuth connection, polling or push (Gmail pub/sub), automatic ingestion. The hard part is reliable matching — mapping "Senior Engineer at Acme" in an email back to the correct job record when multiple similar jobs may be saved. Privacy note: with a cloud LLM provider, email content leaves the machine.

**Feedback loop** — parsed outcomes (rejections, callbacks, offers) feed back into profile refinement over time. The scoring model learns from real-world signal.

---

### Tool discoverability
- **Seed script** (`seed_demo.py`): populate a fresh DB with a realistic profile, 8-10 varied job postings (spanning score range + statuses), evaluations, and a sample chat history — so anyone who clones the repo can immediately see a populated app
- **Screen recording**: short demo walkthrough (dashboard → job detail → chat) using the seeded DB, embedded in README as a GIF or linked video
- **Live public demo** (future): deploy with seeded DB + rate-limited live LLM; open questions are cost/abuse guard and state reset across visitors; Fly.io/Railway are viable hosts
- **Docs**: expand README with fuller setup walkthrough, configuration options, and a usage guide covering the main workflows (pipeline, ingest, evaluate, chat, profile)
