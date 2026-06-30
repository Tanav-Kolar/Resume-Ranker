"""
Compare two submission CSVs to see how rankings shifted.

Usage:
    python diff_submissions.py <old.csv> <new.csv>
    python diff_submissions.py submissions/csv/submission_A.csv submissions/csv/submission_B.csv

Can also be imported:
    from diff_submissions import diff_to_string
    text = diff_to_string(old_path, new_path)
"""

import argparse
import csv
import io
from pathlib import Path


def _load(path: str) -> dict:
    """Return {candidate_id: {rank, score, reasoning}} for every row."""
    rows = {}
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows[row["candidate_id"]] = {
                "rank": int(row["rank"]),
                "score": float(row["score"]),
                "reasoning": row["reasoning"],
            }
    return rows


def diff_to_string(old_path: str, new_path: str) -> str:
    """Return the full diff report as a string."""
    old = _load(old_path)
    new = _load(new_path)

    old_ids = set(old)
    new_ids = set(new)

    entered   = new_ids - old_ids
    dropped   = old_ids - new_ids
    common    = old_ids & new_ids

    moved_up   = [(cid, old[cid], new[cid]) for cid in common if new[cid]["rank"] < old[cid]["rank"]]
    moved_down = [(cid, old[cid], new[cid]) for cid in common if new[cid]["rank"] > old[cid]["rank"]]
    unchanged  = [cid for cid in common if new[cid]["rank"] == old[cid]["rank"]]

    moved_up.sort(key=lambda x: old[x[0]]["rank"] - new[x[0]]["rank"], reverse=True)
    moved_down.sort(key=lambda x: new[x[0]]["rank"] - old[x[0]]["rank"], reverse=True)

    buf = io.StringIO()
    w = lambda line="": buf.write(line + "\n")

    w(f"{'='*70}")
    w(f"  Submission Diff")
    w(f"  Old: {old_path}")
    w(f"  New: {new_path}")
    w(f"{'='*70}")

    if entered:
        w(f"\n{'─'*70}")
        w(f"  NEW ENTRIES ({len(entered)} candidates entered the top {len(new)})")
        w(f"{'─'*70}")
        for cid in sorted(entered, key=lambda c: new[c]["rank"]):
            r = new[cid]
            w(f"  {cid}  entered at rank {r['rank']:>3}  score {r['score']:.6f}")
    else:
        w("\n  No new entries.")

    if dropped:
        w(f"\n{'─'*70}")
        w(f"  DROPPED OUT ({len(dropped)} candidates left the top {len(old)})")
        w(f"{'─'*70}")
        for cid in sorted(dropped, key=lambda c: old[c]["rank"]):
            r = old[cid]
            w(f"  {cid}  was rank {r['rank']:>3}  score {r['score']:.6f}")
    else:
        w("\n  No candidates dropped out.")

    if moved_up:
        w(f"\n{'─'*70}")
        w(f"  MOVED UP ({len(moved_up)} candidates improved rank)")
        w(f"{'─'*70}")
        w(f"  {'ID':<15}  {'Old':>5}  {'New':>5}  {'Δrank':>6}  {'Δscore':>10}")
        for cid, o, n in moved_up:
            w(f"  {cid:<15}  {o['rank']:>5}  {n['rank']:>5}  {o['rank']-n['rank']:>+6}  {n['score']-o['score']:>+10.6f}")

    if moved_down:
        w(f"\n{'─'*70}")
        w(f"  MOVED DOWN ({len(moved_down)} candidates fell in rank)")
        w(f"{'─'*70}")
        w(f"  {'ID':<15}  {'Old':>5}  {'New':>5}  {'Δrank':>6}  {'Δscore':>10}")
        for cid, o, n in moved_down:
            w(f"  {cid:<15}  {o['rank']:>5}  {n['rank']:>5}  {o['rank']-n['rank']:>+6}  {n['score']-o['score']:>+10.6f}")

    score_changed_stable = [
        cid for cid in unchanged
        if abs(new[cid]["score"] - old[cid]["score"]) > 1e-9
    ]
    if score_changed_stable:
        w(f"\n{'─'*70}")
        w(f"  SAME RANK, SCORE CHANGED ({len(score_changed_stable)} candidates)")
        w(f"{'─'*70}")
        w(f"  {'ID':<15}  {'Rank':>5}  {'Δscore':>10}")
        for cid in sorted(score_changed_stable, key=lambda c: new[c]["rank"]):
            w(f"  {cid:<15}  {new[cid]['rank']:>5}  {new[cid]['score']-old[cid]['score']:>+10.6f}")

    old_scores = [r["score"] for r in old.values()]
    new_scores = [r["score"] for r in new.values()]
    w(f"\n{'─'*70}")
    w(f"  SUMMARY")
    w(f"{'─'*70}")
    w(f"  Unchanged rank : {len(unchanged):>4}")
    w(f"  Moved up       : {len(moved_up):>4}")
    w(f"  Moved down     : {len(moved_down):>4}")
    w(f"  Entered top-N  : {len(entered):>4}")
    w(f"  Dropped out    : {len(dropped):>4}")
    w(f"  Score range old: {min(old_scores):.6f} – {max(old_scores):.6f}")
    w(f"  Score range new: {min(new_scores):.6f} – {max(new_scores):.6f}")
    w(f"  Avg score  old : {sum(old_scores)/len(old_scores):.6f}")
    w(f"  Avg score  new : {sum(new_scores)/len(new_scores):.6f}")
    w(f"{'='*70}")

    return buf.getvalue()


def main() -> None:
    p = argparse.ArgumentParser(description="Diff two submission CSVs.")
    p.add_argument("old", help="Older submission CSV")
    p.add_argument("new", help="Newer submission CSV")
    args = p.parse_args()

    for path in (args.old, args.new):
        if not Path(path).exists():
            p.error(f"File not found: {path}")

    print(diff_to_string(args.old, args.new))


if __name__ == "__main__":
    main()
