"""Drive the three agents through the graph, one step at a time.

Every task's state lives in the class graph (Task state, the question it is waiting on, this session's
ATTEMPTED edges), so any process can run the next step:

  start(...)      create the Session and its `diagnose` task, claim it, run Diagnoser.begin -> first question
  answer(...)     route the answer to whichever task in the session is waiting for one (diagnose or remediate)
  remediate(...)  claim the session's `remediate` task and run Tutor.begin -> explanation + check question

The HTTP API calls these once per request. run_session() drives a simulated student through the same steps
with asyncio worker loops, one per agent, each claiming only that session's tasks. Teacher `review` tasks
need no student input: a worker (teacher_worker) claims and handles them whole.
"""

import asyncio
from dataclasses import dataclass, field

from unlearn import llm, tools
from unlearn.agents.base import Answerer, Step, StepError
from unlearn.agents.diagnoser import Diagnoser
from unlearn.agents.teacher import Teacher
from unlearn.agents.tutor import Tutor

INTERACTIVE = {"diagnose": Diagnoser, "remediate": Tutor}
POLL_S = 0.02


def _agent(cls, class_id, on_step, writer):
    return cls(class_id, on_step=on_step, writer=writer)


def _guarded(class_id: str, task_id: str, fn, *args):
    """Run one step; on failure mark the task failed so the chain ends instead of hanging."""
    try:
        return fn(*args)
    except StepError:
        raise
    except Exception as e:
        tools.fail_task(class_id, task_id, repr(e))
        raise


# --- Step API (one call = one agent step) --------------------------------------

def start(class_id: str, student_id: str, construct_id: int, session_id: str | None = None,
          on_step=None, writer=llm.write, worker: str = "http", new_session: bool = True) -> dict:
    """Open a session on a target construct and return the Diagnoser's first question (plus recall).
    new_session=False diagnoses inside a Session that is already open (a pilot session starts with its check)."""
    session_id = session_id or f"{student_id}-{tools.now_ms()}"
    task_id = f"{session_id}-diagnose"
    if new_session:
        n = tools.start_session(class_id, student_id, session_id)["rows"][0]["n"]
    else:
        n = tools.session_lookup(class_id, session_id)["rows"][0]["n"]
    tools.create_task(class_id, task_id, "diagnose", student_id, "Diagnoser", construct_id=construct_id,
                      session_id=session_id)
    if not tools.claim_task(class_id, task_id, "Diagnoser", worker)["rows"]:
        raise StepError(f"task {task_id} was claimed by another worker")
    out = _guarded(class_id, task_id, _agent(Diagnoser, class_id, on_step, writer).begin, task_id)
    return {**out, "session_id": session_id, "session_n": n}


def awaiting(class_id: str, session_id: str) -> dict:
    """The session's task that is waiting for an answer."""
    for t in tools.session_tasks(class_id, session_id)["rows"]:
        if t["state"] == "working" and t["pending_qid"] is not None:
            return t
    raise StepError(f"session {session_id} is not waiting for an answer")


def answer(class_id: str, session_id: str, question_id: str, key: str, explanation: str | None = None,
           on_step=None, writer=llm.write) -> dict:
    t = awaiting(class_id, session_id)
    agent = _agent(INTERACTIVE[t["kind"]], class_id, on_step, writer)
    out = _guarded(class_id, t["id"], agent.answer, t["id"], question_id, key, explanation)
    return {**out, "session_id": session_id, "agent": agent.name}


def remediate(class_id: str, session_id: str, on_step=None, writer=llm.write, worker: str = "http") -> dict:
    """Claim the session's remediate task and return the Tutor's explanation and check question."""
    task = next((t for t in tools.session_tasks(class_id, session_id)["rows"]
                 if t["kind"] == "remediate" and t["state"] == "submitted"), None)
    if task is None or not tools.claim_task(class_id, task["id"], "Tutor", worker)["rows"]:
        raise StepError(f"session {session_id} has no remediate task waiting")
    out = _guarded(class_id, task["id"], _agent(Tutor, class_id, on_step, writer).begin, task["id"])
    return {**out, "session_id": session_id}


# --- Worker loops ----------------------------------------------------------------

async def teacher_worker(class_ids, stop: asyncio.Event, errors: list | None = None, session_id: str | None = None,
                         on_step=None, writer=llm.write, worker: str = "teacher-1") -> None:
    """Claim and handle Teacher review tasks until stop is set. class_ids is a list or a callable returning one."""
    while not stop.is_set():
        handled = False
        for class_id in (class_ids() if callable(class_ids) else class_ids):
            got = await asyncio.to_thread(tools.claim, class_id, "Teacher", worker, session_id)
            if got["rows"]:
                handled = True
                task_id = got["rows"][0]["id"]
                try:
                    await asyncio.to_thread(_agent(Teacher, class_id, on_step, writer).handle, task_id)
                except Exception as e:
                    if errors is not None:
                        errors.append(e)
                    await asyncio.to_thread(tools.fail_task, class_id, task_id, repr(e))
        if not handled:
            await asyncio.sleep(POLL_S)


async def _interactive_worker(cls, class_id, session_id, answerer, stop, errors, on_step, writer):
    """Claim this session's tasks for one interactive agent and answer its questions with the answerer."""
    agent = _agent(cls, class_id, on_step, writer)
    while not stop.is_set():
        got = await asyncio.to_thread(tools.claim, class_id, agent.name, f"{agent.name}-sim", session_id)
        if not got["rows"]:
            await asyncio.sleep(POLL_S)
            continue
        task_id = got["rows"][0]["id"]
        try:
            student_id = (await asyncio.to_thread(tools.task_context, class_id, task_id))["rows"][0]["student_id"]
            out = await asyncio.to_thread(agent.begin, task_id)
            while out["kind"] in ("question", "check"):
                key = answerer(student_id, out["question"])
                out = await asyncio.to_thread(agent.answer, task_id, out["question"]["id"], key)
        except Exception as e:
            errors.append(e)
            await asyncio.to_thread(tools.fail_task, class_id, task_id, repr(e))


@dataclass
class SessionResult:
    session_id: str
    session_n: int
    root_task_id: str
    chain: list[dict]
    steps: list[Step] = field(default_factory=list)


async def run_session(class_id: str, student_id: str, construct_id: int, answerer: Answerer,
                      session_id: str | None = None, on_step=None, writer=llm.write,
                      timeout_s: float = 120.0) -> SessionResult:
    """Run one simulated session to the end: Diagnoser -> Tutor -> (Teacher), each a worker claiming from the graph."""
    steps: list[Step] = []

    def record(step: Step) -> None:
        steps.append(step)
        if on_step:
            on_step(step)

    session_id = session_id or f"{student_id}-{tools.now_ms()}"
    root = f"{session_id}-diagnose"
    n = (await asyncio.to_thread(tools.start_session, class_id, student_id, session_id))["rows"][0]["n"]
    await asyncio.to_thread(tools.create_task, class_id, root, "diagnose", student_id, "Diagnoser",
                            construct_id=construct_id, session_id=session_id)

    stop, errors = asyncio.Event(), []
    workers = [asyncio.create_task(_interactive_worker(cls, class_id, session_id, answerer, stop, errors, record, writer))
               for cls in (Diagnoser, Tutor)]
    workers.append(asyncio.create_task(teacher_worker([class_id], stop, errors, session_id, record, writer,
                                                      worker="Teacher-sim")))
    try:
        async with asyncio.timeout(timeout_s):
            while not errors:
                if (await asyncio.to_thread(tools.chain, class_id, root))["open"] == 0:
                    break
                await asyncio.sleep(POLL_S)
    finally:
        stop.set()
        await asyncio.gather(*workers)
    if errors:
        raise errors[0]
    chain = (await asyncio.to_thread(tools.chain, class_id, root))["rows"]
    return SessionResult(session_id, n, root, chain, steps)


def run_session_sync(*args, **kwargs) -> SessionResult:
    return asyncio.run(run_session(*args, **kwargs))
