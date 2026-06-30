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
import time
from pathlib import Path

from src.io_utils import stream_candidates, write_submission
from src.score import composite_score, HONEYPOT_SENTINEL
from src.reasoning import build_reasoning
from src.candidate_filter import filter_candidates
from src.log_config import setup_logger


def _check(logger, name: str, ok: bool, detail: str = "") -> None:
    """Log a named checkpoint assertion as PASS or FAIL."""
    suffix = f" — {detail}" if detail else ""
    if ok:
        logger.info("  [CHECK PASS] %s%s", name, suffix)
    else:
        logger.warning("  [CHECK FAIL] %s%s", name, suffix)


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
    logger = setup_logger()
    t0 = time.time()

    logger.info("Reading candidates from %s ...", args.candidates)

    # Min-heap keyed by (score, candidate_id).
    # heap[0] is always the lowest-scoring entry in the current top-N window,
    # so we can efficiently discard new candidates that don't make the cut.
    # Tie-break on candidate_id ascending is automatic via string comparison.

    # heap entry: (score, candidate_id, result_dict, candidate_dict)
    heap = []
    n_processed = 0
    n_honeypot = 0
    n_streamed = 0

    def _counted_stream():
        nonlocal n_streamed
        for c in stream_candidates(args.candidates):
            n_streamed += 1
            yield c

    n_passed_filter = 0
    for candidate in filter_candidates(_counted_stream()):
        n_passed_filter += 1
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
            logger.info("Processed %d candidates (%.1fs)", n_processed, elapsed)

    n_filtered_out = n_streamed - n_passed_filter
    logger.info(
        "candidate_filter: %d removed (consulting-only or fictional); %d passed",
        n_filtered_out, n_passed_filter,
    )
    _check(logger, "candidate_filter.no_candidates_added",
           n_streamed >= n_passed_filter,
           f"streamed={n_streamed:,}, passed={n_passed_filter:,}")

    logger.info("Scored %d candidates; %d honeypots detected", n_processed, n_honeypot)
    _check(logger, "scoring.honeypot_count_plausible",
           0 <= n_honeypot <= n_processed,
           f"honeypots={n_honeypot}, processed={n_processed:,}")
    heap_scores = [e[0] for e in heap]
    _check(logger, "scoring.all_scores_in_bounds",
           all(-1.0 <= s <= 1.5 for s in heap_scores),
           f"{len(heap_scores)} heap entries checked")

    # Sort: score desc, candidate_id asc for ties (spec requirement).
    top_entries = sorted(heap, key=lambda e: (-e[0], e[1]))

    if len(top_entries) < args.top:
        logger.warning("Only %d candidates available (requested %d)", len(top_entries), args.top)

    _check(logger, "ranking.size_within_requested",
           len(top_entries) <= args.top,
           f"have={len(top_entries)}, requested={args.top}")
    if len(top_entries) > 1:
        sorted_scores = [e[0] for e in top_entries]
        non_increasing = all(sorted_scores[i] >= sorted_scores[i + 1]
                             for i in range(len(sorted_scores) - 1))
        _check(logger, "ranking.scores_non_increasing", non_increasing)

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
    logger.info("Wrote %d rows to %s in %.2fs", len(rows), args.out, elapsed)
    _check(logger, "output.file_exists",
           Path(args.out).exists(), args.out)
    _check(logger, "output.row_count_matches",
           len(rows) == min(len(top_entries), args.top),
           f"rows={len(rows)}")

    if args.verbose:
        print("\nTop 20:")
        print(f"{'Rank':>4}  {'Score':>8}  {'ID':<15}  Reasoning")
        print("-" * 90)
        for row in rows[:20]:
            print(f"{row['rank']:>4}  {row['score']:>8.4f}  {row['candidate_id']:<15}  {row['reasoning'][:60]}")


if __name__ == "__main__":
    main()
