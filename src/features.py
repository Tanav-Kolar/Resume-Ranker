"""
Rule-based scoring components. Each function returns a float in [0, 1].

All weights are placeholders — the human will tune them against labels.
Keep functions small and pure so they're easy to replace individually.
"""

import math
from src import jd


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _title_tier(title: str) -> float:
    """Map a single title string to its tier score."""
    t = title.lower()
    for pattern in jd.TITLE_LOW:
        if pattern in t:
            return jd.TITLE_SCORE_LOW
    for pattern in jd.TITLE_HIGH:
        if pattern in t:
            return jd.TITLE_SCORE_HIGH
    for pattern in jd.TITLE_MEDIUM:
        if pattern in t:
            return jd.TITLE_SCORE_MEDIUM
    return jd.TITLE_SCORE_UNKNOWN


def _best_career_title_score(candidate: dict) -> float:
    """Return the highest title-tier score across all career history entries."""
    best = 0.0
    for job in candidate.get("career_history", []):
        t = job.get("title", "")
        if t:
            best = max(best, _title_tier(t))
    return best


# ---------------------------------------------------------------------------
# Component 1: Title / role fit  (primary signal)
# ---------------------------------------------------------------------------

def title_fit(candidate: dict) -> float:
    """Score based on current title and best historical title.

    Current title dominates (weight 0.7) because it reflects present identity.
    Best past title provides a softer signal (weight 0.3) to catch candidates
    who transitioned into the right role from something unrelated.
    """
    profile = candidate.get("profile", {})
    current = profile.get("current_title", "")
    current_score = _title_tier(current) if current else jd.TITLE_SCORE_UNKNOWN

    past_score = _best_career_title_score(candidate)
    # If past_score is better, let it lift current slightly but not dominate.
    blended = 0.70 * current_score + 0.30 * past_score
    return min(1.0, blended)


# ---------------------------------------------------------------------------
# Component 2: Skill relevance (trust-deflated)
# ---------------------------------------------------------------------------

def _skill_trust(skill: dict, assessment_scores: dict) -> float:
    """Compute a trust-adjusted weight for a single skill entry.

    Trust = proficiency weight * assessment modifier (if available).
    This deflates buzzword-stuffed profiles where assessments reveal shallow knowledge.
    """
    prof = skill.get("proficiency", "beginner").lower()
    prof_w = jd.PROFICIENCY_WEIGHT.get(prof, 0.30)

    skill_name = skill.get("name", "").strip()
    if skill_name in assessment_scores:
        # Assessment is 0-100; scale to 0-1, clamp, use as modifier
        assessment = assessment_scores[skill_name] / 100.0
        assessment = max(0.0, min(1.0, assessment))
        # Weight proficiency 60%, assessment 40%
        trust = 0.60 * prof_w + 0.40 * assessment
    else:
        trust = prof_w

    # Duration sanity: zero-duration advanced/expert skills get halved
    duration = skill.get("duration_months", 0)
    if duration == 0 and prof in ("advanced", "expert"):
        trust *= 0.5

    return trust


def skill_relevance(candidate: dict) -> float:
    """Saturating sum of trust-adjusted scores for core ML/AI skills.

    A saturating function (tanh-based) prevents piling on skills from
    overpowering the title signal.
    """
    signals = candidate.get("redrob_signals", {})
    raw_assessments = signals.get("skill_assessment_scores", {}) or {}
    # Normalise keys to lowercase for lookup
    assessment_scores = {k.lower(): v for k, v in raw_assessments.items()}

    total_trust = 0.0
    for skill in candidate.get("skills", []):
        name = skill.get("name", "").lower().strip()
        if name in jd.CORE_SKILLS:
            # Look up assessment by lowercase name
            trust = _skill_trust(skill, assessment_scores)
            total_trust += trust
        # Generic skills contribute nothing

    # Saturate: target ~5 strong core skills for score ~0.9
    # tanh(x/3.5) reaches ~0.90 at x≈6, ~0.98 at x≈10
    score = math.tanh(total_trust / 3.5)
    return score


# ---------------------------------------------------------------------------
# Component 3: Experience fit
# ---------------------------------------------------------------------------

def experience_fit(candidate: dict) -> float:
    """Reward the 5-9 yr band; ramp below, decay gently above.

    Sweet spot 6-8 yrs gets a small bonus.
    """
    yoe = candidate.get("profile", {}).get("years_of_experience", 0) or 0

    if yoe < 2:
        return 0.10
    if yoe < jd.EXP_IDEAL_MIN:
        # Linear ramp 2..5 → 0.30..0.75
        return 0.30 + 0.45 * (yoe - 2) / (jd.EXP_IDEAL_MIN - 2)
    if yoe <= jd.EXP_IDEAL_MAX:
        base = 0.90
        # Bonus for sweet spot 6-8
        if jd.EXP_SWEET_MIN <= yoe <= jd.EXP_SWEET_MAX:
            base = 1.0
        return base
    # Gentle decay above 9 yrs — overqualified but not a disqualifier
    # Reaches ~0.65 at 15 yrs, ~0.55 at 20 yrs
    decay = math.exp(-0.05 * (yoe - jd.EXP_IDEAL_MAX))
    return max(0.40, 0.90 * decay)


# ---------------------------------------------------------------------------
# Component 4: Location fit
# ---------------------------------------------------------------------------

def location_fit(candidate: dict) -> float:
    """Score geo match.

    Noida / Pune best; Tier-1 Indian cities very good; generic India good;
    abroad-but-willing acceptable; abroad-not-willing near zero.
    """
    profile = candidate.get("profile", {})
    country = (profile.get("country") or "").strip().lower()
    location = (profile.get("location") or "").strip().lower()
    signals = candidate.get("redrob_signals", {})
    willing = signals.get("willing_to_relocate", False)

    # Check specific Indian cities first
    for city, score in jd.LOCATION_TIER.items():
        if city in location:
            return score

    # Generic India match
    if country == "india":
        return jd.LOCATION_SCORE_INDIA_GENERIC

    # Outside India
    if willing:
        return jd.LOCATION_SCORE_ABROAD_WILLING
    return jd.LOCATION_SCORE_ABROAD_NOT_WILLING
