from __future__ import annotations

from typing import Iterator

CONSULTING_COMPANIES: frozenset[str] = frozenset({
    'infosys', 'wipro', 'tcs', 'capgemini', 'hcl', 'mindtree',
    'accenture', 'cognizant', 'tech mahindra', 'mphasis',
})

FICTIONAL_COMPANIES: frozenset[str] = frozenset({
    'pied piper', 'initech', 'wayne enterprises', 'stark industries',
    'hooli', 'dunder mifflin', 'globex inc', 'acme corp',
})


def _sorted_companies(candidate: dict) -> list[str]:
    career = candidate.get('career_history') or []
    jobs = sorted(
        [j for j in career if j.get('start_date')],
        key=lambda j: j['start_date'],
        reverse=True,
    )
    return [
        j.get('company', '').strip().lower()
        for j in jobs
        if j.get('company', '').strip()
    ]


def is_consulting_only(candidate: dict) -> bool:
    companies = _sorted_companies(candidate)
    return bool(companies) and all(c in CONSULTING_COMPANIES for c in companies)


def has_fictional_company(candidate: dict) -> bool:
    return any(c in FICTIONAL_COMPANIES for c in _sorted_companies(candidate))


def is_clean(candidate: dict) -> bool:
    return not is_consulting_only(candidate) and not has_fictional_company(candidate)


def filter_candidates(candidates: Iterator[dict]) -> Iterator[dict]:
    for candidate in candidates:
        if is_clean(candidate):
            yield candidate
