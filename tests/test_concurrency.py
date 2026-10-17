"""The concurrency demo runs end to end (small sizes) and reports every condition."""

import json

from eval import concurrency
from unlearn.db import list_graphs


def test_concurrency_demo_small(monkeypatch, tmp_path):
    monkeypatch.setattr(concurrency, "OUT", tmp_path / "concurrency.json")
    monkeypatch.setattr(concurrency, "PROBES", 15)
    monkeypatch.setattr(concurrency, "HEAVY_ROWS", 500)
    assert concurrency.main(["--students", "3", "--rounds", "2"]) == 0
    r = json.loads((tmp_path / "concurrency.json").read_text())
    assert set(r["per_graph"]) == set(concurrency.GRAPHS)
    for k in ("baseline", "load_on_other_graph", "load_on_same_graph", "sessions_on_other_graph", "sessions_on_same_graph"):
        assert r["isolation"][k]["n"] == 15
    assert not set(concurrency.GRAPHS) & set(list_graphs())  # cleaned up
