# Redrob AI — Candidate Ranker (Baseline)

Ranks a pool of 100,000 candidate profiles against the **Senior AI Engineer, Founding Team @ Redrob AI** job description and emits a top-100 shortlist as a spec-compliant CSV.

---

## Reproduce

```bash
python rank.py --candidates ./challenge_dataset/candidates.jsonl --out ./submission.csv
```

No installation required — the baseline uses only the Python standard library (Python ≥ 3.10).

Validate the output:

```bash
python data/validate_submission.py submission.csv
```

Typical runtime: **< 5 seconds** on a single CPU core for the full 100K pool.

---

## Project layout

```
rank.py                  # CLI entry point
requirements.txt         # empty (stdlib only)
submission_metadata.yaml # fill in before submitting
src/
  io_utils.py            # streaming JSONL (.gz transparent) reader + spec-safe CSV writer
  jd.py                  # encoded JD knowledge: title tiers, skill vocab, geo, exp band
  text.py                # candidate text blob builder (semantic seam for human's LM step)
  features.py            # rule-based scoring components (title, skill, experience, location)
  behavioral.py          # availability multiplier; handles -1 sentinels as "no data"
  honeypot.py            # logical-consistency veto for impossible profiles
  score.py               # composite fusion with optional `semantic` seam
  reasoning.py           # deterministic, field-grounded reasoning string generator
challenge_dataset/
  candidates.jsonl        # 100K candidate profiles (not committed — too large)
  sample_candidates.json  # ~50 candidate sample for fast testing
  validate_submission.py  # official validator
  ...
```

---

## Scoring approach

```
final = weighted_sum(title, skill, experience, location) * behavioral_multiplier
```

If the candidate is detected as a honeypot, `final = -1` (pushed to the bottom).

| Component | Weight | Purpose |
|---|---|---|
| Title fit | 0.45 | Primary anti-keyword-stuffer signal — maps role to tier |
| Skill relevance | 0.25 | Trust-deflated by proficiency + assessment; saturating |
| Experience fit | 0.15 | Rewards 5–9 yr band (sweet spot 6–8 = 1.0) |
| Location fit | 0.15 | Noida/Pune > Tier-1 India > India > abroad-if-willing |
| Behavioral multiplier | ×0.5–1.2 | Recency, open-to-work flag, recruiter response rate |

### Extension seam

`score.composite_score(candidate, semantic=<float 0-1>)` accepts an optional dense
retrieval score. When provided, it replaces 20 pp of the skill weight so the human
can plug in their semantic model without touching I/O or CLI code.

---

## Acceptance checks

- `validate_submission.py` prints **Submission is valid.**
- Full 100K run completes in **~4 seconds**, well under the 5-minute budget.
- Top 100 are entirely AI/ML/Data engineering roles — zero HR/Accountant/Marketing titles.
- No logically-impossible (honeypot) profile in the top 100.
- Output is deterministic across runs (fixed sort: score desc, candidate_id asc).
- No LLM, no network, CPU-only.
