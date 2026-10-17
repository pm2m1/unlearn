"""Run the three agents as asyncio worker loops that claim Tasks from the class graph.

A session starts by creating a `diagnose` task. Each worker polls `claim` for its own agent, runs the
task, and hands off. The session is over when no task in the chain that began with the diagnose task is
still submitted or working. The graph is the only channel between agents.
"""

import asyncio
from dataclasses import dataclass, field

from unlearn import llm, tools
from unlearn.agents.base import Answerer, Step
from unlearn.agents.diagnoser import Diagnoser
from unlearn.agents.teacher import Teacher
from unlearn.agents.tutor import Tutor

AGENTS = (Diagnoser, Tutor, Teacher)
POLL_S = 0.02


@dataclass
class SessionResult:
    session_id: str
    session_n: int
    root_task_id: str
    chain: list[dict]
    steps: list[Step] = field(default_factory=list)


async def _worker(agent, worker_id: str, stop: asyncio.Event, errors: list) -> None:
    while not stop.is_set():
        got = await asyncio.to_thread(tools.claim, agent.class_id, agent.name, worker_id)
        if not got["rows"]:
            await asyncio.sleep(POLL_S)
            continue
        task_id = got["rows"][0]["id"]
        try:
            await asyncio.to_thread(agent.handle, task_id)
        except Exception as e:  # mark the task failed so the session ends instead of hanging
            errors.append(e)
            await asyncio.to_thread(tools.fail_task, agent.class_id, task_id, repr(e))


async def run_session(class_id: str, student_id: str, construct_id: int, answerer: Answerer,
                      session_id: str | None = None, on_step=None, writer=llm.write,
                      timeout_s: float = 120.0) -> SessionResult:
    """Start a session for one student on one construct and run Diagnoser -> Tutor -> Teacher to the end."""
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
    agents = [cls(class_id, answerer, on_step=record, writer=writer) for cls in AGENTS]
    workers = [asyncio.create_task(_worker(a, f"{a.name}-1", stop, errors)) for a in agents]
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
