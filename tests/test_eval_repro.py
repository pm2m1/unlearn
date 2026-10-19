"""Eval reproducibility: the graph fingerprint, the number diff behind `make eval-check`, and cache-only replies."""

import pytest

from eval.check import diff
from eval.provenance import graph_fingerprint, provenance
from unlearn import llm
from unlearn.db import delete_graph, recreate_graph, run


def test_the_fingerprint_is_stable_and_sees_any_change():
    g = "class_pytest_fingerprint"
    recreate_graph("class_template", g)
    try:
        a, b = graph_fingerprint("class_template"), graph_fingerprint(g)
        assert a["sha256"] == b["sha256"] and a["nodes"] == b["nodes"] > 0      # a copy is the same graph
        run(g, "MATCH (q:Question {id:'q-409-1'}) SET q.text = q.text + ' '")
        assert graph_fingerprint(g)["sha256"] != a["sha256"]                     # one changed character
        run(g, "MATCH (q:Question {id:'q-409-1'}) SET q.text = substring(q.text, 0, size(q.text) - 1)")
        assert graph_fingerprint(g)["sha256"] == a["sha256"]
        run(g, "MATCH (:Construct {id:409})-[r:REQUIRES]->(:Construct {id:408}) SET r.weight = 2")
        assert graph_fingerprint(g)["sha256"] != a["sha256"]                     # an edge property
    finally:
        delete_graph(g)


def test_provenance_records_commit_seeds_and_graph():
    p = provenance(["0", "1"])
    assert len(p["commit"]) == 40 and p["seeds"] == [0, 1] and len(p["graph"]["sha256"]) == 64


def test_the_check_diff_ignores_latency_only():
    committed = {"summary": {"top1": 0.48, "latency_p50_ms": 49.5}, "provenance": {"commit": "a"}, "rows": [1, 2]}
    same = {"summary": {"top1": 0.48, "latency_p50_ms": 52.1}, "provenance": {"commit": "b"}, "rows": [1, 2]}
    assert diff(committed, same) == []
    moved = {"summary": {"top1": 0.478, "latency_p50_ms": 49.5}, "provenance": {}, "rows": [1, 3]}
    assert diff(committed, moved) == ["/rows[1]: committed 2 -> re-run 3", "/summary/top1: committed 0.48 -> re-run 0.478"]


def test_cache_only_mode_never_calls_a_model(monkeypatch, tmp_path):
    monkeypatch.setattr(llm, "CACHE_DIR", tmp_path)
    monkeypatch.setenv("UNLEARN_LLM_CACHE_ONLY", "1")
    with pytest.raises(llm.CacheMiss):
        llm.complete(llm.ollama_provider("nope"), [{"role": "user", "content": "hi"}])
