"""Pilot mode: no personal fields, consent before any answer is stored, deletion really deletes, a restart
rebuilds the same state from the log, unapproved items are never used, and the demo never sees pilot classes.

Runs on SQLite by default. Set PILOT_TEST_PG_URL (a throwaway Postgres) to run the store tests on Postgres too.
Needs FalkorDB with class_template (make up && make seed), like the other graph tests.
"""

import logging
import os

import pytest

from unlearn import queries as Q
from unlearn import tools
from unlearn.db import list_graphs, run
from unlearn.pilot import items as I
from unlearn.pilot import store as S
from unlearn.pilot.engine import (Conflict, Forbidden, NotFound, Pilot, build_graph, class_id, is_pilot_class,
                                  wipe_all)
from unlearn.pilot.store import SCHEMA, Event, SaveFailed, Store

ADMIN = "test-admin-key"
BACKENDS = ["sqlite"] + (["postgres"] if os.getenv("PILOT_TEST_PG_URL") else [])
# Personal-data words no pilot column may contain.
BANNED = {"name", "email", "mail", "phone", "mobile", "ip", "addr", "address", "device", "agent", "ua", "user",
          "text", "comment", "note", "notes", "dob", "birth", "age", "gender", "school", "location", "lat", "lon"}


def approve_all(tmp_path, skip: set[str] = frozenset(), wording_ok: bool = True) -> I.ItemSet:
    """A review file that approves every item (except `skip`), with the right fingerprints."""
    import json
    data = json.loads(I.ITEMS.read_text())
    blocks = [f"### {I.WORDING_ID}\n`fingerprint: {I.wording_fingerprint(data['constructs'])}`\n"
              f"**Decision:** {'APPROVED' if wording_ok else 'PENDING'}\n"]
    for it in data["items"]:
        dec = "DROPPED" if it["id"] in skip else "APPROVED"
        blocks.append(f"### {it['id']}\n`fingerprint: {I.item_fingerprint(it)}`\n**Decision:** {dec}\n")
    review = tmp_path / "ITEM_REVIEW.md"
    review.write_text("\n".join(blocks))
    return I.load(I.ITEMS, review)


def make_store(kind: str, tmp_path) -> Store:
    if kind == "sqlite":
        return Store(f"sqlite:///{tmp_path / 'pilot.db'}")
    st = Store(os.environ["PILOT_TEST_PG_URL"])
    st.init()
    st.wipe()
    return st


@pytest.fixture(params=BACKENDS)
def env(request, tmp_path, monkeypatch):
    monkeypatch.setattr(S, "RETRY_SLEEPS", (0.0, 0.0, 0.0))
    item_set = approve_all(tmp_path)
    store = make_store(request.param, tmp_path)
    p = Pilot(store, item_set, ADMIN)
    p.load_all()
    yield p
    wipe_all(store, p)


def construct_of(p: Pilot, qid: str) -> int:
    return p.items.items[qid]["construct_id"]


def pick(p: Pilot, s: dict, wrong: set[int]) -> str:
    """The student's choice: the first wrong option on constructs in `wrong`, else the right one."""
    it = p.items.items[s["question"]["id"]]
    want_wrong = it["construct_id"] in wrong
    return next(o["key"] for o in it["options"] if bool(o.get("correct")) != want_wrong)


def run_session(p: Pilot, code: str, n: int, wrong: set[int], stop_after: int | None = None) -> tuple[dict, list]:
    """Assent and answer until the session ends (or after `stop_after` answers). Returns the last screen and the
    (phase, question id) pairs asked."""
    s = p.state(code)
    assert s == {"screen": "assent", "session": n}
    s = p.assent(code, n, True)
    asked = []
    while s["screen"] == "question":
        if stop_after is not None and len(asked) == stop_after:
            break
        asked.append((s["phase"], s["question"]["id"]))
        s = p.answer(code, n, s["question"]["id"], pick(p, s, wrong), 4200)
    return s, asked


def snapshot(p: Pilot, pc, code: str) -> dict:
    g = tools.graph_name(pc.cid)
    showed = run(g, Q.STUDENT_SHOWED, {"sid": code})[0]
    attempts = run(g, "MATCH (:Student {id:$sid})-[a:ATTEMPTED]->(q:Question) RETURN q.id AS q, a.option AS o, "
                      "a.session AS s ORDER BY q, s", {"sid": code})[0]
    over = p.overview(pc)
    return {"screen": p.state(code), "showed": showed, "attempts": attempts, "students": over["students"]}


# --- schema: no personal data --------------------------------------------------------------------------------

@pytest.mark.parametrize("kind", BACKENDS)
def test_schema_has_only_the_allowed_fields(kind, tmp_path):
    st = make_store(kind, tmp_path)
    st.init()
    assert st.columns() == SCHEMA
    for table, cols in SCHEMA.items():
        for col in cols:
            assert not set(col.lower().split("_")) & BANNED, f"{table}.{col} looks like personal data"
    assert sorted(SCHEMA) == ["pilot_classes", "pilot_codes", "pilot_events", "pilot_ratings"]
    assert SCHEMA["pilot_events"] == ["id", "code", "session", "kind", "phase", "question_id", "option", "correct",
                                      "misconception_id", "ts", "ms", "assent"]


def test_codes_are_random_and_carry_nothing(env):
    out = env.create_class(ADMIN, 30)
    assert len(out["codes"]) == len(set(out["codes"])) == 30
    for c in out["codes"]:
        cc, s = c.split("-")
        assert cc == out["class_code"] and len(s) == 5 and set(c) <= set("ABCDEFGHJKMNPQRSTUVWXYZ23456789-")
    header = env.answers_csv(env.classes[out["class_code"]]).splitlines()[0].split(",")
    assert header == ["code", "session", "phase", "question_id", "option", "correct", "misconception_id",
                      "answered_at_utc", "time_to_answer_ms"]


# --- consent ---------------------------------------------------------------------------------------------------

def test_no_answer_is_stored_before_assent(env):
    out = env.create_class(ADMIN, 2)
    code = out["codes"][0]
    first = env.items.check[1][0]
    with pytest.raises(Conflict):
        env.answer(code, 1, first, "A", 1000)
    assert env.store.count("pilot_events") == 0

    assert env.assent(code, 1, False) == {"screen": "declined"}
    with pytest.raises(Conflict):
        env.answer(code, 1, first, "A", 1000)
    events = env.store.events(out["class_code"])
    assert [(e.kind, e.assent) for e in events] == [("assent", False)]  # the "no" itself, nothing else

    s = env.assent(code, 1, True)
    assert s["screen"] == "question" and s["question"]["id"] == first
    env.answer(code, 1, first, "A", 1000)
    assert [e.kind for e in env.store.events(out["class_code"])] == ["assent", "assent", "answer"]


# --- the flow ------------------------------------------------------------------------------------------------

def test_two_sessions_end_to_end(env):
    out = env.create_class(ADMIN, 2)
    code = out["codes"][0]
    pc = env.classes[out["class_code"]]
    s, asked = run_session(env, code, 1, wrong={427, 435, 345, 342})
    assert s == {"screen": "done", "session": 1, "all_right": False}
    phases = [ph for ph, _ in asked]
    assert phases[:5] == ["check"] * 5 and "diagnose" in phases and phases[-1] == "tutor"
    assert [q for ph, q in asked if ph == "check"] == env.items.check[1]
    # The Diagnoser and Tutor only ask pool items: check items are never reused.
    assert all(env.items.items[q]["role"] == "POOL" for ph, q in asked if ph != "check")

    assert env.state(code) == {"screen": "wait"}                      # session 2 not open yet
    assert env.assent(code, 2, True) == {"screen": "wait"}
    assert sum(e.session == 2 for e in env.store.events(pc.code)) == 0

    env.set_session2(pc, True)
    s, asked2 = run_session(env, code, 2, wrong={427})
    assert [q for _, q in asked2] == env.items.check[2]
    root = env.overview(pc)["students"][0]["root"]
    assert root and s["screen"] == "done" and s["session"] == 2 and s["recall"] == root
    assert env.state(code) == {"screen": "finished"}

    row = next(x for x in env.overview(pc)["students"] if x["code"] == code)
    assert row["status"] == "both sessions done" and row["check"][1]["right"] == 3 and row["check"][2]["right"] == 4
    answers = [e for e in env.store.events(pc.code) if e.kind == "answer"]
    assert all(e.ms == 4200 and e.option in "ABCD" for e in answers)
    assert all((e.misconception_id is None) == e.correct for e in answers)


def test_all_right_in_session_1_ends_without_a_diagnosis(env):
    out = env.create_class(ADMIN, 1)
    s, asked = run_session(env, out["codes"][0], 1, wrong=set())
    assert s == {"screen": "done", "session": 1, "all_right": True} and len(asked) == 5


def test_a_resent_answer_is_stored_once(env):
    out = env.create_class(ADMIN, 1)
    code = out["codes"][0]
    s = env.assent(code, 1, True)
    q = s["question"]["id"]
    nxt = env.answer(code, 1, q, "A", 900)
    assert env.answer(code, 1, q, "A", 900) == nxt
    assert sum(e.kind == "answer" for e in env.store.events(out["class_code"])) == 1


def test_a_failed_save_is_not_acknowledged(env, monkeypatch):
    out = env.create_class(ADMIN, 1)
    code = out["codes"][0]
    s = env.assent(code, 1, True)
    q = s["question"]["id"]

    def down(ev):
        raise SaveFailed("pilot log unavailable")
    monkeypatch.setattr(env.store, "append", down)
    with pytest.raises(SaveFailed):
        env.answer(code, 1, q, "A", 900)
    assert env.state(code)["question"]["id"] == q                     # still waiting on the same question
    monkeypatch.undo()
    assert env.answer(code, 1, q, "A", 900)["progress"]["i"] == 2


def test_the_store_retries_through_a_dropped_connection(tmp_path, monkeypatch):
    monkeypatch.setattr(S, "RETRY_SLEEPS", (0.0, 0.0, 0.0))
    st = Store(f"sqlite:///{tmp_path / 'retry.db'}")
    st.init()
    real, fails = st._exec, {"n": 2}

    def flaky(*a, **k):
        if fails["n"]:
            fails["n"] -= 1
            raise OSError("connection reset")
        return real(*a, **k)
    monkeypatch.setattr(st, "_exec", flaky)
    assert st.append(Event("ABCD-EFGHJ", 1, "assent", 1, assent=True)) == 1
    fails["n"] = 10
    with pytest.raises(SaveFailed):
        st.append(Event("ABCD-EFGHJ", 1, "assent", 2, assent=True))


# --- restart -------------------------------------------------------------------------------------------------

def test_a_restart_rebuilds_the_same_state_from_the_log(env):
    out = env.create_class(ADMIN, 3)
    a, b, c = out["codes"]
    pc = env.classes[out["class_code"]]
    run_session(env, a, 1, wrong={427, 435, 345, 342})                  # finished session 1
    run_session(env, b, 1, wrong={433, 432}, stop_after=7)             # in the middle of the diagnosis
    env.assent(c, 1, False)                                            # declined
    env.set_rating(pc, a, 4)
    before = {code: snapshot(env, pc, code) for code in (a, b, c)}

    # A restart: the in-memory graph and state are gone; only the log survives.
    tools_graph = tools.graph_name(pc.cid)
    from unlearn.db import delete_graph
    delete_graph(tools_graph)
    fresh = Pilot(Store(env.store.url), env.items, ADMIN)
    fresh.load_all()
    pc2 = fresh.classes[out["class_code"]]
    after = {code: snapshot(fresh, pc2, code) for code in (a, b, c)}
    assert after == before
    assert fresh.realigned == 0

    # And the student carries on where they were.
    s = fresh.state(b)
    while s["screen"] == "question":
        s = fresh.answer(b, 1, s["question"]["id"], pick(fresh, s, {433, 432}), 1000)
    assert s["screen"] == "done"


# --- deletion ------------------------------------------------------------------------------------------------

def test_deleting_a_code_really_deletes_it(env):
    out = env.create_class(ADMIN, 2)
    a, b = out["codes"]
    pc = env.classes[out["class_code"]]
    run_session(env, a, 1, wrong={427, 345})
    run_session(env, b, 1, wrong={433})
    env.set_rating(pc, a, 2)
    env.delete_code(pc, a)

    st = env.store
    rows = st._exec("SELECT code FROM pilot_events UNION ALL SELECT code FROM pilot_ratings "
                    "UNION ALL SELECT code FROM pilot_codes", fetch=True)
    assert a not in {r["code"] for r in rows} and b in {r["code"] for r in rows}
    g = tools.graph_name(pc.cid)
    assert run(g, "MATCH (s:Student {id:$sid}) RETURN count(s) AS n", {"sid": a})[0][0]["n"] == 0
    assert run(g, "MATCH ()-[a:ATTEMPTED]->() WHERE a.session STARTS WITH $p RETURN count(a) AS n",
               {"p": a})[0][0]["n"] == 0
    assert [s["code"] for s in env.overview(pc)["students"]] == [b]
    with pytest.raises(NotFound):
        env.state(a)
    assert env.state(b)["screen"] == "wait"                            # the other student is untouched


def test_deleting_a_class_and_wiping_really_delete(env):
    one = env.create_class(ADMIN, 2)
    two = env.create_class(ADMIN, 2)
    run_session(env, one["codes"][0], 1, wrong={427})
    run_session(env, two["codes"][0], 1, wrong={410})
    pc1 = env.classes[one["class_code"]]
    env.delete_class(pc1)
    assert tools.graph_name(class_id(one["class_code"])) not in list_graphs()
    assert env.store.codes(one["class_code"]) == [] and env.store.events(one["class_code"]) == []
    assert all(r["class_code"] != one["class_code"] for r in env.store.classes())
    assert env.store.events(two["class_code"])                         # the other class is untouched

    with pytest.raises(Forbidden):
        env.wipe("wrong key")
    env.wipe(ADMIN)
    assert {t: env.store.count(t) for t in SCHEMA} == {t: 0 for t in SCHEMA}
    assert not [g for g in list_graphs() if g.startswith("class_pilot_")]


# --- approval ------------------------------------------------------------------------------------------------

def test_only_approved_items_are_used(tmp_path):
    shipped = I.load()                                                 # the repo's review file as it stands
    assert set(shipped.items) <= {k for k, (_, d) in I.decisions(I.REVIEW.read_text()).items() if d == I.APPROVED}

    dropped = {"q-3378-1", "q-3378-2", "q-3378-3", "q-435-1"}
    item_set = approve_all(tmp_path, skip=dropped)
    assert not dropped & set(item_set.items) and "q-435-1" not in item_set.check[1]
    build_graph("pilot_pytest", item_set, ["ZZZZ-AAAAA"])
    g = tools.graph_name("pilot_pytest")
    qids = {r["id"] for r in run(g, "MATCH (q:Question) RETURN q.id AS id")[0]}
    assert qids == set(item_set.items)
    held = {r["id"] for r in run(g, "MATCH (q:Question) WHERE q.check_only = true RETURN q.id AS id")[0]}
    assert held == set(item_set.check[1]) | set(item_set.check[2])
    from unlearn.db import delete_graph
    delete_graph(g)

    # An item changed after approval is out until it is approved again.
    data = I.ITEMS.read_text().replace('"text": "7 × 8 = ?"', '"text": "7 × 9 = ?"')
    changed = tmp_path / "items.json"
    changed.write_text(data)
    assert "q-3378-1" not in I.load(changed, tmp_path / "ITEM_REVIEW.md").items


def test_a_class_needs_approved_wording_and_check_items(tmp_path):
    st = Store(f"sqlite:///{tmp_path / 'p.db'}")
    p = Pilot(st, approve_all(tmp_path, wording_ok=False), ADMIN)
    p.load_all()
    with pytest.raises(Conflict, match="wording"):
        p.create_class(ADMIN, 5)
    data_ids = [i for i in I.load(I.ITEMS, tmp_path / "ITEM_REVIEW.md").items if i.startswith("q-4")]
    p = Pilot(st, approve_all(tmp_path, skip=set(data_ids) | {"q-410-1", "q-410-2"}), ADMIN)
    p.load_all()
    with pytest.raises(Conflict, match="check items"):
        p.create_class(ADMIN, 5)
    with pytest.raises(Forbidden):
        Pilot(st, approve_all(tmp_path), ADMIN).create_class("nope", 5)


# --- HTTP and the demo -----------------------------------------------------------------------------------------

def test_http_routes_and_demo_isolation(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    import main
    from unlearn.pilot import routes

    monkeypatch.setenv("PILOT_DATABASE_URL", "")
    with TestClient(main.app) as client:
        assert client.get("/pilot/api/status").json() == {"configured": False}
        assert client.post("/pilot/api/state", json={"code": "ABCD-EFGHJ"}).status_code == 503

        p = routes.configure(f"sqlite:///{tmp_path / 'http.db'}", ADMIN, approve_all(tmp_path))
        p.load_all()
        try:
            page = client.get("/pilot")
            assert page.status_code == 200 and len(page.content) < 20_000
            assert "<script src=" not in page.text                     # nothing loaded from elsewhere
            assert client.post("/pilot/api/teacher/create", json={"students": 3},
                               headers={"X-Pilot-Admin": "wrong"}).status_code == 403
            made = client.post("/pilot/api/teacher/create", json={"students": 3},
                               headers={"X-Pilot-Admin": ADMIN}).json()
            code, cc = made["codes"][0], made["class_code"]
            assert client.post("/pilot/api/state", json={"code": "ZZZZ-ZZZZZ"}).status_code == 404
            assert client.post("/pilot/api/state", json={"code": code.lower().replace("-", "")}).json()["screen"] == "assent"
            r = client.post("/pilot/api/answer", json={"code": code, "session": 1, "qid": p.items.check[1][0], "key": "A"})
            assert r.status_code == 409
            q = client.post("/pilot/api/assent", json={"code": code, "session": 1, "agree": True}).json()
            assert q["screen"] == "question" and "correct" not in str(q) and "misconception" not in str(q)
            assert client.post("/pilot/api/teacher/overview", headers={"X-Pilot-Class": cc, "X-Pilot-Key": "x"}).status_code == 403
            auth = {"X-Pilot-Class": cc, "X-Pilot-Key": made["teacher_key"]}
            assert len(client.post("/pilot/api/teacher/overview", headers=auth).json()["students"]) == 3
            csv_text = client.post("/pilot/api/teacher/export/answers", headers=auth).text
            assert csv_text.startswith("code,session,phase")

            # The demo never shows, simulates or reports a pilot class.
            cid = class_id(cc)
            assert cid not in client.get("/classes").json()["classes"]
            assert client.get(f"/classes/{cid}/students").status_code == 404
            assert client.post(f"/classes/{cid}/students/{code}/simulate").status_code == 404
            health = client.get("/health").json()
            assert not [g for g in health["graphs"] if "pilot" in g] and cid not in str(health)
            assert health["pilot"]["classes"] == 1
        finally:
            wipe_all(p.store, p)
            routes._state["pilot"] = None
    assert is_pilot_class(cid) and not is_pilot_class("demo")


def test_access_log_lines_carry_no_client_address():
    import main  # noqa: F401  (installs the filter)

    rec = logging.LogRecord("uvicorn.access", logging.INFO, "", 0, '%s - "%s %s HTTP/%s" %d',
                            ("203.0.113.9:5555", "POST", "/pilot/api/answer", "1.1", 200), None)
    for f in logging.getLogger("uvicorn.access").filters:
        f.filter(rec)
    assert "203.0.113.9" not in rec.getMessage() and "/pilot/api/answer" in rec.getMessage()
