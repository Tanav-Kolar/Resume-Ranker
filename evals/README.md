# evals/ — local evaluation harness

A private proxy for the hidden leaderboard. Lets you measure any `submission.csv`
against a small, hand-verified relevance set so you can tune weights / add the
semantic component with a number instead of a guess.

## Files
- `labels.csv` — 60 candidates labeled tier 0–5 (the answer key).
- `evaluate.py` — the grader: NDCG@10/50, MAP, P@10, official composite, coverage, honeypot leakage.
- `baseline.json` — the current pipeline's score (the pre-semantic reference line).
- `make_label_worksheet.py` — reproducible stratified sampler (regenerates the labeling worksheet).

## Run it
```bash
python evals/evaluate.py --submission submission.csv --labels evals/labels.csv
# write/refresh the stored baseline:
python evals/evaluate.py --submission submission.csv --labels evals/labels.csv --json evals/baseline.json
```

## Scoring
`composite = 0.50·NDCG@10 + 0.30·NDCG@50 + 0.15·MAP + 0.05·P@10` (the organizers'
formula). "Relevant" for P@10 / MAP = tier ≥ 3. Only labeled candidates contribute,
so treat the composite as **relative** (before vs after a change), not an absolute
prediction of the hidden score.

## Tier rubric (JD-anchored)
- **5** — ideal: shipped production retrieval / ranking / search / recsys at a product company, ~6–8 yrs, India, active.
- **4** — strong applied ML/AI at a product company, adjacent to the mandate (recsys or search, slightly off-ideal).
- **3** — relevant: solid ML/DS/SWE-ML with real ML or retrieval exposure; could do the role (the P@10 threshold).
- **2** — adjacent: tech + some ML but weak fit, or off-target specialty (CV/speech), or currently at an IT-services firm.
- **1** — tech but off-domain (generic dev / QA / DevOps / analyst, no ML/IR).
- **0** — not relevant / honeypot.

## Strata (why these 60)
- **A (30)** — sampled from the current submission top-100 (ranks 1–10, 11–50, 51–100) → measures whether the *current ordering* is good.
- **B (15)** — strong candidates *not* in the top-100 (7 strong-title + 8 plain-language "Senior SWE (ML)" fits) → measures recall / misses.
- **C (15)** — negatives: honeypots + off-target (CV/speech) + generic-irrelevant.

## Baseline (current pipeline, pre-semantic)
| metric | value |
|---|---|
| NDCG@10 | 0.8164 |
| NDCG@50 | 0.6047 |
| MAP | 0.4901 |
| P@10 | 1.0000 |
| **composite** | **0.7131** |
| tier-0 in top10/50/100 | 0 / 0 / 0 |
| labeled coverage top10/50/100 | 10 / 22 / 30 |

Floor check: the deliberately-weak `sample_submission.csv` scores **0.4106**, so the
pipeline is well above the naive floor.

## What the baseline says (where to improve)
- **P@10 = 1.0, tier-0 leakage = 0** → the top is clean of honeypots/non-fits; the honeypot veto is working.
- **NDCG@10 = 0.816 (not ~1.0)** → *ordering* inside the top-10: tier-3 generalist DS profiles sit above tier-5 retrieval/ranking specialists (e.g. rank-1 is a tier-3 generalist while tier-5 specialists sit at ranks 2–3). Reordering the top is the NDCG@10 lever.
- **MAP = 0.49** → *recall*: many tier-3 "plain-language fits" (Senior SWE(ML) with retrieval work) and even a tier-5 are outside the top-100. This is exactly what the semantic component should pull in.

## Caveats & honeypot-check calibration (findings while labeling)
- **`skill_duration_exceeds_career` is high-precision** — every candidate it flagged was a genuine impossibility (e.g. a QA Engineer with 1 yr experience claiming 49 months of Sentence Transformers; a "Meta recsys" profile claiming 82 months of LangChain). Trust it as a hard veto.
- **Education-date and `exp>since_grad` checks are noisy** — the synthetic education `start_year`/`end_year` are largely decoupled from careers (e.g. an M.Tech dated 2002–2006 on someone with 6.5 yrs experience). The proposed education-duration honeypot checks will **false-positive heavily** here; keep them *soft* at most, and prefer `skill_duration_exceeds_career` and the fictional-company gate.
- **One label to audit:** `CAND_0095884` is a *marginal* honeypot (Feature Engineering 59m vs 45m career, barely over threshold) — eyeball it and adjust if you disagree.
- Labels are a ~60-row proxy; re-verify ~20 rows against your own read before trusting deltas, and expand the set if top-50 coverage (22/50) feels thin.
