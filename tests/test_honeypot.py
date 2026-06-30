"""Tests for src/honeypot.py — consistency veto filter."""
import pytest
from datetime import date, timedelta

from src.honeypot import _parse_date, _total_career_months, check_honeypot


# ---------------------------------------------------------------------------
# _parse_date
# ---------------------------------------------------------------------------

class TestParseDate:
    def test_full_date(self):
        assert _parse_date("2022-06-15") == date(2022, 6, 15)

    def test_year_month(self):
        result = _parse_date("2022-06")
        assert result is not None
        assert result.year == 2022 and result.month == 6

    def test_year_only(self):
        result = _parse_date("2022")
        assert result is not None
        assert result.year == 2022

    def test_none_returns_none(self):
        assert _parse_date(None) is None

    def test_empty_string_returns_none(self):
        assert _parse_date("") is None

    def test_invalid_format_returns_none(self):
        assert _parse_date("not-a-date") is None


# ---------------------------------------------------------------------------
# _total_career_months
# ---------------------------------------------------------------------------

class TestTotalCareerMonths:
    def test_sums_all_entries(self):
        c = {
            "career_history": [
                {"duration_months": 24},
                {"duration_months": 36},
            ]
        }
        assert _total_career_months(c) == 60

    def test_empty_career_returns_zero(self, minimal_candidate):
        assert _total_career_months(minimal_candidate) == 0

    def test_handles_missing_duration(self):
        c = {"career_history": [{"company": "X"}, {"duration_months": 12}]}
        assert _total_career_months(c) == 12

    def test_handles_none_duration(self):
        c = {"career_history": [{"duration_months": None}, {"duration_months": 12}]}
        assert _total_career_months(c) == 12


# ---------------------------------------------------------------------------
# check_honeypot — clean candidates
# ---------------------------------------------------------------------------

class TestCheckHoneypotClean:
    def test_clean_ai_engineer_passes(self, candidate_ai_engineer):
        assert check_honeypot(candidate_ai_engineer) == []

    def test_clean_hr_candidate_passes(self, candidate_hr):
        assert check_honeypot(candidate_hr) == []

    def test_minimal_candidate_passes(self, minimal_candidate):
        assert check_honeypot(minimal_candidate) == []


# ---------------------------------------------------------------------------
# check_honeypot — career tenure mismatch
# ---------------------------------------------------------------------------

class TestCareerTenureMismatch:
    def test_tenure_exceeds_yoe_flagged(self, candidate_honeypot):
        reasons = check_honeypot(candidate_honeypot)
        assert any("career_tenure_mismatch" in r for r in reasons)

    def test_tenure_within_threshold_not_flagged(self):
        c = {
            "profile": {"years_of_experience": 10},
            "career_history": [{"duration_months": 100}],  # 100 < 10*12*1.6 = 192
            "skills": [],
            "education": [],
        }
        reasons = check_honeypot(c)
        assert not any("career_tenure_mismatch" in r for r in reasons)

    def test_zero_yoe_skips_tenure_check(self):
        c = {
            "profile": {"years_of_experience": 0},
            "career_history": [{"duration_months": 999}],
            "skills": [],
            "education": [],
        }
        reasons = check_honeypot(c)
        assert not any("career_tenure_mismatch" in r for r in reasons)


# ---------------------------------------------------------------------------
# check_honeypot — zero-duration advanced skills
# ---------------------------------------------------------------------------

class TestZeroDurationAdvancedSkills:
    def test_four_zero_dur_advanced_flagged(self, candidate_zero_dur_honeypot):
        reasons = check_honeypot(candidate_zero_dur_honeypot)
        assert any("zero_duration_advanced_skills" in r for r in reasons)

    def test_three_zero_dur_advanced_not_flagged(self):
        c = {
            "profile": {"years_of_experience": 3},
            "career_history": [],
            "skills": [
                {"name": "pytorch", "proficiency": "expert", "duration_months": 0},
                {"name": "tensorflow", "proficiency": "expert", "duration_months": 0},
                {"name": "machine learning", "proficiency": "advanced", "duration_months": 0},
            ],
            "education": [],
        }
        reasons = check_honeypot(c)
        assert not any("zero_duration_advanced_skills" in r for r in reasons)

    def test_beginner_zero_duration_not_flagged(self):
        c = {
            "profile": {"years_of_experience": 2},
            "career_history": [],
            "skills": [
                {"name": f"skill{i}", "proficiency": "beginner", "duration_months": 0}
                for i in range(6)
            ],
            "education": [],
        }
        reasons = check_honeypot(c)
        assert not any("zero_duration_advanced_skills" in r for r in reasons)


# ---------------------------------------------------------------------------
# check_honeypot — impossible job dates
# ---------------------------------------------------------------------------

class TestImpossibleJobDates:
    def test_end_before_start_flagged(self):
        c = {
            "profile": {"years_of_experience": 3},
            "career_history": [
                {
                    "title": "Engineer",
                    "start_date": "2022-06-01",
                    "end_date": "2021-01-01",  # end before start
                    "duration_months": 12,
                }
            ],
            "skills": [],
            "education": [],
        }
        reasons = check_honeypot(c)
        assert any("impossible_job_dates" in r for r in reasons)

    def test_future_start_date_flagged(self):
        future = (date.today() + timedelta(days=365)).strftime("%Y-%m-%d")
        c = {
            "profile": {"years_of_experience": 3},
            "career_history": [
                {"title": "Engineer", "start_date": future, "duration_months": 12}
            ],
            "skills": [],
            "education": [],
        }
        reasons = check_honeypot(c)
        assert any("future_job_start" in r for r in reasons)

    def test_valid_dates_not_flagged(self, candidate_ai_engineer):
        reasons = check_honeypot(candidate_ai_engineer)
        assert not any("impossible_job_dates" in r for r in reasons)
        assert not any("future_job_start" in r for r in reasons)


# ---------------------------------------------------------------------------
# check_honeypot — impossible education dates
# ---------------------------------------------------------------------------

class TestImpossibleEducationDates:
    def test_end_before_start_year_flagged(self):
        c = {
            "profile": {"years_of_experience": 5},
            "career_history": [],
            "skills": [],
            "education": [
                {"institution": "MIT", "start_year": 2015, "end_year": 2012}
            ],
        }
        reasons = check_honeypot(c)
        assert any("impossible_edu_dates" in r for r in reasons)

    def test_valid_edu_dates_not_flagged(self, candidate_ai_engineer):
        reasons = check_honeypot(candidate_ai_engineer)
        assert not any("impossible_edu_dates" in r for r in reasons)
