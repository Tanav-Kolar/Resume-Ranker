#!/usr/bin/env python3
"""
Build a stratified labeling worksheet for the eval set.

Samples ~60 candidates from the CLEAN pool (reusing src.candidate_filter.is_clean)
across strata that exercise the ranking's decision boundaries, and emits both a
JSONL worksheet and a human-readable digest for tier labeling.

Honeypot detection lives entirely in src/honeypot.py. This script imports
all_honeypot_reasons() (check_honeypot veto + the extended cross-field checks)
only to *find and flag* likely honeypots for the negatives stratum; every one is
still verified by eye before it gets tier 0. This script is eval-only; it does
not touch the ranking pipeline.

Run from repo root:
    python evals/make_label_worksheet.py \
        --candidates challenge_dataset/candidates.jsonl \
        --submission submission.csv \
        --out evals/label_worksheet.jsonl
"""
from __future__ import annotations
import argparse, csv, json, os, random, sys

# Ensure repo root is importable regardless of how this script is invoked.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.candidate_filter import is_clean
from src.honeypot import all_honeypot_reasons

random.seed(42)

# ---- vocab for stratum predicates (local; independent of the ranker) --------
STRONG_TITLES = ("Lead AI Engineer", "Senior AI Engineer", "Junior ML Engineer", "AI Engineer", "NLP Engineer", "Senior NLP Engineer", "AI Specialist",
                 "Search Engineer", "Recommendation Systems Engineer", "Senior Machine Learning Engineer", "Staff Machine Learning Engineer",
                 "Applied ML Engineer", "AI Research Engineer", "Senior Data Scientist", "Senior Applied Scientist", "Machine Learning Engineer")
GENERIC_ENG_TITLES = ("Software Engineer", "Backend Engineer", "Analytics Engineer",
                      "Full Stack Developer", "Senior Software Engineer",  "Data Analyst")
IRRELEVANT_TITLES = ("QA Engineer", "DevOps Engineer", "Frontend Engineer",  "Mobile Developer",
                     "Android Developer", "Cloud Engineer", ".NET Developer", "Java Developer")
OFFTARGET_TITLES = ("Computer Vision Engineer" , "Data Engineer", "Data Scientist", "Senior Data Engineer")
IR_ML_TERMS = ("retrieval", "ranking", "recommend", "search", "embedding",
               "relevance", "learning to rank", "ltr", "semantic", "vector",
               "information retrieval", "recsys", "nlp", "language model" , "recommendation systems")
OFFTARGET_TERMS = ("computer vision", "image classification", "object detection",
                   "speech recognition", "tts", "asr", "robotics", "slam", "gans")


def _lc(s):  # safe lower
    return (s or "").lower()


def _career_text(c):
    return " ".join(_lc(j.get("description")) + " " + _lc(j.get("title"))
                    for j in c.get("career_history", []))


# ---- stratum predicates -----------------------------------------------------
# Title tuples are written with human-readable capitalisation, so compare
# case-insensitively (each pattern lowered against the lowered title).
def is_strong_title(c):
    title = _lc(c.get("profile", {}).get("current_title"))
    return any(t.lower() in title for t in STRONG_TITLES)

def is_plain_language_fit(c):
    title = _lc(c.get("profile", {}).get("current_title"))
    if not any(t.lower() in title for t in GENERIC_ENG_TITLES):
        return False
    return any(term in _career_text(c) for term in IR_ML_TERMS)

def is_offtarget(c):
    title = _lc(c.get("profile", {}).get("current_title"))
    if any(t.lower() in title for t in OFFTARGET_TITLES):
        return True
    skills = " ".join(_lc(s.get("name")) for s in c.get("skills", []))
    off = sum(1 for t in OFFTARGET_TERMS if t in skills)
    ir = sum(1 for t in IR_ML_TERMS if t in skills)
    return off >= 3 and ir == 0

def is_generic_irrelevant(c):
    title = _lc(c.get("profile", {}).get("current_title"))
    if not any(t.lower() in title for t in IRRELEVANT_TITLES):
        return False
    txt = _career_text(c) + " " + " ".join(_lc(s.get("name")) for s in c.get("skills", []))
    return not any(term in txt for term in IR_ML_TERMS)


# ---- compact record for the worksheet ---------------------------------------
def compact(c, stratum, rank=None, flags=None):
    p = c.get("profile", {})
    return {
        "candidate_id": c.get("candidate_id"),
        "stratum": stratum,
        "submission_rank": rank,
        "current_title": p.get("current_title"),
        "yoe": p.get("years_of_experience"),
        "location": p.get("location"),
        "country": p.get("country"),
        "current_company": p.get("current_company"),
        "current_industry": p.get("current_industry"),
        "summary": (p.get("summary") or "")[:400],
        "career": [
            {"title": j.get("title"), "company": j.get("company"),
             "dates": f"{j.get('start_date')}->{j.get('end_date')}",
             "months": j.get("duration_months"), "is_current": j.get("is_current"),
             "industry": j.get("industry"),
             "desc": (j.get("description") or "")[:220]}
            for j in c.get("career_history", [])[:4]
        ],
        "education": [
            {"degree": e.get("degree"), "field": e.get("field_of_study"),
             "years": f"{e.get('start_year')}-{e.get('end_year')}", "tier": e.get("tier")}
            for e in c.get("education", [])
        ],
        "skills": [f"{s.get('name')}({s.get('proficiency','')[:3]},{s.get('duration_months')}m)"
                   for s in c.get("skills", [])[:14]],
        "signals": {
            "last_active": c.get("redrob_signals", {}).get("last_active_date"),
            "response_rate": c.get("redrob_signals", {}).get("recruiter_response_rate"),
            "open_to_work": c.get("redrob_signals", {}).get("open_to_work_flag"),
            "github": c.get("redrob_signals", {}).get("github_activity_score"),
            "assessments": c.get("redrob_signals", {}).get("skill_assessment_scores", {}),
        },
        "honeypot_flags": flags or [],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidates", default="challenge_dataset/candidates.jsonl")
    ap.add_argument("--submission", default="submission.csv")
    ap.add_argument("--out", default="evals/label_worksheet.jsonl")
    args = ap.parse_args()

    # submission ranks
    sub_rank = {}
    with open(args.submission, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            sub_rank[row["candidate_id"].strip()] = int(row["rank"])
    sub_ids = set(sub_rank)

    chosen_A = {}          # id -> record (in submission)
    pool_strong, pool_plain = [], []
    pool_hp, pool_off, pool_generic = [], [], []
    CAP = 400

    for line in open(args.candidates, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        c = json.loads(line)
        cid = c.get("candidate_id")
        if cid in sub_ids:
            chosen_A[cid] = c
            continue
        if not is_clean(c):
            continue
        if len(pool_strong) < CAP and is_strong_title(c):
            pool_strong.append(c)
        elif len(pool_plain) < CAP and is_plain_language_fit(c):
            pool_plain.append(c)
        if len(pool_off) < CAP and is_offtarget(c):
            pool_off.append(c)
        if len(pool_generic) < CAP and is_generic_irrelevant(c):
            pool_generic.append(c)
        if len(pool_hp) < CAP and all_honeypot_reasons(c):
            pool_hp.append(c)

    # ---- sample strata ----
    picks = []

    # A: current submission — 10 from ranks 1-10, 12 from 11-50, 8 from 51-100
    by_rank = sorted(chosen_A.values(), key=lambda c: sub_rank[c["candidate_id"]])
    band1 = [c for c in by_rank if sub_rank[c["candidate_id"]] <= 10]
    band2 = [c for c in by_rank if 11 <= sub_rank[c["candidate_id"]] <= 50]
    band3 = [c for c in by_rank if sub_rank[c["candidate_id"]] >= 51]
    for c in band1[:10]:
        picks.append(compact(c, "A_top_1_10", sub_rank[c["candidate_id"]], all_honeypot_reasons(c)))
    for c in random.sample(band2, min(12, len(band2))):
        picks.append(compact(c, "A_top_11_50", sub_rank[c["candidate_id"]], all_honeypot_reasons(c)))
    for c in random.sample(band3, min(8, len(band3))):
        picks.append(compact(c, "A_top_51_100", sub_rank[c["candidate_id"]], all_honeypot_reasons(c)))

    # B: should-be-high not in submission — 7 strong-title + 8 plain-language
    for c in random.sample(pool_strong, min(7, len(pool_strong))):
        picks.append(compact(c, "B_strong_missed", None, all_honeypot_reasons(c)))
    for c in random.sample(pool_plain, min(8, len(pool_plain))):
        picks.append(compact(c, "B_plain_language_fit", None, all_honeypot_reasons(c)))

    # C: negatives — 6 honeypot, 5 off-target, 4 generic-irrelevant
    for c in random.sample(pool_hp, min(6, len(pool_hp))):
        picks.append(compact(c, "C_honeypot", None, all_honeypot_reasons(c)))
    for c in random.sample(pool_off, min(5, len(pool_off))):
        picks.append(compact(c, "C_offtarget", None, all_honeypot_reasons(c)))
    for c in random.sample(pool_generic, min(4, len(pool_generic))):
        picks.append(compact(c, "C_generic_irrelevant", None, all_honeypot_reasons(c)))

    # dedup by id (A takes precedence)
    seen, deduped = set(), []
    for r in picks:
        if r["candidate_id"] not in seen:
            seen.add(r["candidate_id"]); deduped.append(r)

    with open(args.out, "w", encoding="utf-8") as f:
        for r in deduped:
            f.write(json.dumps(r) + "\n")

    # ---- readable digest ----
    from collections import Counter
    strata = Counter(r["stratum"] for r in deduped)
    print(f"POOLS  strong={len(pool_strong)} plain={len(pool_plain)} "
          f"hp={len(pool_hp)} off={len(pool_off)} generic={len(pool_generic)} "
          f"submission={len(chosen_A)}")
    print(f"PICKED {len(deduped)}  strata={dict(strata)}")
    print("=" * 100)
    for i, r in enumerate(deduped, 1):
        rk = f" rank#{r['submission_rank']}" if r["submission_rank"] else ""
        print(f"\n[{i}] {r['candidate_id']}  <{r['stratum']}>{rk}")
        print(f"    {r['current_title']} | {r['yoe']}y | {r['location']}, {r['country']} "
              f"| {r['current_company']} | {r['current_industry']}")
        print(f"    SUMMARY: {r['summary'][:300]}")
        for j in r["career"][:3]:
            print(f"    JOB: {j['title']} @ {j['company']} [{j['dates']} {j['months']}m cur={j['is_current']}] "
                  f"({j['industry']}) :: {j['desc'][:160]}")
        edu = "; ".join(f"{e['degree']}/{e['field']} {e['years']}" for e in r["education"])
        print(f"    EDU: {edu}")
        print(f"    SKILLS: {', '.join(r['skills'])}")
        s = r["signals"]
        print(f"    SIGNALS: active={s['last_active']} resp={s['response_rate']} "
              f"open={s['open_to_work']} gh={s['github']} assess={s['assessments']}")
        if r["honeypot_flags"]:
            print(f"    !! HONEYPOT FLAGS: {r['honeypot_flags']}")
    print("\n" + "=" * 100)
    print(f"worksheet written to {args.out}")


if __name__ == "__main__":
    main()
