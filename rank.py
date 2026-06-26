#!/usr/bin/env python3
"""
rank.py — CLI entry point for the Redrob candidate ranker.

Usage:
    python rank.py --candidates ./data/candidates.jsonl --out ./submission.csv

Streams the candidate file, scores every candidate, selects the top 100
(score desc, candidate_id asc for ties), assigns ranks 1-100, and writes
a spec-compliant CSV.

No GPU, no network, no LLM — pure CPU rule-based scoring.
"""

import argparse
import heapq
import sys
import time

from src.io_utils import stream_candidates, write_submission
from src.score import composite_score, HONEYPOT_SENTINEL
from src.reasoning import build_reasoning


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Rank candidates against the Redrob AI JD.")
    p.add_argument(
        "--candidates",
        required=True,
        help="Path to candidates.jsonl (or .jsonl.gz)",
    )
    p.add_argument(
        "--out",
        required=True,
        help="Output CSV path (e.g. team_xyz.csv)",
    )
    p.add_argument(
        "--top",
        type=int,
        default=100,
        help="Number of candidates to shortlist (default 100)",
    )
    p.add_argument(
        "--verbose",
        action="store_true",
        help="Print top-20 to stdout after writing",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    t0 = time.time()

    print(f"[rank] reading candidates from {args.candidates} ...", flush=True)

    # Min-heap keyed by (score, candidate_id).
    # heap[0] is always the lowest-scoring entry in the current top-N window,
    # so we can efficiently discard new candidates that don't make the cut.
    # Tie-break on candidate_id ascending is automatic via string comparison.

    # heap entry: (score, candidate_id, result_dict, candidate_dict)
    heap = []
    n_processed = 0
    n_honeypot = 0

    for candidate in stream_candidates(args.candidates):
        result = composite_score(candidate)
        score = result["score"]
        cid = candidate.get("candidate_id", "")

        if result["honeypot_reasons"]:
            n_honeypot += 1

        entry = (score, cid, result, candidate)
        if len(heap) < args.top:
            heapq.heappush(heap, entry)
        else:
            # Replace the current lowest-scoring entry if this one is better.
            if score > heap[0][0]:
                heapq.heapreplace(heap, entry)

        n_processed += 1
        if n_processed % 10_000 == 0:
            elapsed = time.time() - t0
            print(f"[rank] processed {n_processed:,} candidates ({elapsed:.1f}s)", flush=True)

    print(f"[rank] scored {n_processed:,} candidates; {n_honeypot} honeypots detected", flush=True)

    # Sort: score desc, candidate_id asc for ties (spec requirement).
    top_entries = sorted(heap, key=lambda e: (-e[0], e[1]))

    if len(top_entries) < args.top:
        print(f"[warn] only {len(top_entries)} candidates available (requested {args.top})", file=sys.stderr)

    # Build output rows
    rows = []
    for rank, (_score, cid, result, candidate) in enumerate(top_entries[:args.top], start=1):
        reasoning = build_reasoning(candidate, result)
        rows.append({
            "candidate_id": cid,
            "rank": rank,
            "score": result["score"],
            "reasoning": reasoning,
        })

    write_submission(rows, args.out)
    elapsed = time.time() - t0
    print(f"[rank] wrote {len(rows)} rows to {args.out} in {elapsed:.2f}s", flush=True)

    if args.verbose:
        print("\nTop 20:")
        print(f"{'Rank':>4}  {'Score':>8}  {'ID':<15}  Reasoning")
        print("-" * 90)
        for row in rows[:20]:
            print(f"{row['rank']:>4}  {row['score']:>8.4f}  {row['candidate_id']:<15}  {row['reasoning'][:60]}")


if __name__ == "__main__":
    main()
