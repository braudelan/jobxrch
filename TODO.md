# TODO

## Inbox


## Short-term


## Ideas

### Misc.
- Browser extension as a clip-from-anywhere ingest layer
- Job age/staleness indicators

### Improve UI
- Better progress/status indication for the manual URL ingestion page.
- Thinking indication for chat

### Conversations & job-scoped context
- Named, resumable conversations tied to specific job postings (accessible from job detail page)
- Persisted job context: store AI insights, user notes, and contacts per job
    - Surface context to LLM during chat
    - Display in job listing/detail views

### Tracking capabilities
- Track time-based metrics: application submission dates, response times, interview schedules, and follow-up reminders

### Application outcome feedback loop
Track application outcomes (callbacks, rejections, offers) and feed that data back into profile refinement — so the scoring model learns from real-world signal over time.

### Tool discoverability
- **Seed script** (`seed_demo.py`): populate a fresh DB with a realistic profile, 8-10 varied job postings (spanning score range + statuses), evaluations, and a sample chat history — so anyone who clones the repo can immediately see a populated app
- **Screen recording**: short demo walkthrough (dashboard → job detail → chat) using the seeded DB, embedded in README as a GIF or linked video
- **Live public demo** (future): deploy with seeded DB + rate-limited live LLM; open questions are cost/abuse guard and state reset across visitors; Fly.io/Railway are viable hosts
- **Docs**: expand README with fuller setup walkthrough, configuration options, and a usage guide covering the main workflows (pipeline, ingest, evaluate, chat, profile)
