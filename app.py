"""
Streamlit web interface for the Redrob Candidate Ranker.
Deployed on HuggingFace Spaces (CPU-only, free tier, sdk: streamlit).

Accepts a JSONL or JSON candidate file (<=100 candidates), runs the
rule-based ranker end-to-end, and returns a downloadable ranked CSV.
"""

import csv
import io
import json
import os
import sys
import time

import streamlit as st

# Make src/ importable whether running locally or on HF Spaces
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.score import composite_score
from src.reasoning import build_reasoning
from src.candidate_filter import filter_candidates

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SAMPLE_PATHS = [
    "sample_candidates.json",
    "challenge_dataset/sample_candidates.json",
]


def _find_sample() -> str | None:
    for p in _SAMPLE_PATHS:
        if os.path.exists(p):
            return p
    return None


def _parse_candidates(text: str) -> list:
    """Parse JSONL text or a JSON array into a list of candidate dicts."""
    text = text.strip()
    if not text:
        return []
    if text.startswith("["):
        try:
            data = json.loads(text)
            return data if isinstance(data, list) else [data]
        except json.JSONDecodeError:
            pass
    candidates = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            candidates.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return candidates


def _score_and_rank(candidates: list, top_n: int) -> tuple:
    """Score all candidates and return (rows, n_honeypots, n_filtered, elapsed_s)."""
    t0 = time.time()
    scored = []
    n_honeypot = 0
    n_total = len(candidates)

    for c in filter_candidates(candidates):
        result = composite_score(c)
        if result["honeypot_reasons"]:
            n_honeypot += 1
        scored.append((result["score"], c.get("candidate_id", ""), result, c))

    # Sort: score desc, candidate_id asc for ties (spec §3)
    scored.sort(key=lambda x: (-x[0], x[1]))

    rows = []
    for rank, (score, cid, result, candidate) in enumerate(scored[:top_n], 1):
        reasoning = build_reasoning(candidate, result)
        rows.append({
            "candidate_id": cid,
            "rank": rank,
            "score": round(score, 6),
            "reasoning": reasoning,
        })

    n_filtered = n_total - len(scored)
    return rows, n_honeypot, n_filtered, time.time() - t0


def _build_csv(rows: list) -> bytes:
    """Serialize ranked rows to a UTF-8 CSV byte string for download."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["candidate_id", "rank", "score", "reasoning"])
    for r in rows:
        reasoning = r["reasoning"].replace("\n", " ").replace("\r", " ")
        writer.writerow([r["candidate_id"], r["rank"], f"{r['score']:.6f}", reasoning])
    return buf.getvalue().encode("utf-8")


# ---------------------------------------------------------------------------
# Streamlit UI
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Redrob Candidate Ranker",
    page_icon="🎯",
    layout="wide",
)

st.title("🎯 Redrob Candidate Ranker")
st.caption("Senior AI Engineer, Founding Team @ Redrob AI")

st.markdown("""
Rule-based ranker — **CPU-only · no network · no LLM**.
Upload a `.jsonl` or `.json` file (≤ 100 candidates) or use the built-in sample.
Scores every candidate using title fit, skill relevance, experience, location, and a
behavioral multiplier, then vetoes honeypot profiles.
""")

st.divider()

# --- Sidebar controls ---
with st.sidebar:
    st.header("⚙️ Controls")

    use_sample = st.checkbox("Use built-in sample (50 candidates)", value=True)

    uploaded = st.file_uploader(
        "Or upload a candidates file (.jsonl / .json)",
        type=["jsonl", "json"],
        disabled=use_sample,
    )

    top_n = st.slider("Top-N candidates to return", min_value=1, max_value=100, value=50)

    run_btn = st.button("▶  Run Ranker", type="primary", use_container_width=True)


# --- Main panel ---
if run_btn:
    # Load candidates
    if use_sample or uploaded is None:
        sample_path = _find_sample()
        if sample_path is None:
            st.error("Built-in sample not found. Please upload a JSONL file.")
            st.stop()
        raw = open(sample_path, encoding="utf-8").read()
        source = f"built-in sample (`{sample_path}`)"
    else:
        raw = uploaded.read().decode("utf-8")
        source = f"uploaded file `{uploaded.name}`"

    candidates = _parse_candidates(raw)
    if not candidates:
        st.error("No valid candidate records found in the file.")
        st.stop()

    original_count = len(candidates)
    if len(candidates) > 100:
        candidates = candidates[:100]
        st.warning(
            f"Sandbox limit: using first 100 of {original_count} candidates. "
            "Full 100K reproduction runs locally via `python rank.py ...`"
        )

    top_n = min(top_n, len(candidates))

    # Score
    with st.spinner(f"Scoring {len(candidates)} candidates..."):
        rows, n_honeypot, n_filtered, elapsed = _score_and_rank(candidates, top_n)

    # Stats
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Candidates loaded", len(candidates))
    col2.metric("Filtered out", n_filtered)
    col3.metric("Top-N returned", len(rows))
    col4.metric("Honeypots detected", n_honeypot)
    col5.metric("Runtime", f"{elapsed:.2f}s")

    st.success(f"Ranked {len(rows)} candidates from {source} in {elapsed:.2f}s.")

    # Download button
    csv_bytes = _build_csv(rows)
    st.download_button(
        label="⬇️  Download ranked CSV",
        data=csv_bytes,
        file_name="submission.csv",
        mime="text/csv",
        type="primary",
    )

    st.divider()

    # Results table
    st.subheader(f"Top {len(rows)} candidates")

    import pandas as pd
    df = pd.DataFrame(rows)[["rank", "candidate_id", "score", "reasoning"]]
    df.columns = ["Rank", "Candidate ID", "Score", "Reasoning"]
    st.markdown(
        """
        <div style="overflow-x: auto; max-height: 500px; overflow-y: auto;">
        """
        + df.to_html(index=False, escape=True)
        + """
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Score distribution chart
    st.subheader("Score distribution")
    score_df = pd.DataFrame({"Rank": df["Rank"], "Score": df["Score"]})
    st.line_chart(score_df.set_index("Rank")["Score"])

else:
    st.info(
        "👈 Configure the controls in the sidebar and click **Run Ranker** to start."
    )
    st.markdown("""
    **Reproduce locally (full 100K pool):**
    ```bash
    python rank.py --candidates ./challenge_dataset/candidates.jsonl --out ./submission.csv
    python data/validate_submission.py submission.csv
    ```
    Full run completes in ~4 seconds on a single CPU core.
    """)
