"""Tool behaviour on a fixture class with three hand-made students.

Planted broken prerequisites for target construct 1 (REQUIRES 1 -> 2 -> 3 -> 4, 1 -> 5):
  Asha (sa): construct 3, 2 hops back. Has mastered 5.
  Ben  (sb): construct 4, 3 hops back, plus weaker evidence on 2.
  Chen (sc): construct 3, tied evidence with construct 2, so depth must break the tie.
Asha and Chen share misconception 301; Ben shares nothing with confidence > 0.6.
"""

import pytest

from unlearn import tools as T

TARGET = 1


@pytest.fixture(scope="module")
def planted(fixture_class):
    c = fixture_class
    ts = iter(range(1, 10_000))
    for sid in ("sa", "sb", "sc"):
        T.start_session(c, sid, f"{sid}-1", ts=next(ts))

    def wrong(sid, qid, key="B"):
        out = T.record_attempt(c, sid, qid, key, f"{sid}-1", ts=next(ts))
        row = out["rows"][0]
        T.log_event(c, f"{sid}-1", f"ev-{sid}-{qid}-{key}", "misconception", f"Picked {key} on {qid}",
                    misconception_id=row["mid"], ts=next(ts))

    # Asha: 301 twice (construct 3), masters construct 5.
    wrong("sa", "q-3-1"); wrong("sa", "q-3-2")
    T.record_attempt(c, "sa", "q-5-1", "A", "sa-1", ts=next(ts))
    T.record_attempt(c, "sa", "q-5-2", "A", "sa-1", ts=next(ts))
    # Ben: 401 twice (construct 4), 202 once (construct 2).
    wrong("sb", "q-4-1"); wrong("sb", "q-4-2"); wrong("sb", "q-2-1", key="C")
    # Chen: 301 twice (construct 3) and 201 twice (construct 2): equal evidence 1.5.
    wrong("sc", "q-3-1"); wrong("sc", "q-3-2"); wrong("sc", "q-2-1"); wrong("sc", "q-2-2")

    # Second session for everyone.
    for sid in ("sa", "sb", "sc"):
        T.start_session(c, sid, f"{sid}-2", ts=next(ts))
    return c


def test_receipt_shape(planted):
    out = T.root_cause(planted, "sa", TARGET)
    assert set(out) == {"cypher", "params", "rows", "node_ids"}
    assert len(out["cypher"]) == len(out["params"]) == 2


def test_mastery_marked(planted):
    out = T.learning_path(planted, "sa", TARGET)
    assert 5 not in [r["id"] for r in out["rows"]]


@pytest.mark.parametrize("sid, planted_id, depth", [("sa", 3, 2), ("sb", 4, 3), ("sc", 3, 2)])
def test_root_cause_finds_planted_prerequisite(planted, sid, planted_id, depth):
    rows = T.root_cause(planted, sid, TARGET)["rows"]
    assert rows[0]["id"] == planted_id
    assert rows[0]["depth"] == depth
    assert rows[0]["chain_ids"][0] == TARGET and rows[0]["chain_ids"][-1] == planted_id
    assert len(rows[0]["chain_ids"]) == depth + 1


def test_root_cause_tie_goes_deeper(planted):
    rows = T.root_cause(planted, "sc", TARGET)["rows"]
    assert [r["id"] for r in rows[:2]] == [3, 2]
    assert rows[0]["evidence"] == rows[1]["evidence"] == pytest.approx(1.5)


def test_probe_frontier_returns_deepest_unprobed(planted):
    # Asha attempted constructs 3 and 5 (and mastered 5): the deepest unprobed prerequisite is 4.
    rows = T.probe_frontier(planted, "sa", TARGET)["rows"]
    assert rows[0] == {"id": 4, "name": "Identify multiples of a number", "depth": 3}
    assert {3, 5}.isdisjoint(r["id"] for r in rows)
    # A student with no attempts gets the deepest prerequisite overall.
    assert T.probe_frontier(planted, "sd", TARGET)["rows"][0]["id"] == 4


def test_recall_in_second_session(planted):
    rows = T.recall(planted, "sa")["rows"]
    assert [r["misconception"] for r in rows] == [
        "Multiplies the two numbers together to find the lowest common multiple"]
    assert rows[0]["times"] == 2
    assert rows[0]["recent"] == ["Picked B on q-3-2", "Picked B on q-3-1"]  # newest first
    # Ben's one-off misconception (confidence 0.5) is not recalled.
    assert len(T.recall(planted, "sb")["rows"]) == 1


def test_cohorts_group_students_sharing_a_gap(planted):
    rows = T.cohorts(planted)["rows"]
    assert len(rows) == 1
    assert sorted(rows[0]["students"]) == ["Asha", "Chen"]
    assert T.cohorts(planted)["rows"] == rows  # rebuilding the edges is idempotent


def test_next_question_prefers_unprobed(planted):
    row = T.next_question(planted, "sb", 4, "sb-1")["rows"]
    assert row == []  # Ben attempted both construct-4 questions in session sb-1
    row = T.next_question(planted, "sb", 2, "sb-1")["rows"][0]
    assert row["id"] == "q-2-2" and row["probes"] == 2 and row["unprobed"] == 1


def test_next_question_reasks_in_a_later_session(planted):
    # In session sb-2, earlier attempts are allowed again: least recently attempted first.
    assert T.next_question(planted, "sb", 4, "sb-2")["rows"][0]["id"] == "q-4-1"
    # Never-attempted beats attempted-long-ago: Ben did q-2-1 only.
    row = T.next_question(planted, "sb", 2, "sb-2")["rows"][0]
    assert row["id"] == "q-2-2" and row["fresh"] is True


def test_learning_path_and_shortest_chain(planted):
    out = T.learning_path(planted, "sd", TARGET, to_id=4)
    assert [r["id"] for r in out["rows"]][:2] == [4, 3]
    assert out["rows"][-1]["id"] == TARGET  # depth 0 is the target itself
    assert out["rows"][0]["shortest_chain"] == [
        "Add fractions with unlike denominators", "Identify equivalent fractions",
        "Find the lowest common multiple", "Identify multiples of a number"]


def test_skills(planted):
    assert T.pick_skill(planted, 301)["rows"][0]["skill"] == "Fraction wall"
    rate = T.update_skill(planted, "Fraction wall", ok=True)["rows"][0]
    assert rate["rate"] == pytest.approx((0.5 * 2 + 1) / 3) and rate["uses"] == 1


def test_keystones_rank_foundations(planted):
    rows = T.keystones(planted)["rows"]
    assert rows[0]["id"] == 4  # the deepest prerequisite has the most incoming weight


def test_handoff_and_approval_gate(planted):
    T.create_task(planted, "t-1", "diagnose", "sa", "Diagnoser", ts=1)
    assert T.claim(planted, "Diagnoser", "w1")["rows"] == [{"id": "t-1", "kind": "diagnose"}]
    T.handoff(planted, "t-1", "sa", "Tutor", "remediate", "t-2", ts=2)
    assert T.claim(planted, "Tutor", "w2")["rows"] == [{"id": "t-2", "kind": "remediate"}]
    with pytest.raises(ValueError):
        T.propose(planted, "p-bad", "delete_students", {}, ["sa"])
    with pytest.raises(ValueError):
        T.propose(planted, "p-solo", "regroup", {}, ["sa"])  # a group needs two students
    with pytest.raises(ValueError):
        T.propose(planted, "p-noc", "assign_practice", {}, ["sa"])  # needs a construct
    T.propose(planted, "p-1", "regroup", {"group_id": "g-1"}, ["sa", "sc"], ts=3)
    row = T.decide(planted, "p-1", "approved", ts=4)["rows"][0]
    assert (row["kind"], row["payload"]) == ("regroup", {"group_id": "g-1"})
    assert row["applied"]["group_id"] == "g-1" and sorted(row["applied"]["members"]) == ["sa", "sc"]
    assert T.decide(planted, "p-1", "rejected", ts=5)["rows"] == []  # no longer pending


# --- diagnose_text: is `score` a distance (lower = closer) or a similarity? ---

@pytest.mark.parametrize("cid, explanation, expected", [
    (1, "I added the top numbers together and the bottom numbers together", 101),
    (3, "To get the LCM of 4 and 6 I just multiplied them to get 24", 301),
    (4, "14 ends in a 4 so it has to be a multiple of 4", 401),
])
def test_diagnose_text_closest_first(fixture_class, cid, explanation, expected):
    rows = T.diagnose_text(fixture_class, cid, explanation)["rows"]
    assert rows[0]["id"] == expected
    scores = [r["score"] for r in rows]
    assert scores == sorted(scores)


def test_diagnose_text_score_is_a_distance(fixture_class):
    # The exact misconception text must score ~0 if score is a distance (~1 if a similarity).
    rows = T.diagnose_text(fixture_class, 3, "Multiplies the two numbers together to find the lowest common multiple")["rows"]
    assert rows[0]["id"] == 301
    assert rows[0]["score"] < 0.05
