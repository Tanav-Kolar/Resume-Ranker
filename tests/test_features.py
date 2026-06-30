"""Tests for src/features.py — rule-based scoring components."""
import pytest

from src.features import experience_fit, location_fit, skill_relevance, title_fit


# ---------------------------------------------------------------------------
# title_fit
# ---------------------------------------------------------------------------

class TestTitleFit:
    def test_high_tier_title_scores_near_one(self, candidate_ai_engineer):
        score = title_fit(candidate_ai_engineer)
        assert score >= 0.90, f"Expected >= 0.90, got {score}"

    def test_low_tier_title_scores_near_zero(self, candidate_hr):
        score = title_fit(candidate_hr)
        assert score <= 0.20, f"Expected <= 0.20, got {score}"

    def test_medium_tier_title_mid_range(self):
        c = {
            "profile": {"current_title": "Software Engineer"},
            "career_history": [],
        }
        score = title_fit(c)
        assert 0.30 <= score <= 0.70, f"Expected 0.30-0.70, got {score}"

    def test_empty_title_uses_unknown_tier(self, minimal_candidate):
        score = title_fit(minimal_candidate)
        # No title, no career history → current=UNKNOWN(0.30), past=0.0
        # blended = 0.70*0.30 + 0.30*0.0 = 0.21
        assert score == pytest.approx(0.21, abs=0.01)

    def test_past_career_lifts_score(self):
        c = {
            "profile": {"current_title": "Software Engineer"},
            "career_history": [{"title": "ML Engineer"}],
        }
        score_with_past = title_fit(c)
        c_no_past = {
            "profile": {"current_title": "Software Engineer"},
            "career_history": [],
        }
        score_no_past = title_fit(c_no_past)
        assert score_with_past > score_no_past

    def test_score_capped_at_one(self, candidate_ai_engineer):
        assert title_fit(candidate_ai_engineer) <= 1.0

    def test_score_non_negative(self, candidate_hr):
        assert title_fit(candidate_hr) >= 0.0


# ---------------------------------------------------------------------------
# skill_relevance
# ---------------------------------------------------------------------------

class TestSkillRelevance:
    def test_multiple_core_skills_score_high(self, candidate_ai_engineer):
        score = skill_relevance(candidate_ai_engineer)
        assert score >= 0.5, f"Expected >= 0.5, got {score}"

    def test_no_core_skills_score_near_zero(self, candidate_hr):
        score = skill_relevance(candidate_hr)
        assert score < 0.05, f"Expected near 0, got {score}"

    def test_score_between_zero_and_one(self, candidate_ai_engineer):
        score = skill_relevance(candidate_ai_engineer)
        assert 0.0 <= score <= 1.0

    def test_saturates_with_many_skills(self):
        core_skills = [
            "machine learning", "pytorch", "deep learning", "sql",
            "python", "aws", "docker", "kubernetes",
        ]
        c = {
            "profile": {},
            "skills": [
                {"name": s, "proficiency": "expert", "duration_months": 36, "endorsements": 5}
                for s in core_skills
            ],
            "redrob_signals": {"skill_assessment_scores": {}},
        }
        score = skill_relevance(c)
        assert score >= 0.85, f"Expected high saturation, got {score}"

    def test_zero_duration_advanced_skill_halved(self):
        c_full = {
            "profile": {},
            "skills": [{"name": "pytorch", "proficiency": "advanced", "duration_months": 24}],
            "redrob_signals": {"skill_assessment_scores": {}},
        }
        c_zero = {
            "profile": {},
            "skills": [{"name": "pytorch", "proficiency": "advanced", "duration_months": 0}],
            "redrob_signals": {"skill_assessment_scores": {}},
        }
        assert skill_relevance(c_full) > skill_relevance(c_zero)

    def test_assessment_score_modulates_trust(self):
        base = {
            "profile": {},
            "skills": [{"name": "machine learning", "proficiency": "intermediate", "duration_months": 24}],
            "redrob_signals": {},
        }
        with_high_assess = {
            **base,
            "redrob_signals": {"skill_assessment_scores": {"machine learning": 95}},
        }
        with_low_assess = {
            **base,
            "redrob_signals": {"skill_assessment_scores": {"machine learning": 10}},
        }
        assert skill_relevance(with_high_assess) > skill_relevance(with_low_assess)


# ---------------------------------------------------------------------------
# experience_fit
# ---------------------------------------------------------------------------

class TestExperienceFit:
    def test_sweet_spot_scores_one(self):
        for yoe in (6, 7, 8):
            c = {"profile": {"years_of_experience": yoe}}
            assert experience_fit(c) == pytest.approx(1.0), f"yoe={yoe}"

    def test_ideal_band_scores_high(self):
        for yoe in (5, 9):
            c = {"profile": {"years_of_experience": yoe}}
            assert experience_fit(c) >= 0.85, f"yoe={yoe}"

    def test_very_junior_scores_low(self):
        c = {"profile": {"years_of_experience": 1}}
        assert experience_fit(c) == pytest.approx(0.10)

    def test_ramp_phase_in_range(self):
        c = {"profile": {"years_of_experience": 3}}
        score = experience_fit(c)
        assert 0.30 <= score <= 0.75, f"yoe=3 should be in ramp, got {score}"

    def test_overqualified_decays_but_stays_above_floor(self):
        c = {"profile": {"years_of_experience": 20}}
        score = experience_fit(c)
        assert score >= 0.40, f"Expected >= floor 0.40, got {score}"

    def test_overqualified_lower_than_ideal(self):
        ideal = experience_fit({"profile": {"years_of_experience": 7}})
        old = experience_fit({"profile": {"years_of_experience": 18}})
        assert ideal > old

    def test_zero_experience_handled(self, minimal_candidate):
        score = experience_fit(minimal_candidate)
        assert score == pytest.approx(0.10)


# ---------------------------------------------------------------------------
# location_fit
# ---------------------------------------------------------------------------

class TestLocationFit:
    def test_noida_scores_one(self):
        c = {"profile": {"location": "Noida", "country": "India"}, "redrob_signals": {}}
        assert location_fit(c) == pytest.approx(1.0)

    def test_pune_scores_one(self):
        c = {"profile": {"location": "Pune", "country": "India"}, "redrob_signals": {}}
        assert location_fit(c) == pytest.approx(1.0)

    def test_tier1_city_scores_high(self):
        c = {"profile": {"location": "Bangalore", "country": "India"}, "redrob_signals": {}}
        score = location_fit(c)
        assert score >= 0.85, f"Expected >= 0.85 for Bangalore, got {score}"

    def test_generic_india_mid_score(self):
        c = {"profile": {"location": "Some Town", "country": "india"}, "redrob_signals": {}}
        score = location_fit(c)
        assert score == pytest.approx(0.70)

    def test_abroad_willing_to_relocate(self):
        c = {
            "profile": {"location": "San Francisco", "country": "USA"},
            "redrob_signals": {"willing_to_relocate": True},
        }
        assert location_fit(c) == pytest.approx(0.40)

    def test_abroad_not_willing_near_zero(self):
        c = {
            "profile": {"location": "London", "country": "UK"},
            "redrob_signals": {"willing_to_relocate": False},
        }
        assert location_fit(c) == pytest.approx(0.05)

    def test_missing_location_falls_back_to_country(self):
        c = {"profile": {"location": "", "country": "india"}, "redrob_signals": {}}
        assert location_fit(c) == pytest.approx(0.70)

    def test_score_in_valid_range(self, candidate_ai_engineer):
        score = location_fit(candidate_ai_engineer)
        assert 0.0 <= score <= 1.0
