"""Simulate every student in a class graph, as the Teacher view's "Simulate the class" does, with template
wording only (no LLM calls). Each session runs Diagnoser -> Tutor -> Teacher, so no task is left open.

    python scripts/simulate_class.py --id demo --sessions 2

The Render image runs this at build time, so the live Teacher tab opens with cohorts and pending proposals.
"""

import argparse
import functools
import os

from eval.simulator import Simulator
from unlearn import llm, tools
from unlearn.agents import runner

TEMPLATE_WRITER = functools.partial(llm.write, providers=[])


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--id", default="demo", help="class id (graph class_<id>)")
    ap.add_argument("--sessions", type=int, default=2)
    a = ap.parse_args(argv)
    sim = Simulator(seed=int(os.getenv("UNLEARN_SIM_SEED", "0")))  # the API's simulator for seeded students
    ids = [r["id"] for r in tools.class_students(a.id)["rows"]]
    hits = 0
    for sid in ids:
        student = sim.student(sid)
        for _ in range(a.sessions):
            res = runner.run_session_sync(a.id, sid, student.target, lambda _s, q, s=student: s.answer(q),
                                          writer=TEMPLATE_WRITER)
            dx = [st for st in res.steps if st.agent == "Diagnoser" and st.tool == "root_cause"][-1].rows
            hits += bool(dx) and dx[0]["id"] == student.root_cause
    cohorts = tools.cohorts(a.id)["rows"]
    pending = tools.proposals(a.id, "pending")["rows"]
    print(f"class_{a.id}: {len(ids) * a.sessions} sessions, planted root named in {hits}; "
          f"{len(cohorts)} cohorts, {len(pending)} pending proposals")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
