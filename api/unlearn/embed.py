"""Local 384-dim sentence embeddings: all-MiniLM-L6-v2 through fastembed (ONNX Runtime, CPU).

fastembed runs the same model as sentence-transformers without torch: on the 410 template misconceptions
the vectors match to cosine >= 0.9999998, so the vector index is unchanged, while the API image shrinks from
2.25 GB to ~0.9 GB and a single-sentence embed peaks at ~236 MiB instead of ~555 MiB (Phase 4 measurements).
"""

import os
import threading
from functools import lru_cache

import numpy as np

MODEL = "sentence-transformers/all-MiniLM-L6-v2"
DIM = 384
# Baked into the image at build time (api/Dockerfile); locally it defaults to the repo's .cache.
CACHE_DIR = os.getenv("FASTEMBED_CACHE_PATH", os.path.join(os.path.dirname(__file__), "..", "..", ".cache", "fastembed"))


# One embed at a time: concurrent ONNX Runtime calls each grow their own memory arena (12 parallel requests
# took the API from ~60 MiB to ~960 MiB); serialised, a one-sentence embed costs a few milliseconds.
_lock = threading.Lock()


@lru_cache(maxsize=1)
def _model():
    from fastembed import TextEmbedding

    return TextEmbedding(MODEL, cache_dir=CACHE_DIR)


def embed(texts: list[str]) -> list[list[float]]:
    with _lock:
        vectors = np.array(list(_model().embed(texts, batch_size=64)), dtype=np.float32)
    vectors /= np.linalg.norm(vectors, axis=1, keepdims=True)
    return vectors.tolist()
