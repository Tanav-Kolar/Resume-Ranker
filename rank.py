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
import json
import shutil
import time
from pathlib import Path

from src.io_utils import stream_candidates, write_submission
from src.score import composite_score, HONEYPOT_SENTINEL
from src.reasoning import build_reasoning
from src.candidate_filter import filter_candidates
from src.log_config import setup_logger
from diff_submissions import diff_to_string


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
    p.add_argument(
        "--labels",
        default="evals/labels.csv",
        help="Eval labels CSV; auto-eval runs against it after ranking",
    )
    p.add_argument(
        "--skip-eval",
        action="store_true",
        help="Skip the automatic eval step",
    )
    p.add_argument(
        "--semantic-scores",
        default="artifacts",
        metavar="DIR",
        help="Directory containing query_vectors.npz and candidate_chunks.npz (default: artifacts)",
    )
    p.add_argument(
        "--no-semantic",
        action="store_true",
        help="Disable semantic scoring even if artifacts are present",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    logger = setup_logger()
    t0 = time.time()

    logger.info("Reading candidates from %s ...", args.candidates)

    sem_scores: dict[str, float] = {}
    artifacts_dir = Path(args.semantic_scores)
    query_path = artifacts_dir / "query_vectors.npz"
    chunks_path = artifacts_dir / "candidate_chunks.npz"
    if not args.no_semantic and query_path.exists() and chunks_path.exists():
        from src.semantic import load_semantic_scores
        sem_scores = load_semantic_scores(str(query_path), str(chunks_path))
        logger.info("Semantic active: %d candidates scored", len(sem_scores))
    else:
        logger.info("Semantic inactive (artifacts missing or --no-semantic) — structured only")

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
        cid = candidate.get("candidate_id", "")
        result = composite_score(candidate, semantic=sem_scores.get(cid))
        score = result["score"]

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

    csv_dir   = Path("submissions") / "csv"
    diffs_dir = Path("submissions") / "diffs"
    csv_dir.mkdir(parents=True, exist_ok=True)
    diffs_dir.mkdir(parents=True, exist_ok=True)

    ts = time.strftime("%Y%m%dT%H%M%S")
    archive = csv_dir / f"submission_{ts}.csv"
    shutil.copy2(args.out, archive)
    logger.info("Archived to %s", archive)

    # Auto-diff against the immediately preceding submission.
    prev_csvs = sorted(csv_dir.glob("submission_*.csv"))
    # prev_csvs now includes the archive we just wrote; predecessor is one before it.
    if len(prev_csvs) >= 2:
        predecessor = prev_csvs[-2]
        logger.info("Diffing against predecessor %s ...", predecessor.name)
        diff_text = diff_to_string(str(predecessor), str(archive))
        diff_file = diffs_dir / f"diff_{ts}.txt"
        diff_file.write_text(diff_text, encoding="utf-8")
        logger.info("Diff saved to %s", diff_file)
    else:
        logger.info("No predecessor found — skipping auto-diff (this is the first submission)")

    # Auto-eval the fresh submission against the local label set (proxy leaderboard).
    if not args.skip_eval:
        labels_path = Path(args.labels)
        if labels_path.exists():
            try:
                from evals.evaluate import evaluate
                m = evaluate(args.out, str(labels_path))
                m["submission"] = archive.name  # tie metrics to the archived snapshot, not the generic --out path
                logger.info(
                    "EVAL composite=%.4f (NDCG@10=%.4f NDCG@50=%.4f MAP=%.4f P@10=%.4f)",
                    m["composite"], m["NDCG@10"], m["NDCG@50"], m["MAP"], m["P@10"],
                )
                cov, t0z = m["labeled_coverage"], m["tier0_in_top"]
                logger.info(
                    "EVAL coverage top10/50/100=%d/%d/%d; tier0_in_top100=%d",
                    cov["top10"], cov["top50"], cov["top100"], t0z["top100"],
                )
                # Compare against the stored baseline, if present.
                base_path = Path("evals") / "baseline.json"
                if base_path.exists():
                    base = json.loads(base_path.read_text(encoding="utf-8"))
                    delta = m["composite"] - base.get("composite", 0.0)
                    logger.info("EVAL delta vs baseline: %+.4f (baseline=%.4f)",
                                delta, base.get("composite", 0.0))
                # Archive a timestamped eval result next to the submission archive.
                runs_dir = Path("evals") / "runs"
                runs_dir.mkdir(parents=True, exist_ok=True)
                eval_file = runs_dir / f"eval_{ts}.json"
                eval_file.write_text(json.dumps(m, indent=2), encoding="utf-8")
                logger.info("Eval saved to %s", eval_file)
                _check(logger, "eval.no_honeypots_in_top100",
                       t0z["top100"] == 0, f"tier0_in_top100={t0z['top100']}")
            except Exception as e:  # never let eval crash the pipeline
                logger.warning("EVAL step failed: %s", e)
        else:
            logger.info("EVAL skipped — labels not found at %s", labels_path)

    if args.verbose:
        print("\nTop 20:")
        print(f"{'Rank':>4}  {'Score':>8}  {'ID':<15}  Reasoning")
        print("-" * 90)
        for row in rows[:20]:
            print(f"{row['rank']:>4}  {row['score']:>8.4f}  {row['candidate_id']:<15}  {row['reasoning'][:60]}")

    # Total end-to-end wall-clock: streaming + filter + scoring + ranking + write
    # + archive + diff + eval. This is the number that must stay under the 5-min budget.
    total_elapsed = time.time() - t0
    logger.info("TOTAL end-to-end pipeline time: %.2fs", total_elapsed)


if __name__ == "__main__":
    main()
