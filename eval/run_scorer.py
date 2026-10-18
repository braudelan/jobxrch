# eval/run_scorer.py
"""CLI runner for the cv_tailor llmEV scoring pipeline.

Usage (from repo root):
    python -m eval.run_scorer [--max-tier {1,2,3}] [--log-id ID] [--dry-run]

Fetches all cv_tailor entries from raw_llm_log, skips already-scored rows,
scores each one via cv_tailor_scorer, and writes results to cv_tailor_scores.
"""
import argparse
import sys
import time

from eval.db import get_cv_tailor_log_entries, get_scored_log_ids, init_scores_table, save_score_records
from eval.cv_tailor_scorer import score_log_entry


def _display_name(context: str, title: str) -> str:
    if context == "summary":
        return title
    if context.startswith("skills:"):
        return title
    if ":" in context:
        company = context.split(":", 1)[1]
        return f"{company} / {title}"
    return title


def main():
    parser = argparse.ArgumentParser(description="Score cv_tailor log entries.")
    parser.add_argument("--max-tier", type=int, choices=[1, 2, 3], default=3,
                        help="Stop after this tier (1=deterministic only, 2=+grounding, 3=+relevance)")
    parser.add_argument("--log-id", type=int, default=None,
                        help="Score only this specific raw_llm_log entry (skips already-scored check)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Score but do not write results to DB")
    args = parser.parse_args()

    init_scores_table()

    entries = get_cv_tailor_log_entries()
    if args.log_id is not None:
        pending = [e for e in entries if e["id"] == args.log_id]
        if not pending:
            print(f"No cv_tailor log entry with id={args.log_id}.")
            return
    else:
        scored_ids = get_scored_log_ids()
        pending = [e for e in entries if e["id"] not in scored_ids]

    if args.log_id is not None:
        print(f"Targeting log_id={args.log_id} — {len(pending)} entry to score")
    else:
        print(f"{len(entries)} total entries, {len(scored_ids)} already scored, {len(pending)} to score")

    if not pending:
        print("Nothing to do.")
        return

    total_units = 0
    total_hallucinated = 0
    all_grounding: list[float] = []
    all_relevance: list[float] = []
    start_total = time.monotonic()

    for i, entry in enumerate(pending, 1):
        log_id = entry["id"]
        job_id = entry.get("job_id")

        t0 = time.monotonic()
        try:
            records = score_log_entry(entry, max_tier=args.max_tier)
        except Exception as exc:
            print(f"\n[{i}/{len(pending)}] log_id={log_id} ERROR: {exc}", file=sys.stderr)
            continue
        elapsed = time.monotonic() - t0

        print(f"\n[{i}/{len(pending)}] log_id={log_id}  job_id={job_id}  {entry['model']}  ({elapsed:.1f}s)")

        entry_hallucinated = 0
        entry_grounding: list[float] = []
        entry_relevance: list[float] = []

        for r in records:
            name = _display_name(r["context"], r["bullet_title"])
            gscore = r.get("grounding_score")
            glabel = r["grounding_label"]
            rscore = r.get("relevance_score")
            rlabel = r.get("relevance_label")
            grationale = r.get("grounding_rationale") or ""
            rrationale = r.get("relevance_rationale") or ""

            print(f"  {name}")
            if gscore is not None:
                print(f"    grnd  {gscore:.2f}  {glabel:<20}  {grationale}")
            else:
                miss = r.get("missing_sections", [])
                suffix = f"  (missing: {', '.join(miss)})" if miss else ""
                print(f"    grnd  {glabel}{suffix}")
            if rlabel is not None and rscore is not None:
                print(f"    rel   {rscore:.2f}  {rlabel:<20}  {rrationale}")

            if glabel == "hallucinated":
                entry_hallucinated += 1
                total_hallucinated += 1
            if gscore is not None:
                entry_grounding.append(gscore)
                all_grounding.append(gscore)
            if rscore is not None:
                entry_relevance.append(rscore)
                all_relevance.append(rscore)

        total_units += len(records)

        parts = [f"{len(records)} units"]
        if entry_hallucinated:
            parts.append(f"{entry_hallucinated} hallucinated")
        if entry_grounding:
            parts.append(f"grnd avg {sum(entry_grounding)/len(entry_grounding):.2f}")
        if entry_relevance:
            parts.append(f"rel avg {sum(entry_relevance)/len(entry_relevance):.2f}")
        print(f"\n  {' · '.join(parts)}")

        if not args.dry_run:
            save_score_records(records)

    total_elapsed = time.monotonic() - start_total
    action = "dry-run" if args.dry_run else "saved"

    print(f"\n{'─' * 60}")
    parts = [f"{total_units} units"]
    if total_hallucinated:
        parts.append(f"{total_hallucinated} hallucinated")
    if all_grounding:
        parts.append(f"grnd avg {sum(all_grounding)/len(all_grounding):.2f}")
    if all_relevance:
        parts.append(f"rel avg {sum(all_relevance)/len(all_relevance):.2f}")
    parts.append(f"{total_elapsed:.1f}s total")
    print(f"{' · '.join(parts)}  ({action})")


if __name__ == "__main__":
    main()
