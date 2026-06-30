"""Tests for src/candidate_filter.py — pre-scoring gate."""
import pytest

from src.candidate_filter import (
    filter_candidates,
    has_fictional_company,
    is_clean,
    is_consulting_only,
)


class TestIsConsultingOnly:
    def test_all_consulting_returns_true(self, candidate_consulting_only):
        assert is_consulting_only(candidate_consulting_only) is True

    def test_mixed_career_returns_false(self, candidate_ai_engineer):
        assert is_consulting_only(candidate_ai_engineer) is False

    def test_no_career_history_returns_false(self, minimal_candidate):
        assert is_consulting_only(minimal_candidate) is False

    def test_single_non_consulting_company_returns_false(self):
        c = {
            "career_history": [
                {"company": "Infosys", "start_date": "2018-01-01"},
                {"company": "Swiggy", "start_date": "2021-01-01"},
            ]
        }
        assert is_consulting_only(c) is False

    def test_case_insensitive_match(self):
        c = {"career_history": [{"company": "INFOSYS", "start_date": "2018-01-01"}]}
        assert is_consulting_only(c) is True


class TestHasFictionalCompany:
    def test_fictional_company_detected(self, candidate_fictional):
        assert has_fictional_company(candidate_fictional) is True

    def test_real_company_not_flagged(self, candidate_ai_engineer):
        assert has_fictional_company(candidate_ai_engineer) is False

    def test_no_career_history(self, minimal_candidate):
        assert has_fictional_company(minimal_candidate) is False

    def test_mixed_career_with_fictional_flagged(self):
        c = {
            "career_history": [
                {"company": "Google", "start_date": "2019-01-01"},
                {"company": "Hooli", "start_date": "2022-01-01"},
            ]
        }
        assert has_fictional_company(c) is True


class TestIsClean:
    def test_clean_ai_engineer_passes(self, candidate_ai_engineer):
        assert is_clean(candidate_ai_engineer) is True

    def test_consulting_only_fails(self, candidate_consulting_only):
        assert is_clean(candidate_consulting_only) is False

    def test_fictional_company_fails(self, candidate_fictional):
        assert is_clean(candidate_fictional) is False

    def test_minimal_candidate_passes(self, minimal_candidate):
        assert is_clean(minimal_candidate) is True


class TestFilterCandidates:
    def test_passes_clean_candidates(self, candidate_ai_engineer, candidate_hr):
        candidates = [candidate_ai_engineer, candidate_hr]
        result = list(filter_candidates(iter(candidates)))
        assert len(result) == 2

    def test_drops_consulting_only(self, candidate_ai_engineer, candidate_consulting_only):
        candidates = [candidate_ai_engineer, candidate_consulting_only]
        result = list(filter_candidates(iter(candidates)))
        assert len(result) == 1
        assert result[0]["candidate_id"] == candidate_ai_engineer["candidate_id"]

    def test_drops_fictional_company(self, candidate_ai_engineer, candidate_fictional):
        candidates = [candidate_ai_engineer, candidate_fictional]
        result = list(filter_candidates(iter(candidates)))
        assert len(result) == 1

    def test_empty_input_yields_nothing(self):
        assert list(filter_candidates(iter([]))) == []

    def test_all_filtered_out_yields_nothing(self, candidate_consulting_only, candidate_fictional):
        candidates = [candidate_consulting_only, candidate_fictional]
        assert list(filter_candidates(iter(candidates))) == []

    def test_preserves_order(self, candidate_ai_engineer, candidate_hr):
        candidates = [candidate_ai_engineer, candidate_hr]
        result = list(filter_candidates(iter(candidates)))
        assert result[0]["candidate_id"] == candidate_ai_engineer["candidate_id"]
        assert result[1]["candidate_id"] == candidate_hr["candidate_id"]
