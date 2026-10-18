"""Real-data eval (eval/real): graph shape, no leakage, BKT, metrics, and root_cause agreeing with production Cypher.

These run on synthetic histories, never on the Eedi data (which may not be present).
"""

import random

import numpy as np
import pandas as pd
import pytest
from sklearn.metrics import roc_auc_score

from eval.real import taskb
from eval.real.graph import Graph, edges, is_acyclic
from eval.real.metrics import AUC
from eval.real.models import (BKT, IDX, M0, M0b, GraphFeatures, GraphState, evidence, fit_bkt, root_cause_rows,
                              walk)
from unlearn import queries as Q
from unlearn.db import delete_graph, run, run_batched

SUBS = (204, 219, 220, 226, 227, 228, 230)
PARAMS = [(0.4, 0.15, 0.1, 0.25)] * 7


def test_reviewed_graphs_are_acyclic():
    assert len(edges("primary")) == 9 and is_acyclic(edges("primary"))
    assert len(edges("sensitivity")) == 12 and is_acyclic(edges("sensitivity"))
    assert not is_acyclic(edges("primary") + [(226, 227), (227, 226)])


def test_primary_graph_matches_the_edge_review():
    g = Graph("primary")
    assert g.root_candidates == [204, 219, 220, 226]
    assert g.prereqs[230] == {220: 1, 226: 1, 204: 2}
    assert g.dependents[204] == {219, 220, 226, 227, 228, 230}


def synthetic(n_students=6, n=30, seed=0) -> pd.DataFrame:
    """Answers with repeated timestamps (blocks of 1-4 answers), sorted like data.load()."""
    rng, rows, aid = random.Random(seed), [], 0
    for u in range(n_students):
        t, quiz = 1000, 0
        while sum(r["UserId"] == u for r in rows) < n:
            t += rng.choice([1, 1, 5, 60])
            quiz += 1
            for _ in range(rng.randint(1, 4)):
                aid += 1
                rows.append({"UserId": u, "ts": t, "AnswerId": rng.randint(1, 10**9), "QuizId": quiz,
                             "subtopic": rng.choice(SUBS), "QuestionId": rng.randint(1, 40),
                             "IsCorrect": rng.random() < 0.6})
    df = pd.DataFrame(rows).sort_values(["UserId", "ts", "AnswerId"]).reset_index(drop=True)
    df["IsCorrect"] = df.IsCorrect.astype(int)
    df["pq"] = 0.3 + 0.4 * (df.QuestionId % 5) / 4
    first = df.groupby(["UserId", "QuizId"]).ts.min().rename("q_ts").reset_index().sort_values(["UserId", "q_ts", "QuizId"])
    first["quiz_rank"] = first.groupby("UserId").cumcount()
    return df.merge(first[["UserId", "QuizId", "quiz_rank"]], on=["UserId", "QuizId"])


def models():
    g = Graph("primary")
    return {"M0": (M0(), 1), "M0b": (M0b([0.6] * 7), 1), "M1": (BKT(PARAMS), 1), "M3": (BKT(PARAMS, 0.5, g), 1),
            "M2 features": (GraphFeatures(g), 4), "M2 features (12 edges)": (GraphFeatures(Graph("sensitivity")), 4)}


@pytest.mark.parametrize("name", list(models()))
def test_no_prediction_sees_its_own_or_a_later_answer(name):
    """Flip every outcome at or after time t: predictions for answers at or before t must not change, including
    the other answers in t's block. (walk() also asserts the state is strictly older than each slice.)"""
    model, width = models()[name]
    df = synthetic()
    base = walk(df, model, width)
    for u in df.UserId.unique():
        for t in sorted(df.ts[df.UserId == u].unique()):
            flipped = df.copy()
            later = (flipped.UserId == u) & (flipped.ts >= t)
            flipped.loc[later, "IsCorrect"] = 1 - flipped.loc[later, "IsCorrect"]
            new = walk(flipped, model, width)
            upto = ((df.UserId == u) & (df.ts <= t)).to_numpy() | (df.UserId != u).to_numpy()
            np.testing.assert_array_equal(base[upto], new[upto])


def test_walk_refuses_an_unsorted_history():
    df = synthetic(n_students=1).iloc[::-1].reset_index(drop=True)
    with pytest.raises(AssertionError, match="leak"):
        walk(df, M0b([0.6] * 7))


def test_bkt_matches_a_hand_computed_example():
    """L0 0.5, T 0.2, S 0.1, G 0.3. Two answers at ts 1 (right, right are both predicted from the prior), one at ts 2.
    P(c) = 0.5*0.9 + 0.5*0.3 = 0.6. After a right: 0.45/0.6 = 0.75, then 0.75 + 0.25*0.2 = 0.8; after a second right:
    0.72/0.78 = 0.923077, then + 0.076923*0.2 = 0.938462; P(c) at ts 2 = 0.938462*0.9 + 0.061538*0.3 = 0.863077."""
    df = pd.DataFrame({"UserId": [1, 1, 1], "ts": [1, 1, 2], "AnswerId": [1, 2, 3], "subtopic": [230] * 3,
                       "pq": [0.5] * 3, "IsCorrect": [1, 1, 0]})
    p = walk(df, BKT([(0.5, 0.2, 0.1, 0.3)] * 7))
    np.testing.assert_allclose(p, [0.6, 0.6, 0.863077], atol=1e-6)
    st = BKT([(0.5, 0.2, 0.1, 0.3)] * 7).new_state()
    BKT([(0.5, 0.2, 0.1, 0.3)] * 7).update(st, [IDX[230]], [0])  # wrong: 0.05/0.4 = 0.125, + 0.875*0.2 = 0.3
    assert st["pL"][IDX[230]] == pytest.approx(0.3)


def test_bkt_em_recovers_known_parameters():
    rng = np.random.default_rng(0)
    L0, T, S, G = 0.3, 0.15, 0.1, 0.25
    seqs = []
    for _ in range(4000):
        known, s = rng.random() < L0, []
        for _ in range(15):
            s.append(int(rng.random() < (1 - S if known else G)))
            known = known or rng.random() < T
        seqs.append(np.array(s))
    fit = fit_bkt(seqs)
    np.testing.assert_allclose(fit["params"], (L0, T, S, G), atol=0.03)
    assert all(b >= a - 1e-6 for a, b in zip(fit["loglik"], fit["loglik"][1:]))  # EM never lowers the likelihood


def test_mastery_and_evidence_follow_production():
    assert evidence(0) == 0 and evidence(1) == 0.5 and evidence(2) == 1.5  # count x (1 - 0.5^count)
    gs = GraphState()
    for c in (0, 1, 1):  # one wrong (confidence 0.5 <= 0.6), then two right: mastered
        gs.record(IDX[219], c)
    for c in (0, 0, 1, 1):  # two wrong (0.75 > 0.6): never mastered
        gs.record(IDX[220], c)
    gs.record(IDX[219], 0)
    gs.record(IDX[219], 0)  # mastery is permanent
    assert gs.mastered[IDX[219]] and not gs.mastered[IDX[220]]


def test_weighted_auc_matches_sklearn():
    rng = np.random.default_rng(0)
    y, s = rng.integers(0, 2, 500), np.round(rng.random(500), 2)  # rounded, so there are ties
    w = rng.integers(0, 4, 500).astype(float)
    assert AUC(s, y)(np.ones(500)) == pytest.approx(roc_auc_score(y, s))
    assert AUC(s, y)(w) == pytest.approx(roc_auc_score(y, s, sample_weight=w))


def test_task_b_window_is_first_quizzes_until_k():
    rows = {"quiz_rank": np.array([0, 0, 0, 1, 1, 2, 2, 2]), "ts": np.array([1, 1, 1, 5, 5, 9, 9, 9])}
    win, later = taskb.split_window(rows, 5)
    assert win.tolist() == [True] * 5 + [False] * 3 and later.tolist() == [False] * 5 + [True] * 3


def test_root_cause_matches_the_production_cypher():
    """The Python root_cause on the SubTopic graph returns what production ROOT_CAUSE returns on FalkorDB for
    the same history: one stand-in misconception per SubTopic (SEEN_IN w = 1), SHOWED via UPDATE_SHOWED, MASTERED
    via MARK_MASTERED."""
    name, g, rng = "real_eval_pytest", Graph("primary"), random.Random(1)
    delete_graph(name)
    try:
        run_batched(name, Q.LOAD_HIERARCHY, [{"subject_id": 1, "subject": "Number", "topic_id": 2, "topic": "Fractions",
                                              "subtopic_id": 3, "subtopic": "SubTopics", "construct_id": s,
                                              "construct": f"SubTopic {s}"} for s in SUBS])
        run_batched(name, Q.LOAD_MISCONCEPTIONS, [{"mid": 9000 + s, "mname": f"wrong on {s}", "cid": s, "pct": 100.0}
                                                  for s in SUBS])
        run(name, Q.SET_SEEN_IN_WEIGHTS)
        run_batched(name, Q.LOAD_REQUIRES, [{"construct_id": a, "prereq_id": b, "note": "", "confidence": "high"}
                                            for a, b in g.edges])
        students = [f"s{i}" for i in range(40)]
        run_batched(name, Q.LOAD_STUDENTS, [{"id": s, "alias": s} for s in students])
        checked = 0
        for sid in students:
            gs = GraphState()
            for ts in range(rng.randint(3, 25)):
                x, c = rng.choice(SUBS), int(rng.random() < 0.5)
                gs.record(IDX[x], c)
                if not c:
                    run(name, Q.UPDATE_SHOWED, {"sid": sid, "mid": 9000 + x, "ts": ts})
            for x in SUBS:
                if gs.mastered[IDX[x]]:
                    run(name, Q.MARK_MASTERED, {"sid": sid, "cid": x, "ts": 0, "evidence": "test"})
            for t in SUBS:
                cy = [(r["id"], r["depth"], r["evidence"]) for r in run(name, Q.ROOT_CAUSE, {"sid": sid, "cid": t})[0]]
                py = root_cause_rows(gs, g, t)
                assert len(cy) == min(3, len(py))
                for (cid, d, ev), (_, pd_, pev) in zip(cy, py):
                    assert (d, pytest.approx(ev)) == (pd_, pev)
                    assert (cid, d, pytest.approx(ev)) in [(p, dd, pytest.approx(e)) for p, dd, e in py]
                checked += bool(py)
        assert checked > 20  # enough non-empty diagnoses to mean something
    finally:
        delete_graph(name)


def test_bkt_em_caps_guess_and_slip_at_half():
    """Answers mostly right regardless of state (G 0.8) would push the unconstrained guess above 0.5."""
    rng = np.random.default_rng(1)
    seqs = [(rng.random(12) < 0.8).astype(int) for _ in range(2000)]
    L0, T, S, G = fit_bkt(seqs, max_iter=50)["params"]
    assert G <= 0.5 and S <= 0.5


def test_random_root_is_drawn_only_from_evaluable_roots():
    for variant in ("primary", "sensitivity"):
        g = Graph(variant)
        eligible = [c for c in g.root_candidates if len(g.dependents[c] | {c}) < len(g.prereqs)]
        assert 204 not in eligible and eligible == [c for c in g.root_candidates if c != 204]
