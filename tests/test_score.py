"""Tests for src/score.py — composite scorer."""
import pytest

from src.score import HONEYPOT_SENTINEL, composite_score


class TestCompositeScore:
    # --- Return structure ---

    def test_returns_dict_with_required_keys(self, candidate_ai_engineer):
        result = composite_score(candidate_ai_engineer)
        assert "candidate_id" in result
        assert "score" in result
        assert "components" in result
        assert "honeypot_reasons" in result

    def test_components_dict_has_all_keys(self, candidate_ai_engineer):
        result = composite_score(candidate_ai_engineer)
        for key in ("title", "skill", "experience", "location", "behavioral_mult"):
            assert key in result["components"], f"Missing component: {key}"

    def test_candidate_id_propagated(self, candidate_ai_engineer):
        result = composite_score(candidate_ai_engineer)
        assert result["candidate_id"] == "CAND_0000001"

    # --- Score bounds ---

    def test_score_non_negative_for_clean_candidate(self, candidate_ai_engineer):
        result = composite_score(candidate_ai_engineer)
        assert result["score"] >= 0.0

    def test_score_at_most_1_5(self, candidate_ai_engineer):
        result = composite_score(candidate_ai_engineer)
        assert result["score"] <= 1.5

    def test_score_rounded_to_6_decimals(self, candidate_ai_engineer):
        result = composite_score(candidate_ai_engineer)
        assert result["score"] == round(result["score"], 6)

    # --- Ranking direction ---

    def test_ai_engineer_scores_higher_than_hr(self, candidate_ai_engineer, candidate_hr):
        ai_score = composite_score(candidate_ai_engineer)["score"]
        hr_score = composite_score(candidate_hr)["score"]
        assert ai_score > hr_score

    # --- Honeypot veto ---

    def test_honeypot_candidate_gets_sentinel(self, candidate_honeypot):
        result = composite_score(candidate_honeypot)
        assert result["score"] == HONEYPOT_SENTINEL

    def test_honeypot_reasons_non_empty_for_honeypot(self, candidate_honeypot):
        result = composite_score(candidate_honeypot)
        assert len(result["honeypot_reasons"]) > 0

    def test_clean_candidate_has_empty_honeypot_reasons(self, candidate_ai_engineer):
        result = composite_score(candidate_ai_engineer)
        assert result["honeypot_reasons"] == []

    # --- Semantic seam ---

    def test_semantic_score_changes_result(self, candidate_ai_engineer):
        without_semantic = composite_score(candidate_ai_engineer)["score"]
        with_semantic = composite_score(candidate_ai_engineer, semantic=1.0)["score"]
        # With perfect semantic score, result should differ (unless already capped at 1.5)
        assert without_semantic != with_semantic or without_semantic == 1.5

    def test_semantic_stored_in_components(self, candidate_ai_engineer):
        result = composite_score(candidate_ai_engineer, semantic=0.75)
        assert result["components"]["semantic"] == pytest.approx(0.75)

    def test_semantic_none_stored_in_components(self, candidate_ai_engineer):
        result = composite_score(candidate_ai_engineer)
        assert result["components"]["semantic"] is None

    # --- Minimal candidate ---

    def test_minimal_candidate_does_not_crash(self, minimal_candidate):
        result = composite_score(minimal_candidate)
        assert isinstance(result["score"], float)
