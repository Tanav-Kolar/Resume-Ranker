"""
Streaming JSONL reader (handles .gz transparently) and spec-safe CSV writer.
"""
import csv
import gzip
import json
import logging
from pathlib import Path
from typing import Iterator

logger = logging.getLogger("pipeline")


def stream_candidates(path: str) -> Iterator[dict]:
    """Yield one candidate dict per line; never loads the full file into memory."""
    p = Path(path)
    is_gz = p.suffix == ".gz"
    opener = gzip.open if is_gz else open
    mode = "rt" if is_gz else "r"
    fmt = "gzip" if is_gz else "plain JSONL"
    logger.info("Opening %s (%s) for streaming", p, fmt)
    with opener(p, mode, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as exc:
                logger.warning("Skipping malformed line: %s", exc)


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
