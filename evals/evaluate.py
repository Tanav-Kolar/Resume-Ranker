"""
Local eval harness — a private proxy for the hidden leaderboard.

Scores a submission CSV against evals/labels.csv using the SAME formula the
organizers use:  composite = 0.50*NDCG@10 + 0.30*NDCG@50 + 0.15*MAP + 0.05*P@10
("relevant" = tier >= 3, matching the spec's P@k threshold).

Also reports:
  - labeled_coverage: how many of the top-k are labeled (trust gauge — a metric
    over few labeled rows is noisy).
  - tier0_in_top{10,50,100}: known honeypots/non-fits leaking into the top
    (the Stage-3 disqualifier guardrail).

Labels are a ~60-candidate proxy, not the hidden ground truth: use the composite
for RELATIVE comparison (before vs after a change), not as an absolute prediction.

Usage:
    python evals/evaluate.py --submission submission.csv --labels evals/labels.csv
    python evals/evaluate.py --submission submission.csv --labels evals/labels.csv --json evals/baseline.json
"""
from __future__ import annotations
import argparse, csv, json, math, time

REL_THRESHOLD = 3  # tier >= 3 counts as "relevant" (per submission_spec P@k)


def load_labels(path):
    labels = {}
    with open(path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            labels[row["candidate_id"].strip()] = int(row["tier"])
    return labels


def load_ranked(path):
    rows = []
    with open(path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows.append((int(row["rank"]), row["candidate_id"].strip()))
    rows.sort()
    return [cid for _, cid in rows]


def _dcg(gains):
    return sum(g / math.log2(i + 2) for i, g in enumerate(gains))


def ndcg_at_k(ranked, labels, k):
    gains = [labels.get(cid, 0) for cid in ranked[:k]]
    ideal = sorted(labels.values(), reverse=True)[:k]
    idcg = _dcg(ideal)
    return _dcg(gains) / idcg if idcg > 0 else 0.0


def precision_at_k(ranked, labels, k):
    return sum(1 for cid in ranked[:k] if labels.get(cid, 0) >= REL_THRESHOLD) / k


def mean_avg_precision(ranked, labels):
    total_rel = sum(1 for t in labels.values() if t >= REL_THRESHOLD)
    if total_rel == 0:
        return 0.0
    hits, ap = 0, 0.0
    for i, cid in enumerate(ranked, start=1):
        if labels.get(cid, 0) >= REL_THRESHOLD:
            hits += 1
            ap += hits / i
    return ap / total_rel


def coverage(ranked, labels, k):
    return sum(1 for cid in ranked[:k] if cid in labels)


def tier0_in(ranked, labels, k):
    return sum(1 for cid in ranked[:k] if labels.get(cid, -1) == 0)


def evaluate(submission, labels_path):
    labels = load_labels(labels_path)
    ranked = load_ranked(submission)
    n10, n50 = ndcg_at_k(ranked, labels, 10), ndcg_at_k(ranked, labels, 50)
    mapv, p10 = mean_avg_precision(ranked, labels), precision_at_k(ranked, labels, 10)
    composite = 0.50 * n10 + 0.30 * n50 + 0.15 * mapv + 0.05 * p10
    return {
        "submission": submission,
        "labels": labels_path,
        "n_labels": len(labels),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "NDCG@10": round(n10, 4),
        "NDCG@50": round(n50, 4),
        "MAP": round(mapv, 4),
        "P@10": round(p10, 4),
        "composite": round(composite, 4),
        "labeled_coverage": {"top10": coverage(ranked, labels, 10),
                             "top50": coverage(ranked, labels, 50),
                             "top100": coverage(ranked, labels, 100)},
        "tier0_in_top": {"top10": tier0_in(ranked, labels, 10),
                         "top50": tier0_in(ranked, labels, 50),
                         "top100": tier0_in(ranked, labels, 100)},
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--submission", required=True)
    ap.add_argument("--labels", default="evals/labels.csv")
    ap.add_argument("--json", help="write metrics to this JSON path")
    args = ap.parse_args()

    r = evaluate(args.submission, args.labels)
    print(f"Eval of {r['submission']}  vs {r['labels']} ({r['n_labels']} labels)  {r['timestamp']}")
    print(f"  NDCG@10 = {r['NDCG@10']:.4f}   NDCG@50 = {r['NDCG@50']:.4f}   "
          f"MAP = {r['MAP']:.4f}   P@10 = {r['P@10']:.4f}")
    print(f"  COMPOSITE (proxy) = {r['composite']:.4f}")
    print(f"  labeled coverage  top10={r['labeled_coverage']['top10']}/10  "
          f"top50={r['labeled_coverage']['top50']}/50  "
          f"top100={r['labeled_coverage']['top100']}/100")
    print(f"  tier-0 (honeypot/non-fit) in  top10={r['tier0_in_top']['top10']}  "
          f"top50={r['tier0_in_top']['top50']}  top100={r['tier0_in_top']['top100']}")
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(r, f, indent=2)
        print(f"  -> wrote {args.json}")


if __name__ == "__main__":
    main()
