# eval/run_scorer.py
"""CLI runner for the cv_tailor llmEV scoring pipeline.

Usage (from repo root):
    python -m eval.run_scorer [--max-tier {1,2,3}] [--dry-run]

Fetches all cv_tailor entries from raw_llm_log, skips already-scored rows,
scores each one via cv_tailor_scorer, and writes results to cv_tailor_scores.
"""
import argparse
import sys

from eval.db import get_cv_tailor_log_entries, get_scored_log_ids, init_scores_table, save_score_records
from eval.cv_tailor_scorer import score_log_entry


def main():
    parser = argparse.ArgumentParser(description="Score cv_tailor log entries.")
    parser.add_argument("--max-tier", type=int, choices=[1, 2, 3], default=3,
                        help="Stop after this tier (1=deterministic only, 2=+grounding, 3=+relevance)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Score but do not write results to DB")
    args = parser.parse_args()

    init_scores_table()

    entries = get_cv_tailor_log_entries()
    scored_ids = get_scored_log_ids()
    pending = [e for e in entries if e["id"] not in scored_ids]

    print(f"{len(entries)} total entries, {len(scored_ids)} already scored, {len(pending)} to score")

    if not pending:
        print("Nothing to do.")
        return

    total_records = 0
    for i, entry in enumerate(pending, 1):
        log_id = entry["id"]
        job_id = entry.get("job_id")
        print(f"[{i}/{len(pending)}] log_id={log_id} job_id={job_id} model={entry['model']}", end=" ... ", flush=True)
        try:
            records = score_log_entry(entry, max_tier=args.max_tier)
        except Exception as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            continue

        if not args.dry_run:
            save_score_records(records)

        labels = [r["grounding_label"] for r in records]
        print(f"{len(records)} units — {', '.join(labels)}")
        total_records += len(records)

    action = "would write" if args.dry_run else "wrote"
    print(f"\nDone. {action} {total_records} scored records.")


if __name__ == "__main__":
    main()
