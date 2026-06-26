"""
Behavioral availability multiplier.

Scales the fit score by how reachable and active the candidate is.
Range: approx 0.5 – 1.2.  All -1 sentinel values are treated as "no data",
not as bad data — they contribute nothing positive or negative.
"""

from datetime import date, datetime


_TODAY = date.today()


def _recency_score(last_active_date_str: str) -> float:
    """Return 0..1 based on how recently the candidate was active.

    > 30 days ago degrades linearly; > 180 days → 0.1.
    """
    if not last_active_date_str:
        return 0.50  # no data — neutral
    try:
        last = datetime.strptime(last_active_date_str, "%Y-%m-%d").date()
    except ValueError:
        return 0.50
    days = (_TODAY - last).days
    if days <= 0:
        return 1.0
    if days <= 30:
        return 1.0
    if days <= 180:
        return 1.0 - 0.9 * (days - 30) / 150
    return 0.10


def behavioral_multiplier(candidate: dict) -> float:
    """Return a multiplier in [0.5, 1.2] reflecting candidate availability.

    Components (each normalised 0..1):
      - recency of last_active_date
      - open_to_work_flag
      - recruiter_response_rate  (-1 → neutral 0.5)
    """
    signals = candidate.get("redrob_signals", {}) or {}

    recency = _recency_score(signals.get("last_active_date", ""))

    open_flag = signals.get("open_to_work_flag", None)
    if open_flag is True:
        open_score = 1.0
    elif open_flag is False:
        open_score = 0.40
    else:
        open_score = 0.60  # unknown → slight positive default

    response_rate = signals.get("recruiter_response_rate", -1)
    if response_rate == -1 or response_rate is None:
        response_score = 0.50  # no data → neutral
    else:
        response_score = float(response_rate)

    # Weighted average of three availability signals
    availability = (
        0.40 * recency +
        0.35 * open_score +
        0.25 * response_score
    )

    # Scale to [0.5, 1.2]: high availability boosts, low availability discounts
    multiplier = 0.5 + 0.7 * availability
    return round(multiplier, 4)
