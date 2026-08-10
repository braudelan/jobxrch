# CV Tailor Quality Contract

_Written: 2026-05-26_

---

## 1. Purpose

This document defines the quality contract for first-shot `cv_tailor` generations: what is measured, how it is measured, and what the output looks like. It is the authoritative spec for the llmEV scorer pipeline. Implementation choices (NLI engine, storage backend) are downstream of this contract and intentionally deferred.

---

## 2. Evaluation unit

The atomic unit of evaluation is a single `Bullet`:

```python
class Bullet(BaseModel):
    title: str
    text: str
    source_sections: list[str]
```

One scored record is produced per bullet. `Summary` and `SkillCategory` carry `source_sections` too and are scored identically. `education` and `header` are static fields — out of scope.

---

## 3. Data source and run metadata

All scorer inputs are read from `raw_llm_log` where `task_type = 'cv_tailor'`. Two fields are used per run:

- `input_payload["master_profile"]` — profile snapshot at generation time. Always read from here, never from `user_profile`.
- `input_payload["job_description"]` — job description at generation time. Required for Tier 3 relevance scoring.
- `output_payload` — full `CVTailorResult` JSON with all `source_sections` preserved.

Run metadata available per entry: `run_id`, `job_id`, `model`, `prompt_content`, `latency_ms`, `cost_usd`, `timestamp`.

**Schema change required:** `job_id` must be added to `raw_llm_log`. `generate_cv_tailor()` already receives `job_id` — it just needs to pass it through to `log_llm_call()`.

**Prompt versioning:** `prompt_content` is stored in full. A prompt hash is derivable at score time — no need to store it at log time.

---

## 4. Profile structure requirement

The master profile must use `##` section headers:

```
## Core Identity
A data professional bridging...

## Professional Timeline
Forter (2022–2026)...
```

Section extraction splits the profile text on `^## ` lines, producing a `{section_name: section_text}` map. Section names are open — no fixed schema. The snapshot in `input_payload["master_profile"]` is always the extraction source, never the current `user_profile` table.

**Note:** The existing profile in the DB must be migrated to this format before any scorer runs. The `cv_tailor` prompt passes the profile as raw text and requires no changes — `##` headers are readable LLM context.

---

## 5. Scoring question

For each evaluation unit, the scorer asks:

> *Does the claim in `bullet.text` follow from the content of the sections named in `bullet.source_sections`, as those sections appear in the profile snapshot?*

The **reference** is the concatenated text of the cited source sections extracted from the profile snapshot (in citation order). The **claim** is `bullet.text`. (Named generically rather than NLI's premise/hypothesis — see section 12 — since the same engine is reused for Tier 3's relevance question, which isn't an entailment relationship.)

**Engine: LLM-as-judge**

The intended scoring engine is LLM-as-judge, not a dedicated NLI classification model. This is consistent with current industry practice — G-Eval (2023) demonstrated that LLM-as-judge matches or exceeds NLI classifiers on faithfulness evaluation when given a structured rubric, and it is the default approach in frameworks like RAGAS. It is the right choice here because CV bullets frequently make inferential or paraphrased claims — exactly where classification models fail. A classifier scores direct paraphrase well but assigns `neutral` to valid inferential claims, producing false negatives that would distort the diagnostic signal.

The judge is given a narrow, structured task: does this specific claim follow from this specific text? This mitigates the known same-family bias risk (Claude judging Claude's output) — sycophancy is a concern for open-ended quality judgments, not for constrained entailment checks.

A local NLI model (e.g. `cross-encoder/nli-deberta-v3-small`) remains a viable fallback for cost or latency-sensitive batch runs. The engine is a swappable component — the interface is identical regardless of implementation: takes (reference, claim), returns a score in [0.0, 1.0].

**Reference construction:** When multiple sections are cited, concatenate in citation order as a single reference. If the concatenated text is too long (a concern for local NLI models with 512-token limits; not for LLM-as-judge), score each cited section independently and take the maximum entailment score.

---

## 6. Rubric

Quality checks run in three tiers:

**Tier 1 — Deterministic pre-checks** (no scoring engine invoked)

| Label | Condition | Score |
|---|---|---|
| `uncited` | `source_sections` is empty | `null` |
| `invalid_citation` | One or more cited sections absent from the profile snapshot | `null` |

If either condition is true, scoring stops. Tiers 2 and 3 are not invoked.

**Tier 2 — Grounding**

Asks: *does this bullet follow from its cited profile sections?*

| Label | Meaning | Score |
|---|---|---|
| `supported` | Reference clearly supports the claim | ≥ 0.7 |
| `unverified` | Reference neither confirms nor contradicts | 0.4 – 0.7 |
| `hallucinated` | Claim contradicts or asserts facts absent from the reference | < 0.4 |

**Tier 3 — Relevance**

Asks: *does this bullet serve the job description?*

Scored independently from grounding using the job description as context. The two axes are orthogonal — a bullet can be perfectly grounded but irrelevant (accurate but untargeted), or relevant but hallucinated (useful but dishonest):

| | High relevance | Low relevance |
|---|---|---|
| **High grounding** | Ideal | Accurate but untargeted |
| **Low grounding** | Relevant but hallucinated | Both wrong |

| Label | Meaning | Score |
|---|---|---|
| `highly_relevant` | Bullet directly addresses a key job requirement | ≥ 0.7 |
| `partially_relevant` | Bullet is adjacent but not central to the job | 0.4 – 0.7 |
| `irrelevant` | Bullet does not serve the job description | < 0.4 |

All score thresholds are provisional — calibrate against the first scored batch by manually labeling a sample.

---

## 7. Out of scope

The following quality dimensions are explicitly excluded from this framework:

- **Schema conformance** — structural validity of `CVTailorResult` is enforced at generation time by Pydantic. Any entry in `raw_llm_log` has already passed this check.
- **Static field integrity** — correctness of fixed fields (company names, periods, education) is a generation-time concern, enforceable as a template validator. Not an evaluation signal.
- **Tone and style** — qualitative assessment of how the CV reads. A separate quality dimension requiring LLM-aided evaluation. Out of scope for v1.
- **Refinement loop output** — only first-shot generations are evaluated. Once a human edits a bullet, the profile is no longer the sole grounding truth.
- **Job relevance at the CV level** — Tier 3 scores relevance per bullet. Holistic CV-level relevance to the job is not measured here.
- **Score aggregation** — scored records are stored at bullet level only. Aggregation (mean, median, failure rate, stratified by context or profile section) is computed at query time. No pre-computed aggregates are stored.

---

## 8. Output schema

One scored record per evaluation unit:

```python
{
    "run_id": str,
    "log_id": int,
    "job_id": int | None,
    "timestamp": str,
    "model": str,
    "context": str,              # e.g. "experience:Forter", "summary", "skills:Languages"
    "bullet_title": str,
    "bullet_text": str,
    "source_sections": list[str],
    "missing_sections": list[str],   # cited but absent from snapshot
    "reference": str | None,         # concatenated cited section text; null if uncited/invalid
    "grounding_score": float | None,
    "grounding_label": str,          # supported | unverified | hallucinated | invalid_citation | uncited
    "relevance_score": float | None,
    "relevance_label": str | None,   # highly_relevant | partially_relevant | irrelevant | null if tier 1 failure
}
```

`relevance_score` and `relevance_label` are null for Tier 1 failures — if a bullet is uncited or has an invalid citation, relevance is not evaluated.

---

## 9. Diagnostic value

The scored records are designed to answer the following questions:

**Quality diagnosis**
- Which bullets are hallucinated, uncited, or have invalid citations?
- Which profile sections are consistently cited but produce weak grounding scores?
- Which bullets are well-grounded but irrelevant to the job — accurate but untargeted?

**Run comparison**
- Did a prompt change improve grounding scores relative to a previous run?
- Did a model change improve relevance without degrading grounding?
- Group by `model` and prompt variant (derived by hashing `prompt_content`) to compare score distributions across runs with different parameters.

**Profile quality feedback**
- If certain profile sections consistently produce `unverified` or `hallucinated` across many runs and jobs, the section itself may be too vague or poorly written — the eval becomes a tool for improving the profile, not just the prompt.

**Cost/quality tradeoff**
- `latency_ms` and `cost_usd` are available per run in `raw_llm_log`. Combined with grounding and relevance scores, cost per quality point is computable across models.

---

## 10. Open decisions

The following decisions are intentionally deferred to the build phase:

- **NLI engine implementation** — LLM-as-judge is the intended approach. Local model (`cross-encoder/nli-deberta-v3-small`) is the fallback. Consider benchmarking both on the first scored batch.
- **Score thresholds** — the 0.7/0.4 boundaries in Tiers 2 and 3 are provisional. Calibrate by manually labeling a sample from the first scored batch.
- **Batch generation for calibration** — once the scorer is implemented, consider cheaper batch generation options (smaller model, existing jobs in DB) to produce volume for threshold calibration and prompt comparison.

## 11. Decided

- **Scored record storage** → new DB table, schema per Section 8. Consistent with the app's SQLite-first pattern; queryable and joins naturally to `raw_llm_log` and `jobs`.
- **Reference length handling** → concatenate cited sections in citation order as a single reference. LLM-as-judge handles long context; revisit only if a local model fallback is adopted.

---

## 12. Module architecture

- **Lives in `eval/`, outside `src/`.** llmEV is an offline analysis tool that reads `raw_llm_log` after the fact — nothing in `src/` imports it, and it doesn't instrument `cv_tailor.py` beyond the `job_id` passthrough in section 3. Same category as `notebooks/`: a developer tool, not a runtime application feature.
- **Two modules for the MVP, split on the one seam the contract already calls for** (section 5 — the engine is swappable, independent of the cv_tailor-specific extraction logic):
  - `eval/judge.py` — the generic LLM-as-judge primitive: `judge(reference, claim, question) -> JudgeResult(score, rationale)`. Deliberately neutral naming, not NLI's premise/hypothesis — only Tier 2's entailment check is genuinely premise/hypothesis; Tier 3's relevance check is a different relationship (does the claim address something in the reference, not does it follow from it) and the shared primitive shouldn't imply otherwise. Knows nothing about CVs, bullets, or profiles. Reusable by any future feature that needs an LLM-judged score.
  - `eval/cv_tailor_scorer.py` — everything specific to cv_tailor: profile section extraction (`## ` splitting), the Tier 1/2/3 rubric, and assembly of Section 8 output records. Calls into `judge.py` for Tiers 2 and 3.
- **No generalized scoring framework yet.** A shared base for "evaluation unit" extraction across features, or a single scored-records table reused by every feature, is explicitly deferred. With only one feature (cv_tailor) having a written contract, generalizing now means guessing at a shape with no second data point to validate it against. Revisit when a second feature (e.g. `evaluate`) needs scoring.
