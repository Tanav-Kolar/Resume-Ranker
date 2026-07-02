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


# ---------------------------------------------------------------------------
# Extended cross-field consistency checks
# ---------------------------------------------------------------------------
# Reliability note (calibrated against the eval label set):
#   HIGH-PRECISION (safe to promote into the check_honeypot veto if desired):
#     duration_exceeds_span, is_current_but_ended / not_current_no_end,
#     signal-date sanity, current_company_mismatch.
#   NOISY in this dataset (education start/end years are largely decoupled from
#     careers — e.g. an M.Tech dated 2002-2006 on a 6-yr candidate — so these
#     false-positive heavily; keep SOFT / eval-only, do NOT hard-veto):
#     exp_exceeds_since_grad, work_before_college, education_too_short.
# check_honeypot() (the veto) intentionally does NOT call these; they are
# surfaced separately so the human decides which, if any, to promote.

_CUR_YEAR = _TODAY.year


def _canonical_degree_years(degree: str):
    """Canonical program length in years; None = skip (PhD/diploma/unknown)."""
    d = (degree or "").lower()
    if "integrated" in d or "dual degree" in d:
        return 5
    if any(k in d for k in ("b.tech", "btech", "b.e", "bachelor of technology",
                            "bachelor of engineering")):
        return 4
    if any(k in d for k in ("bca", "bba", "b.com", "bcom", "b.a", "bachelor of arts",
                            "bachelor of commerce", "b.sc", "bsc", "bachelor of science")):
        return 3
    if any(k in d for k in ("m.tech", "mtech", "m.e", "master of technology",
                            "mba", "pgdm", "m.sc", "msc", "master of science",
                            "master of business")):
        return 2
    return None


def extended_honeypot_reasons(candidate: dict) -> list:
    """Strengthened cross-field consistency checks (see reliability note above).

    Returned as reason strings but NOT part of the check_honeypot veto by default.
    """
    reasons = []
    p = candidate.get("profile", {})
    yoe = float(p.get("years_of_experience", 0) or 0)
    career = candidate.get("career_history", [])
    edu = candidate.get("education", [])
    sig = candidate.get("redrob_signals", {})

    # duration_months vs the date span, per job (self-contradiction — high precision)
    for j in career:
        sd, ed = _parse_date(j.get("start_date")), _parse_date(j.get("end_date"))
        if sd:
            end = ed or _TODAY
            span = (end.year - sd.year) * 12 + (end.month - sd.month)
            dur = int(j.get("duration_months", 0) or 0)
            if dur > span + 6:
                reasons.append(f"duration_exceeds_span: '{j.get('title')}' {dur}m vs {span}m span")
                break

    # experience exceeds time since graduation (NOISY — education dates unreliable)
    grad_years = [e.get("end_year") for e in edu
                  if _canonical_degree_years(e.get("degree", "")) in (3, 4, 5)
                  and isinstance(e.get("end_year"), int)]
    if grad_years:
        grad = max(min(grad_years), 1970)
        if 1970 <= grad <= _CUR_YEAR and yoe > (_CUR_YEAR - grad) + 1.5:
            reasons.append(f"exp_exceeds_since_grad: yoe {yoe} vs {_CUR_YEAR - grad}y since {grad}")

    # working before starting undergrad (NOISY)
    ug_starts = [e.get("start_year") for e in edu
                 if _canonical_degree_years(e.get("degree", "")) in (3, 4, 5)
                 and isinstance(e.get("start_year"), int)]
    job_years = [_parse_date(j.get("start_date")).year for j in career
                 if _parse_date(j.get("start_date"))]
    if ug_starts and job_years and min(job_years) < min(ug_starts):
        reasons.append(f"work_before_college: job {min(job_years)} < ug {min(ug_starts)}")

    # is_current vs end_date (high precision)
    for j in career:
        ic = j.get("is_current")
        ed = _parse_date(j.get("end_date"))
        if ic is True and ed and ed.year < _CUR_YEAR:
            reasons.append(f"is_current_but_ended: '{j.get('title')}' ended {ed}")
            break
        if ic is False and j.get("end_date") in (None, "", "null"):
            reasons.append(f"not_current_no_end: '{j.get('title')}'")
            break

    # signal-date sanity (high precision)
    su, la = _parse_date(sig.get("signup_date")), _parse_date(sig.get("last_active_date"))
    if su and la and la < su:
        reasons.append(f"last_active_before_signup: {la} < {su}")
    if (su and su > _TODAY) or (la and la > _TODAY):
        reasons.append("signal_date_in_future")

    # current_company vs the is_current job (high precision)
    cur_co = (p.get("current_company") or "").lower()
    cur_jobs = [(j.get("company") or "").lower() for j in career if j.get("is_current")]
    if cur_co and cur_jobs and not any(cur_co in cj or cj in cur_co for cj in cur_jobs):
        reasons.append(f"current_company_mismatch: '{cur_co}' not in current job(s)")

    # education finishing impossibly fast (NOISY — canonical-2 or less)
    for e in edu:
        can = _canonical_degree_years(e.get("degree", ""))
        sy, ey = e.get("start_year"), e.get("end_year")
        if can and isinstance(sy, int) and isinstance(ey, int):
            actual = ey - sy
            if 0 <= actual <= can - 2:
                reasons.append(f"education_too_short: {e.get('degree')} {actual}y vs {can}y")
                break

    return reasons


def all_honeypot_reasons(candidate: dict) -> list:
    """The veto set (check_honeypot) + the extended checks.

    For tooling that wants the full picture (e.g. the eval label sampler). The
    pipeline veto uses check_honeypot alone.
    """
    return list(check_honeypot(candidate)) + extended_honeypot_reasons(candidate)
