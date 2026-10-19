"""Where an eval result came from: the git commit, the seeds, and a fingerprint of the graph it read.

Every eval reads class_template from the local FalkorDB, not from the commit, so the commit alone doesn't pin
a result: a template rebuilt from changed data gives different numbers on the same code. The fingerprint is a
SHA-256 over every node (labels and properties), every edge (type, properties and both endpoints) and every index
definition with its options, with floats rounded so it doesn't depend on how they print. The indexes count
because the vector index's search width decides whether nearest-neighbour results are exact
(queries.VECTOR_EF_RUNTIME). eval/check.py refuses to compare against a result whose fingerprint differs from the
graph it would read now.
"""

import hashlib
import json
import subprocess
import time
from pathlib import Path

from unlearn import queries as Q
from unlearn.db import run

ROOT = Path(__file__).resolve().parents[1]
GRAPH = "class_template"


def _canon(value):
    if isinstance(value, float):
        return round(value, 6)
    if isinstance(value, list):
        return [_canon(v) for v in value]
    if isinstance(value, dict):
        return {k: _canon(v) for k, v in sorted(value.items())}
    return value


def graph_fingerprint(graph: str = GRAPH) -> dict:
    nodes, _ = run(graph, Q.EVAL_GRAPH_NODES, read_only=True)
    edges, _ = run(graph, Q.EVAL_GRAPH_EDGES, read_only=True)
    indexes, _ = run(graph, Q.EVAL_GRAPH_INDEXES, read_only=True)
    key = {n["id"]: json.dumps([sorted(n["labels"]), _canon(n["props"])], sort_keys=True) for n in nodes}
    h = hashlib.sha256()
    for line in sorted(key.values()):
        h.update(line.encode() + b"\n")
    h.update(b"--edges--\n")
    for line in sorted(json.dumps([key[e["a"]], e["type"], _canon(e["props"]), key[e["b"]]], sort_keys=True)
                       for e in edges):
        h.update(line.encode() + b"\n")
    h.update(b"--indexes--\n")
    for ix in indexes:
        h.update(json.dumps(_canon(ix), sort_keys=True).encode() + b"\n")
    vector = [ix["options"] for ix in indexes if "VECTOR" in str(ix["types"])]
    return {"name": graph, "sha256": h.hexdigest(), "nodes": len(nodes), "edges": len(edges),
            "indexes": len(indexes), "vector_index_options": vector}


def git_state() -> dict:
    def git(*args):
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    # Result files themselves don't count as uncommitted code.
    dirty = git("status", "--porcelain", "--", ".", ":(exclude)eval/results")
    return {"commit": git("rev-parse", "HEAD"), "uncommitted_changes": bool(dirty)}


def provenance(seeds, graph: str = GRAPH) -> dict:
    return {**git_state(), "seeds": [int(s) for s in seeds], "graph": graph_fingerprint(graph),
            "run_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
