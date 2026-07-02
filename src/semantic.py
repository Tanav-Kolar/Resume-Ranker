import numpy as np


def load_semantic_scores(
    query_path: str = "artifacts/query_vectors.npz",
    chunks_path: str = "artifacts/candidate_chunks.npz",
) -> dict[str, float]:
    qz = np.load(query_path, allow_pickle=True)
    Q = qz["Q"].astype(np.float32)          # (n_arch, d)
    weights = qz["weights"].astype(np.float32)  # (n_arch,)
    mode = str(qz["mode"])

    cz = np.load(chunks_path, allow_pickle=True)
    ids = cz["ids"]          # (N,) str
    chunks = cz["chunks"].astype(np.float32)  # (M, d)
    offsets = cz["offsets"]  # (N+1,) int

    # (M, n_arch) cosines — both sides already L2-normalized, so dot == cosine
    sims = chunks @ Q.T

    raw = np.empty(len(ids), dtype=np.float32)
    for i in range(len(ids)):
        block = sims[offsets[i]:offsets[i + 1]]  # (k, n_arch)
        if block.shape[0] == 0:
            raw[i] = 0.0
            continue
        per_arch = block.max(axis=0)  # best chunk per archetype -> (n_arch,)
        weighted = weights * per_arch
        raw[i] = weighted.max() if mode == "max" else weighted.sum()

    lo, hi = raw.min(), raw.max()
    if hi > lo:
        normalized = (raw - lo) / (hi - lo)
    else:
        normalized = np.zeros_like(raw)

    return {str(ids[i]): float(normalized[i]) for i in range(len(ids))}
