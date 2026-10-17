"""p50/p95 latency for every agent tool over 50 calls on a class graph. Writes eval/results/latency.json.

    python eval/latency.py --class demo [--calls 50] [--warm-sessions]

Timing is wall-clock around the Python tool function, so it includes the client round trip and receipt
building, not just FalkorDB execution. Each tool gets 3 warm-up calls first (not counted). With
--warm-sessions every student first runs one simulated session (seed 0), so the read tools see realistic
SHOWED/ATTEMPTED state instead of an empty class. Write tools run against throwaway ids.
"""

import argparse
import json
import platform
import statistics
import time
from pathlib import Path

from eval.simulator import Simulator
from unlearn import tools as T
from unlearn.agents.runner import run_session_sync
from unlearn.db import client

OUT = Path(__file__).resolve().parent / "results" / "latency.json"
WARMUP = 3


def pct(xs: list[float], p: float) -> float:
    xs = sorted(xs)
    k = (len(xs) - 1) * p
    lo, hi = int(k), min(int(k) + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


def measure(fn, n: int) -> dict:
    for i in range(WARMUP):
        fn(-1 - i)
    ms = []
    for i in range(n):
        t0 = time.perf_counter()
        fn(i)
        ms.append((time.perf_counter() - t0) * 1000)
    return {"n": n, "p50_ms": round(pct(ms, 0.5), 2), "p95_ms": round(pct(ms, 0.95), 2),
            "mean_ms": round(statistics.mean(ms), 2), "max_ms": round(max(ms), 2)}


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--class", dest="class_id", default="demo")
    ap.add_argument("--calls", type=int, default=50)
    ap.add_argument("--warm-sessions", action="store_true")
    a = ap.parse_args(argv)
    c, n = a.class_id, a.calls

    sim = Simulator(seed=0)
    students = [f"s{i:02d}" for i in range(1, 31)]
    sims = {sid: sim.student(sid) for sid in students}
    if a.warm_sessions:
        for sid in students:
            run_session_sync(c, sid, sims[sid].target, lambda _sid, q, s=sims[sid]: s.answer(q),
                             session_id=f"bench-{sid}")

    def sid_of(i):
        return students[i % len(students)]

    def target_of(i):
        return sims[sid_of(i)].target

    root_of = {sid: sims[sid].root_cause for sid in students}
    questions = sorted(sim.bank)
    run_id = T.now_ms()
    T.start_session(c, "s01", f"bench-{run_id}")
    misconception_ids = sorted({o["misconception_id"] for q in sim.bank.values() for o in q["options"]
                                if o.get("misconception_id")})
    explanations = ["I added the tops and added the bottoms", "I multiplied the two denominators to get the LCM",
                    "the bigger denominator means the bigger fraction", "I just swapped the top and bottom"]

    # Setup for coordination tools: a pool of tasks to claim, a chain to hand off along, proposals to decide.
    for i in range(-WARMUP, n):
        T.create_task(c, f"bench-{run_id}-claim-{i}", "diagnose", "s01", "Diagnoser", construct_id=410,
                      session_id=f"bench-{run_id}")
    T.create_task(c, f"bench-{run_id}-h--{WARMUP + 1}", "diagnose", "s01", "Diagnoser", construct_id=410,
                  session_id=f"bench-{run_id}")

    results = {}
    results["record_attempt"] = measure(lambda i: T.record_attempt(
        c, "s01", questions[i % len(questions)], "A", f"bench-{run_id}"), n)
    results["diagnose_text"] = measure(lambda i: T.diagnose_text(c, 410, explanations[i % len(explanations)]), n)
    results["next_question"] = measure(lambda i: T.next_question(c, sid_of(i), root_of[sid_of(i)]), n)
    results["root_cause"] = measure(lambda i: T.root_cause(c, sid_of(i), target_of(i)), n)
    results["probe_frontier"] = measure(lambda i: T.probe_frontier(c, sid_of(i), target_of(i)), n)
    results["learning_path"] = measure(lambda i: T.learning_path(c, sid_of(i), target_of(i), root_of[sid_of(i)]), n)
    results["recall"] = measure(lambda i: T.recall(c, sid_of(i)), n)
    results["pick_skill"] = measure(lambda i: T.pick_skill(c, misconception_ids[i % len(misconception_ids)]), n)
    results["update_skill"] = measure(lambda i: T.update_skill(c, "Fraction wall", i % 2 == 0), n)
    results["cohorts"] = measure(lambda i: T.cohorts(c), n)
    results["keystones"] = measure(lambda i: T.keystones(c), n)
    results["bridges"] = measure(lambda i: T.bridges(), n)
    results["claim"] = measure(lambda i: T.claim(c, "Diagnoser", f"bench-w{i}"), n)
    results["handoff"] = measure(lambda i: T.handoff(c, f"bench-{run_id}-h-{i - 1}", "s01", "Tutor", "remediate",
                                                     f"bench-{run_id}-h-{i}"), n)
    results["propose"] = measure(lambda i: T.propose(c, f"bench-{run_id}-p-{i}", "assign_practice",
                                                     {"construct_id": 408}, ["s01"]), n)
    results["decide"] = measure(lambda i: T.decide(c, f"bench-{run_id}-p-{i}", "approved"), n)

    assert set(results) == {f.__name__ for f in T.TOOLS}
    info = client().connection.info("server")
    out = {
        "class_graph": T.graph_name(c), "calls_per_tool": n, "warmup_calls": WARMUP,
        "warm_sessions": a.warm_sessions,
        "measured": "wall clock around the Python tool function (client round trip + receipt), localhost",
        "host": {"platform": platform.platform(), "python": platform.python_version(),
                 "redis_version": info.get("redis_version")},
        "falkordb_image": "falkordb/falkordb:v4.20.7",
        "notes": {"diagnose_text": "includes embedding the explanation with all-MiniLM-L6-v2 on CPU",
                  "bridges": "runs betweenness on the curriculum graph (2,258 constructs), not the class graph",
                  "decide": "approved assign_practice, so it includes the executor and its Event"},
        "tools": results,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2) + "\n")
    width = max(map(len, results))
    print(f"{'tool':<{width}}  {'p50 ms':>8}  {'p95 ms':>8}")
    for k, v in results.items():
        print(f"{k:<{width}}  {v['p50_ms']:>8.2f}  {v['p95_ms']:>8.2f}")


if __name__ == "__main__":
    main()
