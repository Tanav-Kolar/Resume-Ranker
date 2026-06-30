"""
Streaming JSONL reader (handles .gz transparently) and spec-safe CSV writer.
"""
import csv
import gzip
import json
import sys
from pathlib import Path
from typing import Iterator


def stream_candidates(path: str) -> Iterator[dict]:
    """Yield one candidate dict per line; never loads the full file into memory."""
    p = Path(path)
    opener = gzip.open if p.suffix == ".gz" else open
    mode = "rt" if p.suffix == ".gz" else "r"
    with opener(p, mode, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as exc:
                print(f"[warn] skipping malformed line: {exc}", file=sys.stderr)


def write_submission(rows: list, out_path: str) -> None:
    """Write a spec-compliant CSV to out_path.

    rows: list of dicts with keys candidate_id, rank, score, reasoning.
    Rows must already be sorted correctly and ranked 1-100 by the caller.
    """
    p = Path(out_path)
    with p.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh, quoting=csv.QUOTE_MINIMAL)
        writer.writerow(["candidate_id", "rank", "score", "reasoning"])
        for row in rows:
            # Collapse newlines so reasoning stays single-line.
            reasoning = row["reasoning"].replace("\n", " ").replace("\r", " ")
            writer.writerow([
                row["candidate_id"],
                row["rank"],
                f"{row['score']:.6f}",
                reasoning,
            ])
