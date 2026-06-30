"""Tests for src/reasoning.py — deterministic reasoning string generator."""
import pytest

from src.reasoning import build_reasoning
from src.score import composite_score


def _result(candidate, **kwargs):
    """Run composite_score and optionally override keys for isolation."""
    r = composite_score(candidate)
    r.update(kwargs)
    return r


class TestBuildReasoning:
    # --- Return type and format ---

    def test_returns_string(self, candidate_ai_engineer):
        result = _result(candidate_ai_engineer)
        assert isinstance(build_reasoning(candidate_ai_engineer, result), str)

    def test_no_embedded_newlines(self, candidate_ai_engineer):
        result = _result(candidate_ai_engineer)
        reasoning = build_reasoning(candidate_ai_engineer, result)
        assert "\n" not in reasoning
        assert "\r" not in reasoning

    def test_non_empty_for_clean_candidate(self, candidate_ai_engineer):
        result = _result(candidate_ai_engineer)
        assert len(build_reasoning(candidate_ai_engineer, result)) > 0

    # --- Honeypot path ---

    def test_honeypot_mentions_excluded(self, candidate_honeypot):
        result = _result(candidate_honeypot)
        reasoning = build_reasoning(candidate_honeypot, result)
        assert "excluded from shortlist" in reasoning

    def test_honeypot_reasoning_contains_reason(self, candidate_honeypot):
        result = _result(candidate_honeypot)
        reasoning = build_reasoning(candidate_honeypot, result)
        assert "career tenure mismatch" in reasoning or "inconsistent profile" in reasoning

    # --- Normal path ---

    def test_normal_reasoning_contains_title(self, candidate_ai_engineer):
        result = _result(candidate_ai_engineer)
        reasoning = build_reasoning(candidate_ai_engineer, result)
        assert "ML Engineer" in reasoning

    def test_normal_reasoning_contains_yoe(self, candidate_ai_engineer):
        result = _result(candidate_ai_engineer)
        reasoning = build_reasoning(candidate_ai_engineer, result)
        assert "7" in reasoning  # 7 years of experience

    def test_normal_reasoning_contains_location(self, candidate_ai_engineer):
        result = _result(candidate_ai_engineer)
        reasoning = build_reasoning(candidate_ai_engineer, result)
        assert "Bangalore" in reasoning

    def test_strong_title_produces_strong_fit_mention(self):
        c = {
            "candidate_id": "CAND_0000099",
            "profile": {"current_title": "ML Engineer", "years_of_experience": 7, "location": "Bangalore"},
            "career_history": [],
            "skills": [],
            "education": [],
            "redrob_signals": {},
        }
        result = {
            "components": {"title": 1.0},
            "honeypot_reasons": [],
        }
        reasoning = build_reasoning(c, result)
        assert "strong role fit" in reasoning

    def test_weak_title_produces_weak_fit_mention(self, candidate_hr):
        result = _result(candidate_hr)
        reasoning = build_reasoning(candidate_hr, result)
        assert "weak role fit" in reasoning

    def test_no_newlines_in_honeypot_reasoning(self, candidate_honeypot):
        result = _result(candidate_honeypot)
        reasoning = build_reasoning(candidate_honeypot, result)
        assert "\n" not in reasoning

    def test_minimal_candidate_does_not_crash(self, minimal_candidate):
        result = {
            "components": {"title": 0.3},
            "honeypot_reasons": [],
        }
        reasoning = build_reasoning(minimal_candidate, result)
        assert isinstance(reasoning, str)
