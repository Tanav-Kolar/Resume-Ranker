---
title: Redrob AI Candidate Ranker
emoji: 🤖
colorFrom: blue
colorTo: indigo
sdk: streamlit
sdk_version: "1.44.1"
app_file: app.py
pinned: false
---

# Redrob AI — Candidate Ranker Submission

Ranks a pool of 100,000 candidate profiles against the role : **Senior AI Engineer, Founding Team @ Redrob AI** job description and returns a top-100 shortlist as a CSV.


## Running the pipeline

Produce the top-100 submission from the candidate pool with a single command:

```bash
pip install -r requirements.txt
python rank.py --candidates challenge_dataset/candidates.jsonl --out submission.csv
```

This runs the whole pipeline end-to-end — streaming read → candidate filter → scoring →
honeypot veto → ranking → CSV write — and logs a `TOTAL end-to-end pipeline time` line at the
end (currently ~2–3 s on the full 100K pool, far under the 5-minute budget). Every run also
automatically:

- archives the output to `submissions/csv/submission_<ts>.csv`
- diffs it against the previous run → `submissions/diffs/diff_<ts>.txt`
- scores it against the local eval set, logging the metrics and the delta vs baseline, and saves `evals/runs/eval_<ts>.json`
- writes a full run log to `logs/pipeline_<ts>.log`

Validate the CSV against the official validator (should print **Submission is valid.**):

```bash
python data/validate_submission.py submission.csv
```

Useful flags: `--verbose` (print the top 20), `--skip-eval` (skip the auto-eval),
`--labels <path>` (different eval label set), `--top N` (shortlist size, default 100).


## Project layout

```
rank.py                    # CLI entry point — orchestrates the full pipeline
diff_submissions.py        # compares two submission CSVs (rank/score deltas); auto-run after every rank.py call
requirements.txt           # stdlib only for rank.py; streamlit/pandas for app.py; pytest for the test suite
submission_metadata.yaml   # fill in before submitting
src/
  io_utils.py             # streaming JSONL (.gz transparent) reader + spec-safe CSV writer
  jd.py                   # encoded JD knowledge: title tiers, skill vocab, geo, exp band
  text.py                 # candidate text blob builder (semantic seam for human's LM step)
  candidate_filter.py     # pre-filter: drops consulting-only and fictional-company profiles
  features.py             # rule-based scoring components (title, skill, experience, location)
  behavioral.py           # availability multiplier; handles -1 sentinels as "no data"
  honeypot.py             # logical-consistency veto for impossible profiles
  score.py                # composite fusion with optional `semantic` seam
  reasoning.py            # deterministic, field-grounded reasoning string generator
  log_config.py           # sets up the shared "pipeline" logger (console + file handlers)
tests/
  conftest.py               # shared candidate fixtures used across test files
  test_io_utils.py          # streaming reader, gzip handling, CSV writer
  test_candidate_filter.py  # consulting-only / fictional-company filtering
  test_features.py          # title, skill, experience, location scoring
  test_behavioral.py        # recency + availability multiplier
  test_honeypot.py          # logical-consistency checks
  test_score.py             # composite_score structure, bounds, honeypot sentinel
  test_reasoning.py         # reasoning string generation
  test_pipeline_e2e.py      # full pipeline run against fixture JSONL, end to end
logs/
  pipeline_<timestamp>.log  # one file per rank.py run (gitignored, regenerated each run)
  sample_pipeline.log       # example of what a run log looks like (committed)
submissions/
  csv/
    submission_<timestamp>.csv  # archived copy of every rank.py output (gitignored)
    sample_submission.csv       # example of the CSV format (committed)
  diffs/
    diff_<timestamp>.txt        # auto-generated diff vs. the immediately preceding run. (gitignored)
    sample_diff.txt             # example diff report (committed)
evals/
  labels.csv                # human-verified relevance labels (tier 0-5) — the eval answer key
  evaluate.py               # scores a submission vs labels: NDCG@10/50, MAP, P@10, composite
  baseline.json             # stored reference score to compare each run against
  make_label_worksheet.py   # stratified sampler that builds the labeling worksheet
  runs/
    eval_<timestamp>.json   # metrics for each rank.py run (auto-saved)
challenge_dataset/
  candidates.jsonl        # 100K candidate profiles (not committed — too large)
  sample_candidates.json  # ~50 candidate sample for fast testing
  validate_submission.py  # official validator
  ...
```

### `diff_submissions.py`

Compares two submission CSVs and reports how rankings shifted: candidates that entered or
dropped out of the top-N, moved up/down in rank, or kept their rank but changed score. It can
be run standalone:

```bash
python diff_submissions.py submissions/csv/submission_A.csv submissions/csv/submission_B.csv
```

or imported and called programmatically via `diff_to_string(old_path, new_path) -> str`. `rank.py`
calls this automatically after every run (see `submissions/` below), so you don't normally need
to invoke it by hand — it's most useful for diffing two arbitrary runs after the fact.

### `tests/`

A pytest suite covering every pure function in `src/` individually, plus a `test_pipeline_e2e.py`
integration test that runs the whole pipeline against fixture JSONL data. Shared candidate
fixtures (clean, consulting-only, fictional-company, honeypot, etc.) live in `conftest.py` so
each test file isn't redefining the same sample data. Run with:

```bash
pip install -r requirements.txt
pytest tests/ -v
```

### `logs/`

Every `rank.py` run creates its own timestamped log file here (`pipeline_<timestamp>.log`) via
`src/log_config.py`, capturing every pipeline checkpoint — stream-open, candidate-filter counts,
scoring/honeypot stats, ranking, and output — at `INFO`/`WARNING` level, plus inline
`[CHECK PASS]`/`[CHECK FAIL]` assertions for sanity-checking the run as it happens. Real run logs
are gitignored; `sample_pipeline.log` is committed so reviewers can see the expected format
without running the pipeline.

### `submissions/`

Every `rank.py` run archives its output CSV into `submissions/csv/submission_<timestamp>.csv`,
and — if a prior run exists — automatically diffs the new run against its immediate predecessor
via `diff_submissions.py`, saving the report to `submissions/diffs/diff_<timestamp>.txt`. This
makes it easy to see how the ranking evolves as the scoring logic is tuned. Generated CSVs and
diffs are gitignored; `sample_submission.csv` and `sample_diff.txt` are committed as format
examples.

### `evals/`

A local evaluation harness — a private proxy for the hidden leaderboard. `evaluate.py` scores a
submission against `labels.csv` (60 hand-verified candidates tiered 0–5) using the organizers'
exact formula (`0.50·NDCG@10 + 0.30·NDCG@50 + 0.15·MAP + 0.05·P@10`), and reports label coverage
and honeypot leakage. `rank.py` runs this automatically after every ranking, logs the metrics and
the delta vs `baseline.json`, and archives the result to `evals/runs/eval_<timestamp>.json`. Use it
to tell — with a number, not a guess — whether a scoring change helped. See `evals/README.md` for
the tier rubric and caveats.

Run it standalone against any submission:

```bash
python evals/evaluate.py --submission submission.csv --labels evals/labels.csv
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
