"""
Honeypot / consistency filter.

Detects logically impossible profiles and returns a list of reason strings.
A non-empty list means the candidate should be vetoed from the top 100.

All checks are conservative to avoid false-positives on real candidates.
The human will calibrate thresholds against labels later.
"""

from datetime import datetime, date

_TODAY = date.today()


def _parse_date(s: str | None) -> date | None:
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m", "%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _total_career_months(candidate: dict) -> int:
    """Sum duration_months across all career history entries."""
    return sum(
        int(j.get("duration_months", 0) or 0)
        for j in candidate.get("career_history", [])
    )


def check_honeypot(candidate: dict) -> list:
    """Return a list of impossibility reasons (empty = clean)."""
    reasons = []
    profile = candidate.get("profile", {})
    yoe = float(profile.get("years_of_experience", 0) or 0)
    skills = candidate.get("skills", [])
    career = candidate.get("career_history", [])
    education = candidate.get("education", [])

    # --- 1. Career tenure far exceeds stated years_of_experience ---------------
    # Allow generous slack (1.5x) to avoid false positives from overlapping roles.
    total_months = _total_career_months(candidate)
    yoe_months = yoe * 12
    if yoe_months > 0 and total_months > yoe_months * 1.6:
        reasons.append(
            f"career_tenure_mismatch: total career months {total_months} "
            f"exceeds {yoe_months:.0f} (1.6x yoe={yoe}) threshold"
        )

    # --- 2. Many skills expert/advanced with zero duration ----------------------
    zero_dur_advanced = [
        s["name"] for s in skills
        if s.get("duration_months", 0) == 0
        and s.get("proficiency", "").lower() in ("advanced", "expert")
    ]
    if len(zero_dur_advanced) >= 4:
        reasons.append(
            f"zero_duration_advanced_skills: {len(zero_dur_advanced)} skills "
            f"marked advanced/expert with duration_months=0"
        )

    # --- 3. A single skill used longer than the entire career -------------------
    career_months_max = max(total_months, int(yoe * 12)) if yoe > 0 else total_months
    for s in skills:
        dur = int(s.get("duration_months", 0) or 0)
        if career_months_max > 0 and dur > career_months_max * 1.3:
            reasons.append(
                f"skill_duration_exceeds_career: skill '{s.get('name')}' "
                f"duration {dur}m > career {career_months_max}m * 1.3"
            )
            break  # one example is enough

    # --- 4. Impossible job dates ------------------------------------------------
    for job in career:
        title = job.get("title", "unknown")
        start = _parse_date(job.get("start_date"))
        end = _parse_date(job.get("end_date"))
        if start and end and end < start:
            reasons.append(
                f"impossible_job_dates: '{title}' end {end} before start {start}"
            )
            break
        if start and start > _TODAY:
            reasons.append(
                f"future_job_start: '{title}' starts in the future ({start})"
            )
            break

    # --- 5. Impossible education dates -----------------------------------------
    for edu in education:
        ey = edu.get("end_year")
        sy = edu.get("start_year")
        if ey and sy and ey < sy:
            reasons.append(
                f"impossible_edu_dates: {edu.get('institution','?')} "
                f"end_year {ey} < start_year {sy}"
            )
            break

    return reasons
