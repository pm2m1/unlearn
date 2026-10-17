"""End to end: Diagnoser -> Tutor -> Teacher on a GRAPH.COPY of class_template, with noiseless planted students.

  p1: root 408, target 410, misconception 18650 (on two of 408's questions, so it can be shown twice)
  p2: root 408, target 419, misconceptions 18650 and 19773 (shares 18650 with p1, so the Teacher regroups)
  p3: root 3378, target 411, misconception 15384 (no cohort, so the Teacher assigns practice)
"""

import pytest

from eval.simulator import Simulator
from unlearn import llm
from unlearn import queries as Q
from unlearn import tools as T
from unlearn.agents.runner import run_session_sync
from unlearn.db import copy_graph, delete_graph, run, run_batched

CLASS_ID = "pytest_agents"
PLANTED = {"p1": (408, 410, [18650]), "p2": (408, 419, [18650, 19773]), "p3": (3378, 411, [15384]),
           "p4": (408, 410, [18650])}


def run_named(class_id, sid, student, session):
    return run_session_sync(class_id, sid, student.target, lambda _sid, q: student.answer(q),
                            session_id=f"{sid}-s{session}")


@pytest.fixture(scope="module")
def world():
    g = f"class_{CLASS_ID}"
    delete_graph(g)
    copy_graph("class_template", g)
    run_batched(g, Q.LOAD_STUDENTS, [{"id": s, "alias": s.upper()} for s in PLANTED])
    sim = Simulator(seed=0, noiseless=True)
    students = {sid: sim.student(sid, root, target, mids) for sid, (root, target, mids) in PLANTED.items()}
    results = {sid: run_named(CLASS_ID, sid, students[sid], 1) for sid in ("p1", "p2", "p3")}
    yield {"students": students, "results": results}
    delete_graph(g)


def final_diagnosis(result):
    return [s for s in result.steps if s.agent == "Diagnoser" and s.tool == "root_cause"][-1].rows


@pytest.mark.parametrize("sid", ["p1", "p2", "p3"])
def test_diagnosis_names_the_planted_root_cause(world, sid):
    rows = final_diagnosis(world["results"][sid])
    assert rows[0]["id"] == world["students"][sid].root_cause
    said = [s for s in world["results"][sid].steps if s.tool == "llm:diagnosis"][0].text
    assert rows[0]["name"] in said


@pytest.mark.parametrize("sid", ["p1", "p2", "p3"])
def test_task_chain_runs_diagnoser_tutor_teacher(world, sid):
    chain = T.chain(CLASS_ID, f"{sid}-s1-diagnose")
    assert [(t["agent"], t["kind"], t["state"]) for t in chain["rows"]] == [
        ("Diagnoser", "diagnose", "completed"), ("Tutor", "remediate", "completed"), ("Teacher", "review", "completed")]
    assert chain["open"] == 0


def test_agents_never_write_cypher(world):
    # Every query any agent ran is a named constant from queries.py.
    names = {q for r in world["results"].values() for s in r.steps for q in s.queries}
    assert names and "?" not in names


def test_pending_proposals(world):
    by_id = {p["id"]: p for p in T.proposals(CLASS_ID)["rows"]}
    assert by_id["p-p1-s1-review"]["kind"] == "assign_practice" and by_id["p-p1-s1-review"]["students"] == ["p1"]
    assert by_id["p-p2-s1-review"]["kind"] == "regroup"
    assert sorted(by_id["p-p2-s1-review"]["students"]) == ["p1", "p2"]
    assert by_id["p-p3-s1-review"]["kind"] == "assign_practice"
    assert by_id["p-p3-s1-review"]["payload"]["construct_id"] == 3378
    assert all(p["state"] == "pending" for p in by_id.values())


def test_approve_regroup_applies_it_and_logs_an_event(world):
    row = T.decide(CLASS_ID, "p-p2-s1-review", "approved")["rows"][0]
    gid = row["applied"]["group_id"]
    members, _ = run(f"class_{CLASS_ID}", Q.GROUP_MEMBERS, {"gid": gid})
    assert [m["id"] for m in members] == ["p1", "p2"]
    events, _ = run(f"class_{CLASS_ID}", Q.PROPOSAL_EVENTS, {"pid": "p-p2-s1-review"})
    assert [e["type"] for e in events] == ["proposal_applied"] and gid in events[0]["summary"]


def test_approve_assign_practice(world):
    row = T.decide(CLASS_ID, "p-p1-s1-review", "approved")["rows"][0]
    got, _ = run(f"class_{CLASS_ID}", Q.ASSIGNMENTS_FOR, {"sid": "p1"})
    assert got == [{"id": row["applied"]["assignment_id"], "construct_id": 408}]
    events, _ = run(f"class_{CLASS_ID}", Q.PROPOSAL_EVENTS, {"pid": "p-p1-s1-review"})
    assert len(events) == 1


def test_reject_changes_nothing(world):
    g = f"class_{CLASS_ID}"
    before, _ = run(g, Q.COUNT_LABELS)
    assert T.decide(CLASS_ID, "p-p3-s1-review", "rejected")["rows"][0]["kind"] == "assign_practice"
    after, _ = run(g, Q.COUNT_LABELS)
    assert after == before
    assert run(g, Q.ASSIGNMENTS_FOR, {"sid": "p3"})[0] == []
    assert run(g, Q.PROPOSAL_EVENTS, {"pid": "p-p3-s1-review"})[0] == []
    assert T.proposals(CLASS_ID, "rejected")["rows"][0]["id"] == "p-p3-s1-review"
    assert T.decide(CLASS_ID, "p-p3-s1-review", "approved")["rows"] == []  # decided once only


def test_approve_skip_ahead_marks_teacher_override(world):
    T.propose(CLASS_ID, "p-skip", "skip_ahead", {"construct_id": 3342}, ["p3"])
    T.decide(CLASS_ID, "p-skip", "approved")
    got, _ = run(f"class_{CLASS_ID}", Q.MASTERED_EDGE, {"sid": "p3", "cid": 3342})
    assert got == [{"evidence": "teacher_override"}]


def test_session_two_opens_with_recall_of_the_planted_misconception(world):
    result = run_named(CLASS_ID, "p1", world["students"]["p1"], 2)
    assert result.session_n == 2
    first = next(s for s in result.steps if s.tool not in ("task_context",))
    assert (first.agent, first.tool) == ("Diagnoser", "recall")
    planted, _ = run(f"class_{CLASS_ID}", Q.STUDENT_SHOWED, {"sid": "p1"})
    planted_name = next(r["name"] for r in planted if r["mid"] == 18650)
    assert planted_name in [r["misconception"] for r in first.rows]
    said = next(s for s in result.steps if s.tool == "llm:recall").text
    assert said.startswith("Welcome back") and planted_name in said


def test_fabricated_llm_reply_never_reaches_the_student(world, monkeypatch):
    """A provider that invents a misconception is retried once, then replaced by the template."""
    fake = llm.Provider("fake", "FAKE_KEY", "http://unused", "FAKE_MODEL", "fake-1")
    monkeypatch.setattr(llm, "available", lambda: [fake])
    monkeypatch.setattr(llm, "complete", lambda p, m: ("You believe [[Fractions are made of cheese]].", False))
    result = run_named(CLASS_ID, "p4", world["students"]["p4"], 1)
    said = [s for s in result.steps if s.tool.startswith("llm:")]
    assert said and all(s.source == "template" for s in said)
    assert all("cheese" not in s.text for s in said)
    assert all([a["ok"] for a in s.rows] == [False, False, True] for s in said)


def test_step_api_drives_one_session_without_memory(world):
    """The HTTP path: one call per step, a fresh agent each time; only the graph carries state."""
    from unlearn.agents import runner
    from unlearn.agents.base import StepError

    run_batched(f"class_{CLASS_ID}", Q.LOAD_STUDENTS, [{"id": "p5", "alias": "P5"}])
    student = Simulator(seed=0, noiseless=True).student("p5", 408, 410, [18650])
    out = runner.start(CLASS_ID, "p5", 410, session_id="p5-s1")
    assert out["kind"] == "question" and out["session_n"] == 1
    with pytest.raises(StepError):
        runner.answer(CLASS_ID, "p5-s1", "q-not-pending", "A")
    while out["kind"] == "question":
        out = runner.answer(CLASS_ID, "p5-s1", out["question"]["id"], student.answer(out["question"]))
    assert out["kind"] == "diagnosis" and out["root"]["id"] == 408
    tut = runner.remediate(CLASS_ID, "p5-s1")
    assert tut["kind"] == "check" and tut["skill"]["skill"] and tut["explanation"]
    with pytest.raises(StepError):
        runner.remediate(CLASS_ID, "p5-s1")  # already claimed
    done = runner.answer(CLASS_ID, "p5-s1", tut["question"]["id"], student.answer(tut["question"]))
    assert done["kind"] == "done" and done["agent"] == "Tutor"
    with pytest.raises(StepError):
        runner.answer(CLASS_ID, "p5-s1", tut["question"]["id"], "A")  # nothing pending any more
