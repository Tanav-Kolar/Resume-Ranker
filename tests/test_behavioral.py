"""Tests for src/behavioral.py — availability multiplier."""
import pytest
from datetime import date, timedelta

from src.behavioral import _recency_score, behavioral_multiplier


# ---------------------------------------------------------------------------
# _recency_score
# ---------------------------------------------------------------------------

class TestRecencyScore:
    def _days_ago(self, n):
        return (date.today() - timedelta(days=n)).strftime("%Y-%m-%d")

    def test_active_today_scores_one(self):
        assert _recency_score(self._days_ago(0)) == pytest.approx(1.0)

    def test_active_within_30_days_scores_one(self):
        assert _recency_score(self._days_ago(15)) == pytest.approx(1.0)

    def test_active_at_30_days_scores_one(self):
        assert _recency_score(self._days_ago(30)) == pytest.approx(1.0)

    def test_active_at_180_days_scores_low(self):
        score = _recency_score(self._days_ago(180))
        assert score == pytest.approx(0.10, abs=0.05)

    def test_active_over_180_days_scores_floor(self):
        score = _recency_score(self._days_ago(365))
        assert score == pytest.approx(0.10)

    def test_missing_date_neutral(self):
        assert _recency_score("") == pytest.approx(0.50)
        assert _recency_score(None) == pytest.approx(0.50)

    def test_invalid_date_format_neutral(self):
        assert _recency_score("not-a-date") == pytest.approx(0.50)

    def test_score_between_30_and_180_decays_linearly(self):
        score_90 = _recency_score(self._days_ago(90))
        score_150 = _recency_score(self._days_ago(150))
        assert score_90 > score_150 > 0.10


# ---------------------------------------------------------------------------
# behavioral_multiplier
# ---------------------------------------------------------------------------

class TestBehavioralMultiplier:
    def _days_ago(self, n):
        return (date.today() - timedelta(days=n)).strftime("%Y-%m-%d")

    def test_result_in_valid_range(self, candidate_ai_engineer):
        mult = behavioral_multiplier(candidate_ai_engineer)
        assert 0.5 <= mult <= 1.2

    def test_highly_available_candidate_near_max(self):
        c = {
            "redrob_signals": {
                "last_active_date": self._days_ago(5),
                "open_to_work_flag": True,
                "recruiter_response_rate": 1.0,
            }
        }
        mult = behavioral_multiplier(c)
        assert mult >= 1.1, f"Expected near 1.2, got {mult}"

    def test_unavailable_candidate_near_min(self):
        c = {
            "redrob_signals": {
                "last_active_date": self._days_ago(365),
                "open_to_work_flag": False,
                "recruiter_response_rate": 0.0,
            }
        }
        mult = behavioral_multiplier(c)
        assert mult <= 0.75, f"Expected near 0.5, got {mult}"

    def test_no_signals_returns_neutral(self, minimal_candidate):
        mult = behavioral_multiplier(minimal_candidate)
        assert 0.5 <= mult <= 1.2

    def test_open_to_work_true_beats_false(self):
        base = {"last_active_date": self._days_ago(30), "recruiter_response_rate": 0.5}
        c_open = {"redrob_signals": {**base, "open_to_work_flag": True}}
        c_closed = {"redrob_signals": {**base, "open_to_work_flag": False}}
        assert behavioral_multiplier(c_open) > behavioral_multiplier(c_closed)

    def test_sentinel_response_rate_treated_as_neutral(self):
        c_sentinel = {"redrob_signals": {"recruiter_response_rate": -1}}
        c_none = {"redrob_signals": {"recruiter_response_rate": None}}
        # Both should give same result (neutral 0.5 for response)
        assert behavioral_multiplier(c_sentinel) == behavioral_multiplier(c_none)

    def test_result_rounded_to_4_decimals(self, candidate_ai_engineer):
        mult = behavioral_multiplier(candidate_ai_engineer)
        assert mult == round(mult, 4)
