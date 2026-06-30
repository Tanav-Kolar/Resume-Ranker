"""End-to-end integration test — exercises the full pipeline on fixture data."""
import csv
import heapq
import json
from pathlib import Path

import pytest

from src.candidate_filter import filter_candidates
from src.io_utils import stream_candidates, write_submission
from src.reasoning import build_reasoning
from src.score import HONEYPOT_SENTINEL, composite_score


# ---------------------------------------------------------------------------
# Fixture data — written to a temp JSONL file for each test
# ---------------------------------------------------------------------------

_CANDIDATES = [
    {
        "candidate_id": "CAND_0000001",
        "profile": {
            "current_title": "ML Engineer",
            "years_of_experience": 7,
            "location": "Bangalore",
            "country": "India",
        },
        "career_history": [
            {"company": "Swiggy", "title": "ML Engineer", "start_date": "2019-01-01",
             "end_date": "2024-01-01", "duration_months": 60}
        ],
        "skills": [
            {"name": "machine learning", "proficiency": "expert", "duration_months": 72},
            {"name": "pytorch", "proficiency": "advanced", "duration_months": 48},
            {"name": "python", "proficiency": "expert", "duration_months": 84},
        ],
        "education": [{"institution": "IIT Bombay", "start_year": 2012, "end_year": 2016}],
        "redrob_signals": {
            "last_active_date": "2026-06-20", "open_to_work_flag": True,
            "recruiter_response_rate": 0.8, "willing_to_relocate": False,
            "skill_assessment_scores": {}
        },
    },
    {
        "candidate_id": "CAND_0000002",
        "profile": {
            "current_title": "HR Manager",
            "years_of_experience": 5,
            "location": "Mumbai",
            "country": "India",
        },
        "career_history": [
            {"company": "Corp Ltd", "title": "HR Manager", "start_date": "2019-01-01",
             "end_date": "2024-01-01", "duration_months": 60}
        ],
        "skills": [],
        "education": [],
        "redrob_signals": {"open_to_work_flag": None, "recruiter_response_rate": -1,
                           "willing_to_relocate": False, "skill_assessment_scores": {}},
    },
    {
        "candidate_id": "CAND_0000003",
        "profile": {
            "current_title": "Software Engineer",
            "years_of_experience": 4,
            "location": "Chennai",
            "country": "India",
        },
        "career_history": [
            {"company": "Infosys", "title": "SE", "start_date": "2020-01-01", "duration_months": 48},
            {"company": "TCS", "title": "SE", "start_date": "2018-01-01", "duration_months": 24},
        ],
        "skills": [],
        "education": [],
        "redrob_signals": {"skill_assessment_scores": {}},
    },
    # Honeypot: career tenure far exceeds YoE
    {
        "candidate_id": "CAND_0000004",
        "profile": {
            "current_title": "ML Engineer",
            "years_of_experience": 3,
            "location": "Pune",
            "country": "India",
        },
        "career_history": [
            {"company": "TechCo", "title": "ML Engineer", "start_date": "2010-01-01",
             "end_date": "2020-01-01", "duration_months": 144}
        ],
        "skills": [],
        "education": [],
        "redrob_signals": {"skill_assessment_scores": {}},
    },
]


@pytest.fixture
def candidates_jsonl(tmp_path):
    p = tmp_path / "candidates.jsonl"
    with open(p, "w", encoding="utf-8") as f:
        for c in _CANDIDATES:
            f.write(json.dumps(c) + "\n")
    return str(p)


@pytest.fixture
def submission_csv(tmp_path):
    return str(tmp_path / "submission.csv")


# ---------------------------------------------------------------------------
# Pipeline runner (mirrors rank.py logic without argparse)
# ---------------------------------------------------------------------------

def _run_pipeline(jsonl_path: str, csv_path: str, top: int = 100):
    heap = []
    n_streamed = 0
    n_passed_filter = 0
    n_honeypot = 0

    def _counted():
        nonlocal n_streamed
        for c in stream_candidates(jsonl_path):
            n_streamed += 1
            yield c

    for candidate in filter_candidates(_counted()):
        n_passed_filter += 1
        result = composite_score(candidate)
        if result["honeypot_reasons"]:
            n_honeypot += 1
        score = result["score"]
        cid = candidate.get("candidate_id", "")
        entry = (score, cid, result, candidate)
        if len(heap) < top:
            heapq.heappush(heap, entry)
        elif score > heap[0][0]:
            heapq.heapreplace(heap, entry)

    top_entries = sorted(heap, key=lambda e: (-e[0], e[1]))
    rows = []
    for rank, (_score, cid, result, candidate) in enumerate(top_entries[:top], start=1):
        reasoning = build_reasoning(candidate, result)
        rows.append({"candidate_id": cid, "rank": rank, "score": result["score"], "reasoning": reasoning})

    write_submission(rows, csv_path)
    return {
        "n_streamed": n_streamed,
        "n_passed_filter": n_passed_filter,
        "n_honeypot": n_honeypot,
        "rows": rows,
        "top_entries": top_entries,
    }


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------

class TestPipelineE2E:
    def test_pipeline_runs_without_error(self, candidates_jsonl, submission_csv):
        _run_pipeline(candidates_jsonl, submission_csv)

    def test_output_csv_created(self, candidates_jsonl, submission_csv):
        _run_pipeline(candidates_jsonl, submission_csv)
        assert Path(submission_csv).exists()

    def test_consulting_only_filtered_out(self, candidates_jsonl, submission_csv):
        stats = _run_pipeline(candidates_jsonl, submission_csv)
        # CAND_0000003 is consulting-only and should not appear in output
        output_ids = {r["candidate_id"] for r in stats["rows"]}
        assert "CAND_0000003" not in output_ids

    def test_honeypot_not_in_top_results(self, candidates_jsonl, submission_csv):
        # Use top=2 so the honeypot (score -1.0) cannot displace the two real candidates.
        stats = _run_pipeline(candidates_jsonl, submission_csv, top=2)
        output_ids = {r["candidate_id"] for r in stats["rows"]}
        assert "CAND_0000004" not in output_ids

    def test_ai_engineer_ranks_above_hr(self, candidates_jsonl, submission_csv):
        stats = _run_pipeline(candidates_jsonl, submission_csv)
        rows_by_id = {r["candidate_id"]: r for r in stats["rows"]}
        assert "CAND_0000001" in rows_by_id and "CAND_0000002" in rows_by_id
        assert rows_by_id["CAND_0000001"]["rank"] < rows_by_id["CAND_0000002"]["rank"]

    def test_scores_non_increasing_by_rank(self, candidates_jsonl, submission_csv):
        _run_pipeline(candidates_jsonl, submission_csv)
        with open(submission_csv, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        scores = [float(r["score"]) for r in rows]
        for i in range(len(scores) - 1):
            assert scores[i] >= scores[i + 1], (
                f"Score not non-increasing at rank {i+1}: {scores[i]} < {scores[i+1]}"
            )

    def test_csv_header_correct(self, candidates_jsonl, submission_csv):
        _run_pipeline(candidates_jsonl, submission_csv)
        with open(submission_csv, newline="", encoding="utf-8") as f:
            header = next(csv.reader(f))
        assert header == ["candidate_id", "rank", "score", "reasoning"]

    def test_ranks_are_sequential_from_one(self, candidates_jsonl, submission_csv):
        _run_pipeline(candidates_jsonl, submission_csv)
        with open(submission_csv, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        ranks = [int(r["rank"]) for r in rows]
        assert ranks == list(range(1, len(ranks) + 1))

    def test_filter_stats_make_sense(self, candidates_jsonl, submission_csv):
        stats = _run_pipeline(candidates_jsonl, submission_csv)
        assert stats["n_streamed"] == 4  # total input
        assert stats["n_passed_filter"] == 3  # consulting-only dropped
        assert stats["n_streamed"] >= stats["n_passed_filter"]

    def test_honeypot_count_tracked(self, candidates_jsonl, submission_csv):
        stats = _run_pipeline(candidates_jsonl, submission_csv)
        assert stats["n_honeypot"] >= 1  # CAND_0000004 is a honeypot

    def test_reasoning_has_no_newlines(self, candidates_jsonl, submission_csv):
        stats = _run_pipeline(candidates_jsonl, submission_csv)
        for row in stats["rows"]:
            assert "\n" not in row["reasoning"]

    def test_deterministic_across_runs(self, candidates_jsonl, tmp_path):
        out1 = str(tmp_path / "run1.csv")
        out2 = str(tmp_path / "run2.csv")
        r1 = _run_pipeline(candidates_jsonl, out1)
        r2 = _run_pipeline(candidates_jsonl, out2)
        assert [(r["candidate_id"], r["rank"]) for r in r1["rows"]] == \
               [(r["candidate_id"], r["rank"]) for r in r2["rows"]]
