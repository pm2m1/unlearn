"""Local 384-dim sentence embeddings (all-MiniLM-L6-v2 on CPU)."""

from functools import lru_cache

MODEL = "sentence-transformers/all-MiniLM-L6-v2"
DIM = 384


@lru_cache(maxsize=1)
def _model():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(MODEL, device="cpu")


def embed(texts: list[str]) -> list[list[float]]:
    vectors = _model().encode(texts, batch_size=64, normalize_embeddings=True, show_progress_bar=False)
    return [v.tolist() for v in vectors]
