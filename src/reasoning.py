"""
Deterministic, field-grounded reasoning string generator.

Rules:
- 1-2 sentences only; single-line (no embedded newlines).
- Only reference facts that exist in the profile — never hallucinate.
- Factual from the profile: title, years_of_experience, top skill, location.
"""

from src import jd


def _top_core_skill(candidate: dict) -> str | None:
    """Return the name of the highest-trust core skill, or None."""
    best_name = None
    best_trust = -1.0

    prof_order = {"expert": 4, "advanced": 3, "intermediate": 2, "beginner": 1}
    signals = candidate.get("redrob_signals", {}) or {}
    raw_assessments = signals.get("skill_assessment_scores", {}) or {}
    assessments = {k.lower(): v for k, v in raw_assessments.items()}

    for skill in candidate.get("skills", []):
        name = skill.get("name", "").strip()
        if name.lower() not in jd.CORE_SKILLS:
            continue
        prof = skill.get("proficiency", "beginner").lower()
        trust = prof_order.get(prof, 1)
        # Boost by assessment if available
        if name.lower() in assessments:
            trust += assessments[name.lower()] / 100.0
        if trust > best_trust:
            best_trust = trust
            best_name = name

    return best_name


def _count_core_skills(candidate: dict) -> int:
    return sum(
        1 for s in candidate.get("skills", [])
        if s.get("name", "").lower() in jd.CORE_SKILLS
    )


def build_reasoning(candidate: dict, result: dict) -> str:
    """Return a 1-2 sentence reasoning string grounded entirely in the profile."""
    profile = candidate.get("profile", {})
    cid = candidate.get("candidate_id", "")
    title = profile.get("current_title", "Engineer")
    yoe = profile.get("years_of_experience")
    location = profile.get("location", "") or profile.get("country", "")
    components = result.get("components", {})
    hp_reasons = result.get("honeypot_reasons", [])

    # Honeypot case
    if hp_reasons:
        short_reason = hp_reasons[0].split(":")[0].replace("_", " ")
        return (
            f"{title} with {yoe:.1f} yrs flagged as inconsistent profile "
            f"({short_reason}); excluded from shortlist."
        )

    top_skill = _top_core_skill(candidate)
    n_core = _count_core_skills(candidate)

    # Build sentence 1: title + experience
    yoe_str = f"{yoe:.1f} yrs" if yoe is not None else "unknown experience"
    s1 = f"{title} with {yoe_str} of experience"
    if location:
        s1 += f" based in {location}"
    s1 += "."

    # Build sentence 2: skill highlight + score context
    parts = []
    if top_skill:
        parts.append(f"Top matched skill: {top_skill}")
    if n_core > 0:
        parts.append(f"{n_core} core AI/ML skills")

    t_score = components.get("title", 0)
    if t_score >= 0.90:
        parts.append("strong role fit")
    elif t_score >= 0.55:
        parts.append("moderate role fit")
    else:
        parts.append("weak role fit")

    s2 = "; ".join(parts) + "." if parts else ""

    return (s1 + " " + s2).strip()
