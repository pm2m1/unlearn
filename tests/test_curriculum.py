"""The curriculum graph matches the Eedi CSVs (counts verified against data/raw/ at HF commit 2ae0839d)."""

import pytest

from unlearn import queries as Q
from unlearn.db import run

GRAPH = "curriculum"


@pytest.fixture(scope="module")
def labels():
    rows, _ = run(GRAPH, Q.COUNT_NODES_BY_LABEL)
    return {r["label"]: r["n"] for r in rows}


def test_misconception_nodes(labels):
    assert labels["Misconception"] == 8117


def test_construct_nodes(labels):
    assert labels["Construct"] == 2258


def test_subjects(labels):
    assert labels["Subject"] == 4


def test_seen_in_edges():
    rows, _ = run(GRAPH, Q.COUNT_SEEN_IN)
    assert rows[0]["n"] == 19294


def test_seen_in_pct_sums_to_100():
    rows, _ = run(GRAPH, Q.SEEN_IN_PCT_SUMS)
    assert rows[0]["min_total"] == pytest.approx(100, abs=0.05)
    assert rows[0]["max_total"] == pytest.approx(100, abs=0.05)


def test_shares_misconception_both_directions():
    rows, _ = run(GRAPH, Q.COUNT_SHARES_MISCONCEPTION)
    assert rows[0]["n"] > 0 and rows[0]["min_n"] >= 2
    rows, _ = run(GRAPH, Q.ASYMMETRIC_SHARES_MISCONCEPTION)
    assert rows[0]["n"] == 0


def test_receipt_shape():
    rows, receipt = run(GRAPH, Q.COUNT_SEEN_IN)
    assert set(receipt) == {"cypher", "params", "rows"}
    assert receipt["rows"] == rows
