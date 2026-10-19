"""The vector index must give exact nearest neighbours, not approximate ones.

FalkorDB's vector index is HNSW. With its default search width two graphs with identical content returned different
top-10 neighbours for 1 query in 5, so the eval's recall judge and A/B retrieval depended on how the index happened
to be built. CLASS_INDEXES sets efRuntime to at least the number of vectors, which makes search exact. These tests
build a fresh index (vectors inserted in a shuffled order) and check 200 fixed queries against brute-force cosine.
"""

import random
import re

import numpy as np
import pytest

from unlearn import queries as Q
from unlearn.db import create_indexes, delete_graph, run, run_batched

N_QUERIES, K = 200, 10
TEMPLATE = "class_template"


def template_vectors() -> tuple[list[int], np.ndarray]:
    rows, _ = run(TEMPLATE, "MATCH (m:Misconception) WHERE m.embedding IS NOT NULL "
                            "RETURN m.id AS id, m.embedding AS v ORDER BY m.id", read_only=True)
    return [r["id"] for r in rows], np.array([r["v"] for r in rows], dtype=np.float64)


def fixed_queries(vectors: np.ndarray) -> list[list[float]]:
    """200 queries that sit between two misconceptions, like a real explanation or opening would."""
    rng = random.Random(20261019)
    out = []
    for _ in range(N_QUERIES):
        a, b = rng.sample(range(len(vectors)), 2)
        noise = np.array([rng.gauss(0, 0.02) for _ in range(vectors.shape[1])])
        out.append((vectors[a] + vectors[b] + noise).tolist())
    return out


def exact_top_k(ids: list[int], vectors: np.ndarray, q: list[float], k: int = K) -> list[int]:
    v = np.asarray(q, dtype=np.float64)
    dist = 1 - (vectors @ v) / (np.linalg.norm(vectors, axis=1) * np.linalg.norm(v))
    return [ids[i] for i in np.argsort(dist, kind="stable")[:k]]


def mismatches(graph: str, ids: list[int], vectors: np.ndarray) -> list[str]:
    bad = []
    for i, q in enumerate(fixed_queries(vectors)):
        got = [r["id"] for r in run(graph, Q.NEAREST_MISCONCEPTIONS, {"v": q, "k": K}, read_only=True)[0]]
        want = exact_top_k(ids, vectors, q)
        if got != want:
            bad.append(f"query {i}: index {got} != exact {want}")
    return bad


def test_ef_runtime_covers_every_vector():
    ef = int(re.search(r"efRuntime:(\d+)", Q.CLASS_INDEXES[-1]).group(1))
    ids, _ = template_vectors()
    assert ef >= len(ids) > 0, f"efRuntime {ef} < {len(ids)} vectors: vector search would be approximate"


def test_a_freshly_built_index_is_exact():
    ids, vectors = template_vectors()
    g = "class_pytest_vector_exact"
    delete_graph(g)
    create_indexes(g, Q.CLASS_INDEXES)
    order = list(range(len(ids)))
    random.Random(7).shuffle(order)  # a different insertion order from the template's
    run_batched(g, "UNWIND $rows AS r CREATE (:Misconception {id: r.id, embedding: vecf32(r.v)})",
                [{"id": ids[i], "v": vectors[i].tolist()} for i in order], batch_size=100)
    try:
        bad = mismatches(g, ids, vectors)
    finally:
        delete_graph(g)
    assert not bad, f"vector index is NOT exact on a fresh build: {len(bad)}/{N_QUERIES} queries differ, e.g. {bad[:3]}"


@pytest.mark.parametrize("graph", [TEMPLATE])
def test_the_graph_the_eval_reads_is_exact(graph):
    ids, vectors = template_vectors()
    bad = mismatches(graph, ids, vectors)
    assert not bad, (f"vector index of {graph} is NOT exact: {len(bad)}/{N_QUERIES} queries differ, e.g. {bad[:3]} "
                     "(an index built before efRuntime was set: rebuild with make seed)")
