"""The demo video's scenario: two students, the same 40% on fractions, opposite root causes.

    python scripts/demo_scenario.py              # (re)build class_demo_video: students + their fractions check
    python scripts/demo_scenario.py --verify 10  # rebuild and play sessions 1 and 2 for both, 10 times over

class_demo_video is a GRAPH.COPY of class_template with two simulated students:
  Asha  root cause: Identify the Lowest Common Multiple (345), outside the Fractions topic, 2 hops below the target
  Ben   root cause: Identify equivalent fractions when presented as numbers (409), 2 hops below the target
Target for both: Add fractions involving mixed number fractions with different denominators (429).

Both take the same five-question fractions check first: two questions on adding mixed numbers with the SAME
denominator (428), which neither root affects, and the three questions on the target, which both roots break.
Both score 2/5 = 40%. The check is recorded as real ATTEMPTED edges in a 'quiz:<student>' session, so the
score on screen is read from the graph.

The students are noiseless simulator profiles stored on their Student nodes (sim_* properties, which no
agent query reads): every answer is a fixed function of the question, so the whole demo replays exactly.
In the UI, "Let the simulated student answer" and Autoplay use the same profile.
"""

import argparse
import sys
import time

from redis.exceptions import ConnectionError

from eval.simulator import Simulator
from unlearn import queries as Q
from unlearn import tools as T
from unlearn.agents import runner
from unlearn.db import copy_graph, delete_graph, run_batched

CLASS_ID = "demo_video"
TARGET = 429
CHECK_KNOWN = 428  # same-denominator mixed numbers: both students can do it
SEED = 0
STUDENTS = {
    "asha": {"alias": "Asha", "root": 345, "mids": [15341]},   # finds a common multiple, not the lowest
    "ben": {"alias": "Ben", "root": 409, "mids": [22639]},     # changes only the denominator for an equivalent fraction
}


def check_questions(sim: Simulator) -> list[str]:
    by = {}
    for q in sim.bank.values():
        by.setdefault(q["construct_id"], []).append(q["id"])
    return sorted(by[CHECK_KNOWN])[:2] + sorted(by[TARGET])


def simulated(sid: str, sim: Simulator | None = None):
    p = STUDENTS[sid]
    return (sim or Simulator(seed=SEED, noiseless=True)).student(sid, p["root"], TARGET, p["mids"])


def build() -> dict:
    g = T.graph_name(CLASS_ID)
    for attempt in (1, 2):
        try:
            delete_graph(g)
            copy_graph("class_template", g)
            break
        except ConnectionError as e:  # FalkorDB v4.20.7 can segfault in GRAPH.COPY (README: known issues)
            if attempt == 2:
                raise
            print(f"FalkorDB dropped the connection during GRAPH.COPY ({e}); waiting for it to restart", file=sys.stderr)
            time.sleep(8)
    run_batched(g, Q.LOAD_STUDENT_PROFILES, [
        {"id": sid, "alias": p["alias"], "root": p["root"], "target": TARGET, "mids": p["mids"], "seed": SEED}
        for sid, p in STUDENTS.items()])
    sim = Simulator(seed=SEED, noiseless=True)
    for sid in STUDENTS:
        student = simulated(sid, sim)
        for qid in check_questions(sim):
            T.record_attempt(CLASS_ID, sid, qid, student.answer(qid), f"quiz:{sid}")
    return {r["id"]: r["check"] for r in T.class_students(CLASS_ID)["rows"]}


def play(sid: str, session: int) -> dict:
    """One full session through the step API: diagnosis, then the Tutor and its check question."""
    student = simulated(sid)
    sess = f"{sid}-video-{session}"
    out = runner.start(CLASS_ID, sid, TARGET, session_id=sess)
    recall = [r["misconception"] for r in out["recall"]]
    while out["kind"] == "question":
        out = runner.answer(CLASS_ID, sess, out["question"]["id"], student.answer(out["question"]))
    dx = out
    score = T.session_score(CLASS_ID, sid, sess)["rows"][0]
    if dx.get("next_task"):
        tut = runner.remediate(CLASS_ID, sess)
        if tut["kind"] == "check":
            runner.answer(CLASS_ID, sess, tut["question"]["id"], student.answer(tut["question"]))
    return {"recall": recall, "root": dx["root"]["id"] if dx["root"] else None, "asked": dx["asked"],
            "score": f"{score['correct']}/{score['total']}", "chain": dx["root"]["chain"] if dx["root"] else []}


def verify(runs: int) -> bool:
    ok_all = True
    for i in range(1, runs + 1):
        checks = build()
        line = [f"run {i:2d}"]
        for sid, p in STUDENTS.items():
            s1, s2 = play(sid, 1), play(sid, 2)
            planted = {r["mid"]: r["name"] for r in T.showed_on(CLASS_ID, sid, p["root"])["rows"]}
            recalled = [planted[m] for m in p["mids"] if planted.get(m) in s2["recall"]]
            ok = (checks[sid] == {"correct": 2, "total": 5} and s1["root"] == p["root"] and bool(recalled))
            ok_all &= ok
            line.append(f"{p['alias']}: check {checks[sid]['correct']}/{checks[sid]['total']}, session 1 root {s1['root']} "
                        f"({'right' if s1['root'] == p['root'] else 'WRONG'}) after {s1['asked']} q, "
                        f"session 2 recalls planted: {'yes' if recalled else 'NO'}, session 2 root {s2['root']}")
        print(" | ".join(line))
    build()  # leave a fresh class for the live demo
    return ok_all


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--verify", type=int, default=0, help="rebuild and play both students this many times")
    a = ap.parse_args(argv)
    if a.verify:
        ok = verify(a.verify)
        print("ALL RUNS CORRECT" if ok else "SOME RUNS FAILED")
        return 0 if ok else 1
    checks = build()
    for sid, p in STUDENTS.items():
        c = checks[sid]
        print(f"{p['alias']}: fractions check {c['correct']}/{c['total']} ({100 * c['correct'] // c['total']}%), "
              f"planted root {p['root']}, target {TARGET}")
    print(f"class_{CLASS_ID} ready: open http://localhost:8000/?class={CLASS_ID}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
