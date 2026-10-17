"""The HTTP API: a planted student driven through it by the simulator, approvals, /health and self-heal."""

import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import main
from eval.simulator import Simulator
from unlearn import queries as Q
from unlearn import tools as T
from unlearn.db import copy_graph, delete_graph, run, run_batched
from unlearn.heal import plan

ROOT = Path(__file__).resolve().parents[1]
CLASS_ID = "pytest_api"


@pytest.fixture(scope="module")
def client():
    g = f"class_{CLASS_ID}"
    delete_graph(g)
    copy_graph("class_template", g)
    run_batched(g, Q.LOAD_STUDENTS, [{"id": s, "alias": s.upper()} for s in ("h1", "h2", "h3")])
    with TestClient(main.app) as c:
        yield c
    delete_graph(g)


def test_planted_student_through_http_gets_the_right_diagnosis(client):
    student = Simulator(seed=0, noiseless=True).student("h1", 408, 410, [18650])
    out = client.post(f"/classes/{CLASS_ID}/students/h1/sessions", json={"construct_id": 410}).json()
    sess = out["session_id"]
    assert out["kind"] == "question" and out["receipts"]
    asked = 0
    while out["kind"] == "question":
        key = student.answer(out["question"])
        r = client.post(f"/sessions/{sess}/answer", json={"qid": out["question"]["id"], "key": key})
        assert r.status_code == 200, r.text
        out = r.json()
        asked += 1
    assert out["kind"] == "diagnosis" and out["root"]["id"] == 408 and asked <= 6
    dx = client.get(f"/sessions/{sess}/diagnosis").json()
    assert dx["root"]["id"] == 408 and dx["chain"][-1] == dx["root"]["name"]
    receipt = client.get(f"/receipts/{dx['receipt_id']}").json()
    assert receipt["queries"] == ["ROOT_CAUSE", "ROOT_CAUSE_CHAIN"] and receipt["cypher"][0].startswith("MATCH")

    tut = client.post(f"/sessions/{sess}/remediate").json()
    assert tut["kind"] == "check" and tut["explanation"] and tut["skill"]
    assert client.post(f"/sessions/{sess}/remediate").status_code == 409  # only once
    done = client.post(f"/sessions/{sess}/answer", json={"qid": tut["question"]["id"],
                                                          "key": student.answer(tut["question"])}).json()
    assert done["kind"] == "done" and done["agent"] == "Tutor"

    graph = client.get(f"/classes/{CLASS_ID}/students/h1/graph", params={"construct_id": 410, "session": sess}).json()
    assert graph["chain_ids"][-1] == 408 and any(s["mid"] == 18650 for s in graph["showed"])


def test_answer_errors(client):
    out = client.post(f"/classes/{CLASS_ID}/students/h2/sessions", json={"construct_id": 410}).json()
    sess = out["session_id"]
    assert client.post(f"/sessions/{sess}/answer", json={"qid": "q-wrong", "key": "A"}).status_code == 409
    assert client.post(f"/sessions/{sess}/answer", json={"qid": out["question"]["id"]}).status_code == 422
    assert client.post("/sessions/nope/answer", json={"qid": "q", "key": "A"}).status_code == 404
    simulated = client.post(f"/sessions/{sess}/answer", json={"qid": out["question"]["id"], "simulate": True})
    assert simulated.status_code == 200 and simulated.json()["answer"]["key"] in "ABCD"


def test_approve_flow(client):
    T.propose(CLASS_ID, "p-api-1", "assign_practice", {"construct_id": 408}, ["h3"])
    pending = client.get(f"/classes/{CLASS_ID}/proposals").json()["rows"]
    assert "p-api-1" in [p["id"] for p in pending]
    r = client.post("/proposals/p-api-1/decide", json={"decision": "approved"}).json()  # class found by lookup
    assert r["class_id"] == CLASS_ID and r["applied"]["assignment_id"] and r["applied"]["event_id"]
    assert run(f"class_{CLASS_ID}", Q.ASSIGNMENTS_FOR, {"sid": "h3"})[0][0]["construct_id"] == 408
    assert client.post("/proposals/p-api-1/decide", json={"decision": "approved"}).status_code == 409


def test_reject_flow(client):
    g = f"class_{CLASS_ID}"
    T.propose(CLASS_ID, "p-api-2", "regroup", {}, ["h1", "h2"])
    before = run(g, Q.COUNT_LABELS)[0]
    r = client.post("/proposals/p-api-2/decide", json={"decision": "rejected", "class_id": CLASS_ID})
    assert r.status_code == 200 and "applied" not in r.json()
    assert run(g, Q.COUNT_LABELS)[0] == before
    assert run(g, Q.PROPOSAL_EVENTS, {"pid": "p-api-2"})[0] == []
    assert client.post("/proposals/p-api-2/decide", json={"decision": "maybe"}).status_code == 422
    assert client.post("/proposals/p-nope/decide", json={"decision": "approved"}).status_code == 404


def test_health(client):
    h = client.get("/health").json()
    assert h["ok"] is True
    assert {"curriculum", "class_template", f"class_{CLASS_ID}"} <= set(h["graphs"])
    assert h["node_counts"]["curriculum"] > 10_000
    assert h["falkordb_version"].count(".") == 2
    assert h["self_heal"][-1].startswith("graphs now")


def test_teacher_views_and_chat(client):
    for path in ("cohorts", "keystones", "bridges"):
        body = client.get(f"/classes/{CLASS_ID}/{path}").json()
        assert "rows" in body and body["receipt"]["queries"]
    chat = client.post(f"/classes/{CLASS_ID}/teacher/chat", json={"message": "keystones and pending proposals"}).json()
    assert chat["source"] == "template" and "Keystones:" in chat["text"] and chat["receipts"]
    assert client.get("/classes/nope/cohorts").status_code == 404


def test_heal_plan():
    assert plan({"curriculum", "class_template", "class_demo"}) == []
    assert plan({"curriculum", "class_template"}) == [["05_new_class.py", "--id", "demo", "--students", "30"]]
    assert [s[0] for s in plan({"curriculum"})] == ["04_build_template.py", "05_new_class.py"]
    assert [s[0] for s in plan(set())][:2] == ["01_download.py", "02_load_curriculum.py"]


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.mark.skipif(shutil.which("docker") is None, reason="needs docker for a throwaway FalkorDB")
def test_self_heal_on_an_empty_falkordb():
    """Start an empty FalkorDB, run the app's startup self-heal against it, check every graph appears."""
    port, name, password = _free_port(), f"unlearn-heal-test-{os.getpid()}", "heal-test-pw"
    up = subprocess.run(["docker", "run", "-d", "--rm", "--name", name, "-p", f"127.0.0.1:{port}:6379",
                         "-e", f"REDIS_ARGS=--requirepass {password}", "falkordb/falkordb:v4.20.7"],
                        capture_output=True, text=True)
    if up.returncode != 0:
        pytest.skip(f"could not start FalkorDB: {up.stderr.strip()[:200]}")
    try:
        env = {**os.environ, "FALKOR_HOST": "127.0.0.1", "FALKOR_PORT": str(port), "FALKOR_PASSWORD": password,
               "PYTHONPATH": os.pathsep.join([str(ROOT / "api"), str(ROOT)])}
        probe = "from unlearn.db import list_graphs; print(sorted(list_graphs()))"
        for _ in range(60):
            ready = subprocess.run([sys.executable, "-c", probe], env=env, capture_output=True, text=True)
            if ready.returncode == 0:
                break
            time.sleep(0.5)
        assert ready.stdout.strip() == "[]"
        healed = subprocess.run([sys.executable, "-c", "from unlearn.heal import self_heal; print('\\n'.join(self_heal()))"],
                                env=env, capture_output=True, text=True, timeout=600)
        assert healed.returncode == 0, healed.stderr[-2000:]
        assert "graphs found: none" in healed.stdout
        assert "graphs now: ['class_demo', 'class_template', 'curriculum']" in healed.stdout
        again = subprocess.run([sys.executable, "-c", "from unlearn.heal import self_heal; print('\\n'.join(self_heal()))"],
                               env=env, capture_output=True, text=True, timeout=120)
        assert "nothing to seed" in again.stdout
    finally:
        subprocess.run(["docker", "rm", "-f", name], capture_output=True)
