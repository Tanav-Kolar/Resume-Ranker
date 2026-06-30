"""Tests for src/io_utils.py — streaming reader and CSV writer."""
import csv
import gzip
import json

import pytest

from src.io_utils import stream_candidates, write_submission


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_jsonl(path, records):
    with open(path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")


def _write_jsonl_gz(path, records):
    with gzip.open(path, "wt", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")


_SAMPLE = [
    {"candidate_id": "CAND_0000001", "profile": {"current_title": "ML Engineer"}},
    {"candidate_id": "CAND_0000002", "profile": {"current_title": "Data Scientist"}},
]


# ---------------------------------------------------------------------------
# stream_candidates
# ---------------------------------------------------------------------------

class TestStreamCandidates:
    def test_yields_all_records(self, tmp_path):
        p = tmp_path / "candidates.jsonl"
        _write_jsonl(p, _SAMPLE)
        results = list(stream_candidates(str(p)))
        assert len(results) == 2

    def test_yields_correct_data(self, tmp_path):
        p = tmp_path / "candidates.jsonl"
        _write_jsonl(p, _SAMPLE)
        results = list(stream_candidates(str(p)))
        assert results[0]["candidate_id"] == "CAND_0000001"
        assert results[1]["profile"]["current_title"] == "Data Scientist"

    def test_skips_blank_lines(self, tmp_path):
        p = tmp_path / "candidates.jsonl"
        with open(p, "w") as f:
            f.write(json.dumps(_SAMPLE[0]) + "\n")
            f.write("\n")
            f.write("\n")
            f.write(json.dumps(_SAMPLE[1]) + "\n")
        results = list(stream_candidates(str(p)))
        assert len(results) == 2

    def test_skips_malformed_lines(self, tmp_path):
        p = tmp_path / "candidates.jsonl"
        with open(p, "w") as f:
            f.write(json.dumps(_SAMPLE[0]) + "\n")
            f.write("this is not json\n")
            f.write(json.dumps(_SAMPLE[1]) + "\n")
        results = list(stream_candidates(str(p)))
        assert len(results) == 2  # malformed line skipped

    def test_handles_gzip(self, tmp_path):
        p = tmp_path / "candidates.jsonl.gz"
        _write_jsonl_gz(p, _SAMPLE)
        results = list(stream_candidates(str(p)))
        assert len(results) == 2
        assert results[0]["candidate_id"] == "CAND_0000001"

    def test_empty_file_yields_nothing(self, tmp_path):
        p = tmp_path / "empty.jsonl"
        p.write_text("")
        assert list(stream_candidates(str(p))) == []


# ---------------------------------------------------------------------------
# write_submission
# ---------------------------------------------------------------------------

class TestWriteSubmission:
    def _make_rows(self, n=3):
        return [
            {
                "candidate_id": f"CAND_{i:07d}",
                "rank": i,
                "score": 1.0 - i * 0.1,
                "reasoning": f"Candidate {i} reasoning.",
            }
            for i in range(1, n + 1)
        ]

    def test_creates_file(self, tmp_path):
        out = tmp_path / "submission.csv"
        write_submission(self._make_rows(), str(out))
        assert out.exists()

    def test_header_row(self, tmp_path):
        out = tmp_path / "submission.csv"
        write_submission(self._make_rows(), str(out))
        with open(out, newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader)
        assert header == ["candidate_id", "rank", "score", "reasoning"]

    def test_data_row_count(self, tmp_path):
        out = tmp_path / "submission.csv"
        rows = self._make_rows(5)
        write_submission(rows, str(out))
        with open(out, newline="", encoding="utf-8") as f:
            data_rows = list(csv.reader(f))[1:]  # skip header
        assert len(data_rows) == 5

    def test_score_formatted_to_6_decimals(self, tmp_path):
        out = tmp_path / "submission.csv"
        write_submission([{"candidate_id": "CAND_0000001", "rank": 1, "score": 0.123456789, "reasoning": "x"}], str(out))
        with open(out, newline="", encoding="utf-8") as f:
            rows = list(csv.reader(f))
        score_str = rows[1][2]
        assert len(score_str.split(".")[1]) == 6

    def test_reasoning_newlines_collapsed(self, tmp_path):
        out = tmp_path / "submission.csv"
        write_submission([{"candidate_id": "CAND_0000001", "rank": 1, "score": 0.5, "reasoning": "line1\nline2"}], str(out))
        with open(out, newline="", encoding="utf-8") as f:
            rows = list(csv.reader(f))
        assert "\n" not in rows[1][3]
