# eval/ — LLM Evaluation Pipeline (llmEV)

Offline scoring pipeline for `cv_tailor` first-shot generations. Reads `raw_llm_log` after the fact and writes scored records to `cv_tailor_scores`. Nothing in `src/` imports this directory — it's a developer tool in the same category as `notebooks/`.

The full scoring rubric and architecture rationale live in [`cv_tailor_quality_contract.md`](cv_tailor_quality_contract.md). This document covers how to run the pipeline and how to extend it.

---

## Running the scorer

Run from the repo root:

```bash
# Full pipeline — Tier 1 (deterministic) + Tier 2 (grounding) + Tier 3 (relevance)
python -m eval.run_scorer

# Tier 1 only — zero LLM judge calls; use this to validate historical data cheaply
python -m eval.run_scorer --max-tier 1

# Score without writing to the DB (verify output before committing)
python -m eval.run_scorer --dry-run
```

Already-scored log entries are skipped on re-runs, so the runner is safe to run repeatedly as new `cv_tailor` calls accumulate in `raw_llm_log`.

**Provider:** the judge uses the same `LLM_PROVIDER` env var as the main app (`anthropic` by default). Set it in `.env` or export it before running.

---

## Scoring model (three tiers)

Each evaluation unit (bullet, summary, skill category) is scored in three tiers that run in sequence — if a tier fails, later tiers are skipped.

| Tier | Type | What it checks | Labels |
|---|---|---|---|
| **1** | Deterministic | Citation presence — are `source_sections` non-empty and do they exist in the profile? | `uncited`, `invalid_citation` |
| **2** | LLM judge | Grounding — does the bullet follow from the cited profile sections? | `supported`, `unverified`, `hallucinated` |
| **3** | LLM judge | Relevance — does the bullet serve the job description? | `highly_relevant`, `partially_relevant`, `irrelevant` |

Score thresholds (0.7 / 0.4) are provisional — calibrate against a manually-labeled sample from the first scored batch.

---

## Output

Results land in the `cv_tailor_scores` table (created automatically on first run). Each row is one evaluation unit with grounding and relevance scores, labels, and a pointer back to `raw_llm_log.id`.

Useful queries:

```sql
-- Hallucination rate by model
SELECT model, grounding_label, COUNT(*) FROM cv_tailor_scores GROUP BY model, grounding_label;

-- Bullets that are well-grounded but irrelevant (accurate but untargeted)
SELECT bullet_title, bullet_text, context FROM cv_tailor_scores
WHERE grounding_label = 'supported' AND relevance_label = 'irrelevant';

-- Profile sections that consistently produce weak grounding
SELECT source_sections, AVG(grounding_score), COUNT(*)
FROM cv_tailor_scores
WHERE grounding_score IS NOT NULL
GROUP BY source_sections ORDER BY AVG(grounding_score) ASC;
```

---

## Module map

| File | Role |
|---|---|
| `judge.py` | Generic LLM-as-judge primitive: `judge(reference, claim, question) → JudgeResult(score, rationale)`. Knows nothing about CVs. Reusable by any future feature scorer. |
| `cv_tailor_scorer.py` | cv_tailor-specific logic: profile section extraction, Tier 1/2/3 rubric, output record assembly. Calls into `judge.py` for Tiers 2 and 3. |
| `db.py` | DB layer: reads `raw_llm_log`, writes `cv_tailor_scores`. |
| `run_scorer.py` | CLI runner that wires the above together. |
| `cv_tailor_quality_contract.md` | Authoritative spec — scoring questions, rubric, output schema, design decisions. Read this before changing scoring logic. |

---

## Adding a scorer for a new feature

1. Write a quality contract (follow `cv_tailor_quality_contract.md` as a template).
2. Add a `<feature>_scorer.py` with an `_iter_units()` function that yields evaluation units from the feature's `output_payload`, and a `score_log_entry()` that calls `judge.py` for LLM-graded tiers.
3. Add DB functions to `db.py` (or a new `<feature>_db.py`) for reading log entries and writing scored records.
4. Add a runner script or extend `run_scorer.py` with a `--feature` flag.

The one reusable seam is `judge.py` — the scoring question and reference/claim framing change per feature, but the call signature doesn't.
