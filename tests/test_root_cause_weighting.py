"""root_cause weights evidence by SEEN_IN.pct, so a generic misconception spread over many prerequisites
can't outvote one that is concentrated on a single prerequisite.

Target 10 REQUIRES 11, 12, 13, 14 and 15 (all one hop).
  901 generic:  SEEN_IN 11, 12, 13, 14 at pct 25 each. Shown 3 times -> 3 * 0.875 * 0.25 = 0.656 on each.
  902 specific: SEEN_IN 15 at pct 95 (and 11 at pct 5). Shown twice -> 2 * 0.75 * 0.95 = 1.425 on 15.
Unweighted (the old sum), 11-14 would score 2.625 each and beat 15's 1.5.
"""

import pytest

from unlearn import queries as Q
from unlearn import tools as T
from unlearn.db import create_indexes, delete_graph, run, run_batched

CLASS_ID = "pytest_weighting"
TARGET, X = 10, 15
CONSTRUCTS = {10: "Target", 11: "Prereq A", 12: "Prereq B", 13: "Prereq C", 14: "Prereq D", 15: "Prereq X"}
SEEN_IN = [(901, c, 25.0) for c in (11, 12, 13, 14)] + [(902, 15, 95.0), (902, 11, 5.0)]
NAMES = {901: "Generic misconception", 902: "Specific misconception"}
QUESTIONS = {"q-g-1": (11, 901), "q-g-2": (12, 901), "q-g-3": (13, 901), "q-x-1": (15, 902), "q-x-2": (15, 902)}


@pytest.fixture(scope="module")
def weighted_class():
    name = f"class_{CLASS_ID}"
    delete_graph(name)
    create_indexes(name, Q.CLASS_INDEXES)
    run_batched(name, Q.LOAD_HIERARCHY, [
        {"subject_id": 900, "subject": "Number", "topic_id": 901, "topic": "Fractions", "subtopic_id": 902,
         "subtopic": "Fixture", "construct_id": c, "construct": n} for c, n in CONSTRUCTS.items()])
    run_batched(name, Q.LOAD_MISCONCEPTIONS, [
        {"mid": m, "mname": NAMES[m], "cid": c, "pct": p} for m, c, p in SEEN_IN])
    run_batched(name, Q.LOAD_REQUIRES, [
        {"construct_id": TARGET, "prereq_id": c, "note": "fixture", "confidence": "high"} for c in CONSTRUCTS if c != TARGET])
    run_batched(name, Q.LOAD_QUESTIONS, [
        {"id": q, "construct_id": c, "text": f"Fixture {q}"} for q, (c, _) in QUESTIONS.items()])
    run_batched(name, Q.LOAD_OPTIONS, [row for q, (_, m) in QUESTIONS.items() for row in (
        {"qid": q, "key": "A", "text": "right", "correct": True, "mid": None},
        {"qid": q, "key": "B", "text": "wrong", "correct": False, "mid": m})])
    run_batched(name, Q.LOAD_STUDENTS, [{"id": "sw", "alias": "Wen"}])
    T.start_session(CLASS_ID, "sw", "sw-1", ts=1)
    for i, q in enumerate(QUESTIONS, start=2):
        T.record_attempt(CLASS_ID, "sw", q, "B", "sw-1", ts=i)
    yield CLASS_ID
    delete_graph(name)


def test_specific_misconception_beats_generic_spread(weighted_class):
    rows = T.root_cause(weighted_class, "sw", TARGET)["rows"]
    assert rows[0]["id"] == X
    assert rows[0]["evidence"] == pytest.approx(2 * 0.75 * 0.95)
    # 11 also gets 902's small share: 0.656 + 2 * 0.75 * 0.05.
    others = {r["id"]: r["evidence"] for r in rows[1:]}
    assert others[11] == pytest.approx(3 * 0.875 * 0.25 + 2 * 0.75 * 0.05)
    assert all(e < rows[0]["evidence"] for e in others.values())


def test_shown_counts_are_unweighted(weighted_class):
    # The weighting lives in root_cause only; SHOWED still counts raw hits.
    rows, _ = run(f"class_{weighted_class}", Q.STUDENT_SHOWED, {"sid": "sw"})
    assert {r["mid"]: r["count"] for r in rows} == {901: 3, 902: 2}
