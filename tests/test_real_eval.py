"""Real-data eval (eval/real): graph shape, no leakage, BKT, and root_cause agreeing with production Cypher.

These run on synthetic histories, never on the Eedi data (which may not be present).
"""

from eval.real.graph import Graph, edges, is_acyclic


def test_reviewed_graphs_are_acyclic():
    assert len(edges("primary")) == 9 and is_acyclic(edges("primary"))
    assert len(edges("sensitivity")) == 12 and is_acyclic(edges("sensitivity"))
    assert not is_acyclic(edges("primary") + [(226, 227), (227, 226)])


def test_primary_graph_matches_the_edge_review():
    g = Graph("primary")
    assert g.root_candidates == [204, 219, 220, 226]
    assert g.prereqs[230] == {220: 1, 226: 1, 204: 2}
    assert g.dependents[204] == {219, 220, 226, 227, 228, 230}
