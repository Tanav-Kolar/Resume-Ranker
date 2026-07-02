#!/usr/bin/env python3
"""
Offline precompute step — run once (needs network to download the model).

Produces:
  artifacts/query_vectors.npz   — HyDE archetype embeddings (~6 KB, commit this)
  artifacts/candidate_chunks.npz — candidate chunk embeddings (~40-60 MB, gitignored)

Usage:
    pip install fastembed
    python scripts/precompute_embeddings.py
"""

import json
import sys
import time
from pathlib import Path

import numpy as np

# Allow running from repo root without installing the package.
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastembed import TextEmbedding
from src.hyde_profiles import HYDE_PROFILES, AGG_MODE
from src.candidate_filter import is_clean

CANDIDATES_PATH = Path("challenge_dataset/candidates.jsonl")
ARTIFACTS_DIR = Path("artifacts")
MODEL_NAME = "BAAI/bge-small-en-v1.5"


def l2_normalize(x: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(x, axis=1, keepdims=True)
    norms = np.maximum(norms, 1e-12)
    return x / norms


def main() -> None:
    t0 = time.time()
    ARTIFACTS_DIR.mkdir(exist_ok=True)

    print(f"Loading model {MODEL_NAME} ...")
    model = TextEmbedding(MODEL_NAME)

    # --- Query vectors (archetype profiles) ---
    print(f"Embedding {len(HYDE_PROFILES)} HyDE archetype profiles ...")
    profile_texts = [p["text"] for p in HYDE_PROFILES]
    Q_list = list(model.embed(profile_texts))
    Q = l2_normalize(np.array(Q_list, dtype=np.float32))

    names = np.array([p["name"] for p in HYDE_PROFILES])
    weights = np.array([p["weight"] for p in HYDE_PROFILES], dtype=np.float32)

    np.savez(
        ARTIFACTS_DIR / "query_vectors.npz",
        Q=Q,
        names=names,
        weights=weights,
        mode=np.str_(AGG_MODE),
    )
    print(f"  Saved query_vectors.npz  shape={Q.shape}")

    # --- Candidate chunks ---
    print(f"Streaming candidates from {CANDIDATES_PATH} ...")
    all_ids: list[str] = []
    all_texts: list[str] = []
    offsets: list[int] = [0]

    with open(CANDIDATES_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            c = json.loads(line)
            if not is_clean(c):
                continue

            cid = c.get("candidate_id", "")
            chunks: list[str] = []

            profile = c.get("profile", {})
            summary = (profile.get("summary") or "").strip()
            if summary:
                chunks.append(summary)

            for entry in c.get("career_history", []):
                desc = (entry.get("description") or "").strip()
                if desc:
                    chunks.append(desc)

            if not chunks:
                continue

            all_ids.append(cid)
            all_texts.extend(chunks)
            offsets.append(len(all_texts))

    n_candidates = len(all_ids)
    n_chunks = len(all_texts)
    print(f"  {n_candidates:,} clean candidates, {n_chunks:,} chunks total")

    print("Embedding candidate chunks (this may take 1-3 min) ...")
    chunk_vecs = list(model.embed(all_texts))
    chunks_arr = l2_normalize(np.array(chunk_vecs, dtype=np.float32))

    np.savez(
        ARTIFACTS_DIR / "candidate_chunks.npz",
        ids=np.array(all_ids),
        chunks=chunks_arr,
        offsets=np.array(offsets, dtype=np.int64),
    )
    elapsed = time.time() - t0
    print(f"  Saved candidate_chunks.npz  shape={chunks_arr.shape}")
    print(f"Done in {elapsed:.1f}s")


if __name__ == "__main__":
    main()
