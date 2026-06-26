"""
Composite scorer: fuses rule-based components + behavioral multiplier + honeypot veto.

Extension seam: pass `semantic` (float 0..1, default None) to blend in a dense
retrieval score when the human plugs in their model.  The fusion weights below are
placeholders — all marked TODO for tuning.

Final formula:
    base  = weighted_sum(title, skill, experience, location [, semantic])
    final = base * behavioral_multiplier
    if honeypot: final = HONEYPOT_SENTINEL
"""

from src import features, behavioral, honeypot

# ---------------------------------------------------------------------------
# Component weights  (TODO: tune against labeled eval set)
# ---------------------------------------------------------------------------
# Must sum to 1.0 when semantic is absent.
WEIGHT_TITLE = 0.45        # primary signal — beats keyword stuffers
WEIGHT_SKILL = 0.25        # secondary; trust-deflated to resist stuffing
WEIGHT_EXPERIENCE = 0.15   # experience band
WEIGHT_LOCATION = 0.15     # geo fit

# When semantic score is provided, it replaces part of skill signal.
# The human should tune this split.
WEIGHT_SEMANTIC = 0.20     # replaces this share of WEIGHT_SKILL when active

# Candidates detected as honeypots get this score so they sort to the bottom.
HONEYPOT_SENTINEL = -1.0


def composite_score(candidate: dict, semantic: float | None = None) -> dict:
    """Score a single candidate and return a result dict.

    Returns:
        {
            "candidate_id": str,
            "score": float,           # final score (may be HONEYPOT_SENTINEL)
            "components": dict,       # individual component scores for debugging
            "honeypot_reasons": list, # empty unless vetoed
        }
    """
    cid = candidate.get("candidate_id", "UNKNOWN")

    # --- Rule-based components ---
    t_score = features.title_fit(candidate)
    s_score = features.skill_relevance(candidate)
    e_score = features.experience_fit(candidate)
    l_score = features.location_fit(candidate)

    # --- Weighted sum ---
    if semantic is not None:
        # Blend: reduce skill weight, add semantic weight, keep total = 1.
        w_skill_adj = WEIGHT_SKILL - WEIGHT_SEMANTIC
        base = (
            WEIGHT_TITLE * t_score
            + w_skill_adj * s_score
            + WEIGHT_SEMANTIC * float(semantic)
            + WEIGHT_EXPERIENCE * e_score
            + WEIGHT_LOCATION * l_score
        )
    else:
        base = (
            WEIGHT_TITLE * t_score
            + WEIGHT_SKILL * s_score
            + WEIGHT_EXPERIENCE * e_score
            + WEIGHT_LOCATION * l_score
        )

    base = max(0.0, min(1.0, base))

    # --- Behavioral multiplier ---
    b_mult = behavioral.behavioral_multiplier(candidate)
    final = base * b_mult
    final = max(0.0, min(1.5, final))  # allow slight >1.0 for very available top fits

    # --- Honeypot veto ---
    hp_reasons = honeypot.check_honeypot(candidate)
    if hp_reasons:
        final = HONEYPOT_SENTINEL

    return {
        "candidate_id": cid,
        "score": round(final, 6),
        "components": {
            "title": round(t_score, 4),
            "skill": round(s_score, 4),
            "experience": round(e_score, 4),
            "location": round(l_score, 4),
            "behavioral_mult": round(b_mult, 4),
            "semantic": semantic,
        },
        "honeypot_reasons": hp_reasons,
    }
