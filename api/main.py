"""FastAPI app: sessions, answers, approvals, teacher views, receipts, and the static web UI at /.

Run:  PYTHONPATH=api:. uvicorn main:app --app-dir api --port 8000

Every route calls the step API (unlearn.agents.runner) or a fixed tool. State lives in the class graphs, so
any worker process can serve the next request for a session. On startup the app self-heals (seeds what is
missing) and starts one Teacher worker that claims `review` tasks from every class graph.
"""

import asyncio
import json
import logging
import os
import re
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from eval.simulator import Simulator
from unlearn import heal, receipts, tools
from unlearn.agents import runner
from unlearn.agents.base import StepError
from unlearn.agents.teacher_chat import chat
from unlearn.db import client, list_graphs, run
from unlearn import queries as Q

ROOT = Path(__file__).resolve().parents[1]
STATIC = Path(__file__).resolve().parent / "static"
RESULTS = ROOT / "eval" / "results"
SIM_SEED = int(os.getenv("UNLEARN_SIM_SEED", "0"))
TEACHER_POLL_S = 0.5
_CLASS_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("unlearn.api")


def class_ids() -> list[str]:
    return sorted(g.removeprefix("class_") for g in list_graphs()
                  if g.startswith("class_") and g != "class_template")


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.heal_log = []
    if os.getenv("UNLEARN_SELF_HEAL", "1") != "0":
        app.state.heal_log = await asyncio.to_thread(heal.self_heal)
    stop = asyncio.Event()
    worker = asyncio.create_task(_teacher_loop(stop))
    yield
    stop.set()
    await worker


async def _teacher_loop(stop: asyncio.Event) -> None:
    """The API's Teacher agent: claims review tasks handed off by Tutors in any class graph."""
    while not stop.is_set():
        try:
            for cid in await asyncio.to_thread(class_ids):
                got = await asyncio.to_thread(tools.claim, cid, "Teacher", "api-teacher")
                if got["rows"]:
                    task_id = got["rows"][0]["id"]
                    try:
                        await asyncio.to_thread(runner.Teacher(cid, on_step=receipts.Collector()).handle, task_id)
                    except Exception as e:
                        log.exception("teacher task %s failed", task_id)
                        await asyncio.to_thread(tools.fail_task, cid, task_id, repr(e))
        except Exception:
            log.exception("teacher loop")
        try:
            await asyncio.wait_for(stop.wait(), TEACHER_POLL_S)
        except asyncio.TimeoutError:
            pass


app = FastAPI(title="Unlearn", lifespan=lifespan)


@app.exception_handler(StepError)
async def _step_error(_, exc: StepError):
    return JSONResponse({"detail": str(exc)}, status_code=409)


# --- helpers -------------------------------------------------------------------

def _class(cid: str) -> str:
    if not _CLASS_ID.match(cid) or tools.graph_name(cid) not in list_graphs():
        raise HTTPException(404, f"no class {cid!r}")
    return cid


def _session_class(sess: str) -> tuple[str, str]:
    """(class_id, student_id) for a session id, found in the graph."""
    for cid in class_ids():
        rows = tools.session_lookup(cid, sess)["rows"]
        if rows:
            return cid, rows[0]["student_id"]
    raise HTTPException(404, f"no session {sess!r}")


def _sim(student_id: str):
    return Simulator(seed=SIM_SEED).student(student_id)


def _with_receipts(out: dict, col: receipts.Collector) -> dict:
    return {**out, "receipts": col.summaries()}


def _receipt_for(tool_out: dict, agent: str, name: str) -> str:
    from unlearn.agents.base import Step
    return receipts.add(Step(agent, "api", name, tools.query_names(tool_out), tool_out["cypher"], tool_out["params"],
                             tool_out["node_ids"], tool_out["rows"]))


def _tool_view(tool_out: dict, agent: str, name: str) -> dict:
    return {"rows": tool_out["rows"], "receipt": receipts.summary(_receipt_for(tool_out, agent, name))}


# --- health --------------------------------------------------------------------

@app.get("/health")
def health():
    graphs = sorted(list_graphs())
    counts = {g: run(g, Q.COUNT_NODES)[0][0]["n"] for g in graphs}
    version = None
    for mod in client().connection.execute_command("MODULE", "LIST"):
        fields = {(k.decode() if isinstance(k, bytes) else k): v for k, v in zip(mod[::2], mod[1::2])}
        name = fields.get("name")
        if (name.decode() if isinstance(name, bytes) else name) == "graph":
            v = int(fields.get("ver"))
            version = f"{v // 10000}.{v // 100 % 100}.{v % 100}"
    return {"ok": True, "graphs": graphs, "node_counts": counts, "falkordb_version": version,
            "receipts_stored": receipts.size(), "self_heal": getattr(app.state, "heal_log", [])}


# --- class lists for the UI ------------------------------------------------------

@app.get("/classes")
def classes():
    return {"classes": class_ids()}


@app.get("/classes/{cid}/students")
def students(cid: str):
    rows = tools.class_students(_class(cid))["rows"]
    for r in rows:
        r["default_target"] = _sim(r["id"]).target
    return {"students": rows}


@app.get("/classes/{cid}/targets")
def targets(cid: str):
    return {"targets": tools.targets(_class(cid))["rows"]}


@app.get("/classes/{cid}/students/{sid}/graph")
def student_graph(cid: str, sid: str, construct_id: int, session: str | None = None):
    out = tools.student_graph(_class(cid), sid, construct_id, session)
    return {**out["rows"][0], "receipt": receipts.summary(_receipt_for(out, "UI", "student_graph"))}


# --- sessions --------------------------------------------------------------------

class StartBody(BaseModel):
    construct_id: int | None = None


class AnswerBody(BaseModel):
    qid: str
    key: str | None = None
    explanation: str | None = None
    simulate: bool = Field(False, description="let the seeded simulator pick the key for this student")


@app.post("/classes/{cid}/students/{sid}/sessions")
def start_session(cid: str, sid: str, body: StartBody | None = None):
    _class(cid)
    target = body.construct_id if body and body.construct_id else _sim(sid).target
    col = receipts.Collector()
    out = runner.start(cid, sid, target, on_step=col)
    return _with_receipts({**out, "class_id": cid, "student_id": sid, "target": target}, col)


@app.post("/sessions/{sess}/answer")
def answer(sess: str, body: AnswerBody):
    cid, sid = _session_class(sess)
    key = body.key
    if body.simulate:
        t = runner.awaiting(cid, sess)
        key = _sim(sid).answer(t["pending_qid"])
    if not key:
        raise HTTPException(422, "key is required unless simulate is true")
    col = receipts.Collector()
    out = runner.answer(cid, sess, body.qid, key, body.explanation, on_step=col)
    return _with_receipts({**out, "class_id": cid, "student_id": sid}, col)


@app.get("/sessions/{sess}")
def session_state(sess: str):
    cid, sid = _session_class(sess)
    return {"class_id": cid, "student_id": sid, "tasks": tools.session_tasks(cid, sess)["rows"]}


@app.get("/sessions/{sess}/diagnosis")
def diagnosis(sess: str):
    cid, sid = _session_class(sess)
    tasks = tools.session_tasks(cid, sess)["rows"]
    dx = next((t for t in tasks if t["kind"] == "diagnose"), None)
    if dx is None or dx["state"] not in ("completed", "failed") and dx["pending_qid"] is not None:
        raise HTTPException(409, "diagnosis not finished")
    target = tools.task_context(cid, dx["id"])["rows"][0]["construct_id"]
    rc = tools.root_cause(cid, sid, target)
    rid = _receipt_for(rc, "Diagnoser", "root_cause")
    top = rc["rows"][0] if rc["rows"] else None
    return {"class_id": cid, "student_id": sid, "target": target, "root": top,
            "chain": top["chain"] if top else [], "evidence": top["evidence"] if top else None,
            "candidates": rc["rows"], "receipt_id": rid}


@app.post("/sessions/{sess}/remediate")
def remediate(sess: str):
    cid, sid = _session_class(sess)
    col = receipts.Collector()
    out = runner.remediate(cid, sess, on_step=col)
    return _with_receipts({**out, "class_id": cid, "student_id": sid}, col)


# --- simulation (fills the teacher view) ------------------------------------------

def _simulate(cid: str, sid: str, sessions: int) -> list[dict]:
    student = _sim(sid)
    out = []
    for _ in range(sessions):
        res = runner.run_session_sync(cid, sid, student.target, lambda _s, q: student.answer(q),
                                      on_step=receipts.Collector())
        dx = [s for s in res.steps if s.agent == "Diagnoser" and s.tool == "root_cause"][-1].rows
        out.append({"session_id": res.session_id, "n": res.session_n, "chain": [c["kind"] for c in res.chain],
                    "diagnosed": dx[0]["id"] if dx else None, "planted": student.root_cause})
    return out


@app.post("/classes/{cid}/students/{sid}/simulate")
def simulate(cid: str, sid: str, sessions: int = Query(2, ge=1, le=5)):
    t0 = time.time()
    runs = _simulate(_class(cid), sid, sessions)
    return {"student_id": sid, "sessions": runs, "seconds": round(time.time() - t0, 2)}


@app.post("/classes/{cid}/simulate-all")
def simulate_all(cid: str, sessions: int = Query(2, ge=1, le=5)):
    t0 = time.time()
    _class(cid)
    ids = [r["id"] for r in tools.class_students(cid)["rows"]]
    runs = {sid: _simulate(cid, sid, sessions) for sid in ids}
    hits = sum(1 for r in runs.values() for s in r if s["diagnosed"] == s["planted"])
    return {"students": len(ids), "sessions": len(ids) * sessions, "root_cause_hits": hits,
            "seconds": round(time.time() - t0, 2), "runs": runs}


# --- teacher views ------------------------------------------------------------------

@app.get("/classes/{cid}/cohorts")
def cohorts(cid: str):
    return _tool_view(tools.cohorts(_class(cid)), "Teacher", "cohorts")


@app.get("/classes/{cid}/keystones")
def keystones(cid: str):
    return _tool_view(tools.keystones(_class(cid)), "Teacher", "keystones")


@app.get("/classes/{cid}/bridges")
def bridges(cid: str):
    _class(cid)
    return _tool_view(tools.bridges(), "Teacher", "bridges")


@app.get("/classes/{cid}/proposals")
def proposals(cid: str, state: str | None = "pending"):
    return _tool_view(tools.proposals(_class(cid), state), "Teacher", "proposals")


class DecideBody(BaseModel):
    decision: str
    class_id: str | None = None


@app.post("/proposals/{pid}/decide")
def decide(pid: str, body: DecideBody):
    if body.decision not in tools.DECISIONS:
        raise HTTPException(422, f"decision must be one of {sorted(tools.DECISIONS)}")
    candidates = [_class(body.class_id)] if body.class_id else class_ids()
    cid = next((c for c in candidates if tools.proposal_lookup(c, pid)["rows"]), None)
    if cid is None:
        raise HTTPException(404, f"no proposal {pid!r}")
    out = tools.decide(cid, pid, body.decision)
    if not out["rows"]:
        raise HTTPException(409, f"proposal {pid} is not pending")
    return {"class_id": cid, "proposal_id": pid, **out["rows"][0],
            "receipt": receipts.summary(_receipt_for(out, "Teacher", "decide"))}


class ChatBody(BaseModel):
    message: str = Field(..., min_length=1, max_length=1000)


@app.post("/classes/{cid}/teacher/chat")
def teacher_chat(cid: str, body: ChatBody):
    col = receipts.Collector()
    out = chat(_class(cid), body.message, on_step=col)
    return _with_receipts(out, col)


# --- receipts and eval ----------------------------------------------------------------

@app.get("/receipts/{rid}")
def receipt(rid: str):
    r = receipts.get(rid)
    if r is None:
        raise HTTPException(404, "receipt not found (the store keeps the newest 5000)")
    return r


@app.get("/eval/results")
def eval_results():
    files = sorted(RESULTS.glob("*.json")) if RESULTS.exists() else []
    return {"results": {f.stem: json.loads(f.read_text()) for f in files}}


# --- static UI ----------------------------------------------------------------------

@app.get("/", include_in_schema=False)
def index():
    return FileResponse(STATIC / "index.html")


if STATIC.exists():
    app.mount("/static", StaticFiles(directory=STATIC), name="static")
