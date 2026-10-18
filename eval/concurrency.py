"""Concurrency demo (SPEC "Concurrency demo"): one FalkorDB graph per class, so classes never queue on
each other's writes.

    python eval/concurrency.py [--students 30] [--rounds 6]

1. Two class graphs (GRAPH.COPY of class_template). N simulated students in EACH run at the same time
   through the async client. Each answer runs a Diagnoser step's query mix: NEXT_QUESTION, RECORD_ATTEMPT,
   UPDATE_SHOWED (wrong answers) and ROOT_CAUSE. Reports p50/p95 per graph, reads and writes separately.
2. Isolation. Small probe writes into class A, one at a time, from a separate process with its own connection
   (so only server-side waiting shows), in these conditions:
     baseline              nothing else running
     load_on_other_graph   K writers hammer class B with heavy writes
     load_on_same_graph    the same K writers hammer class A
     sessions_on_other_graph / sessions_on_same_graph   the same with a realistic load: N students running
                                                         ordinary sessions in B, or in A
   FalkorDB serialises writes per graph: probes should be unaffected by load on B and queue behind load on A.
Writes eval/results/concurrency.json. The two graphs are deleted afterwards.

    python eval/concurrency.py --scale-classes 10 [--students 30]

3. Scale (only this part runs; its result is merged into concurrency.json under "scale"). N class graphs with
   30 students each run sessions at the same time, looping until the probes are done. During that load, probe
   writes go first into an extra idle class graph, then into busy class 1. Reports p50/p95 per class, total
   queries per second over the load window, and any query errors (FalkorDB's pending-query queue is bounded).
"""

import argparse
import asyncio
import concurrent.futures
import json
import os
import statistics
import time
from pathlib import Path

from falkordb.asyncio import FalkorDB

from eval.simulator import Simulator
from unlearn import queries as Q
from unlearn.db import delete_graph, recreate_graph, run_batched

OUT = Path(__file__).resolve().parent / "results" / "concurrency.json"
GRAPHS = ("class_conc_a", "class_conc_b")
PROBES = 200
WRITERS = 4
HEAVY_ROWS = 20000


def pct(xs, p):
    xs = sorted(xs)
    k = (len(xs) - 1) * p
    lo, hi = int(k), min(int(k) + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


def stats(ms: list[float]) -> dict:
    return {"n": len(ms), "p50_ms": round(pct(ms, 0.5), 2), "p95_ms": round(pct(ms, 0.95), 2),
            "mean_ms": round(statistics.mean(ms), 2)}


async def timed(graph, query, params, out: list, read_only=False):
    t0 = time.perf_counter()
    res = await (graph.ro_query(query, params) if read_only else graph.query(query, params))
    out.append((time.perf_counter() - t0) * 1000)
    return res


async def student_session(graph, sim, sid: str, rounds: int, reads: list, writes: list) -> None:
    """One simulated student's answers, each with a Diagnoser step's query mix."""
    s = sim.student(sid)
    constructs = [s.target] + sorted(sim.prerequisites_of(s.target))
    sess = f"{sid}-conc"
    for i in range(rounds):
        cid = constructs[i % len(constructs)]
        res = await timed(graph, Q.NEXT_QUESTION, {"sid": sid, "cid": cid, "sess": sess}, reads, read_only=True)
        if not res.result_set:
            continue
        qid = res.result_set[0][0]
        res = await timed(graph, Q.RECORD_ATTEMPT, {"sid": sid, "qid": qid, "key": s.answer(qid),
                                                    "ts": time.time_ns() // 1_000_000, "sess": sess}, writes)
        mid = res.result_set[0][1] if res.result_set else None
        if mid is not None:
            await timed(graph, Q.UPDATE_SHOWED, {"sid": sid, "mid": mid, "ts": time.time_ns() // 1_000_000}, writes)
        await timed(graph, Q.ROOT_CAUSE, {"sid": sid, "cid": s.target}, reads, read_only=True)


def probe_process(graph_name: str, tag: str, n: int) -> list[float]:
    """Probe writes from a separate process with its own connection, so the load's event loop and client
    can't delay them: only server-side waiting shows up."""
    from unlearn.db import run
    ms = []
    for i in range(n):
        t0 = time.perf_counter()
        run(graph_name, Q.CONC_PROBE_WRITE, {"id": f"{tag}-{i}", "ts": i})
        ms.append((time.perf_counter() - t0) * 1000)
    return ms


_POOL: concurrent.futures.ProcessPoolExecutor | None = None


async def probes(graph_name: str, tag: str) -> list[float]:
    return await asyncio.get_running_loop().run_in_executor(_POOL, probe_process, graph_name, tag, PROBES)


async def heavy_writer(graph, stop: asyncio.Event, done: list) -> None:
    while not stop.is_set():
        t0 = time.perf_counter()
        await graph.query(Q.CONC_HEAVY_WRITE, {"n": HEAVY_ROWS, "w": 1})
        done.append((time.perf_counter() - t0) * 1000)


async def probes_under_load(db, probe_graph: str, load_graph: str | None, tag: str) -> tuple[dict, dict | None]:
    stop, heavy = asyncio.Event(), []
    writers = [asyncio.create_task(heavy_writer(db.select_graph(load_graph), stop, heavy))
               for _ in range(WRITERS)] if load_graph else []
    if writers:
        await asyncio.sleep(0.3)  # let the load start
    ms = await probes(probe_graph, tag)
    stop.set()
    await asyncio.gather(*writers)
    return stats(ms), (stats(heavy) if heavy else None)


async def probes_under_sessions(db, sim, probe_graph: str, load_graph: str, students: int, rounds: int, tag: str) -> dict:
    """Probe writes into probe_graph while `students` simulated students run normal sessions in load_graph."""
    reads, writes = [], []
    load = asyncio.gather(*[student_session(db.select_graph(load_graph), sim, f"s{i:02d}", rounds, reads, writes)
                            for i in range(1, students + 1)])
    ms = await probes(probe_graph, tag)
    await load
    return stats(ms)


async def main_async(students: int, rounds: int) -> dict:
    db = FalkorDB(host=os.getenv("FALKOR_HOST", "localhost"), port=int(os.getenv("FALKOR_PORT", "6379")),
                  password=os.getenv("FALKOR_PASSWORD") or None, max_connections=4 * students + 16)
    sim = Simulator(seed=0)
    per_graph = {}
    lat = {g: {"reads": [], "writes": []} for g in GRAPHS}
    t0 = time.perf_counter()
    await asyncio.gather(*[student_session(db.select_graph(g), sim, f"s{i:02d}", rounds, lat[g]["reads"], lat[g]["writes"])
                           for g in GRAPHS for i in range(1, students + 1)])
    wall = time.perf_counter() - t0
    for g in GRAPHS:
        both = lat[g]["reads"] + lat[g]["writes"]
        per_graph[g] = {**stats(both), "reads": stats(lat[g]["reads"]), "writes": stats(lat[g]["writes"])}

    a, b = GRAPHS
    await probes(a, "warm")  # start the probe process and its connection before timing
    baseline, _ = await probes_under_load(db, a, None, "base")
    other, other_heavy = await probes_under_load(db, a, b, "other")
    same, same_heavy = await probes_under_load(db, a, a, "same")
    # The same comparison with a realistic load: a class of students running ordinary sessions.
    sess_other = await probes_under_sessions(db, sim, a, b, students, rounds * 3, "sess-other")
    sess_same = await probes_under_sessions(db, sim, a, a, students, rounds * 3, "sess-same")
    await db.aclose() if hasattr(db, "aclose") else None
    return {"graphs": list(GRAPHS), "students_per_graph": students, "rounds_per_student": rounds,
            "both_classes_wall_s": round(wall, 2), "per_graph": per_graph,
            "isolation": {"baseline": baseline, "load_on_other_graph": other, "load_on_same_graph": same,
                          "heavy_write": {"writers": WRITERS, "rows_per_write": HEAVY_ROWS,
                                          "on_other_graph": other_heavy, "on_same_graph": same_heavy},
                          "probes": PROBES,
                          "sessions_on_other_graph": sess_other, "sessions_on_same_graph": sess_same},
            "falkordb_image": "falkordb/falkordb:v4.20.7"}


async def looping_student(graph, sim, sid: str, rounds: int, lat: list, errors: list, stop: asyncio.Event) -> None:
    """A student who keeps running sessions until stopped (at least one), timing every query, counting errors."""
    first = True
    while first or not stop.is_set():
        first = False
        try:
            await student_session(graph, sim, sid, rounds, lat, lat)
        except Exception as e:  # e.g. "Max pending queries exceeded": report it, keep the load going
            errors.append(type(e).__name__ + ": " + str(e)[:80])
            await asyncio.sleep(0.05)


async def scale_async(classes: list[str], idle: str, students: int, rounds: int) -> dict:
    db = FalkorDB(host=os.getenv("FALKOR_HOST", "localhost"), port=int(os.getenv("FALKOR_PORT", "6379")),
                  password=os.getenv("FALKOR_PASSWORD") or None, max_connections=len(classes) * students + 16)
    sim = Simulator(seed=0)
    await probes(idle, "warm")
    idle_base = stats(await probes(idle, "idle-base"))
    lat = {g: [] for g in classes}
    errors: list[str] = []
    stop = asyncio.Event()
    t0 = time.perf_counter()
    load = asyncio.gather(*[looping_student(db.select_graph(g), sim, f"s{i:02d}", rounds, lat[g], errors, stop)
                            for g in classes for i in range(1, students + 1)])
    await asyncio.sleep(0.5)  # let every class get going
    into_idle = stats(await probes(idle, "idle-load"))
    into_busy = stats(await probes(classes[0], "busy-load"))
    stop.set()
    await load
    wall = time.perf_counter() - t0
    await db.aclose() if hasattr(db, "aclose") else None
    total = sum(len(v) for v in lat.values())
    return {"classes": len(classes), "students_per_class": students, "rounds_per_session": rounds,
            "load_window_s": round(wall, 2), "queries": total, "queries_per_s": round(total / wall),
            "per_class": {g: stats(v) for g, v in lat.items()},
            "all_classes": stats([x for v in lat.values() for x in v]),
            "errors": len(errors), "error_kinds": sorted(set(errors))[:5],
            "probe_writes": {"probes": PROBES, "idle_class_no_load": idle_base, "idle_class_during_load": into_idle,
                             "busy_class_1_during_load": into_busy},
            "host": f"one laptop, Docker Desktop VM with {os.cpu_count()} host CPUs; FalkorDB in Docker"}


def scale(classes: int, students: int, rounds: int) -> int:
    graphs = [f"class_conc_scale_{i:02d}" for i in range(1, classes + 1)]
    idle = "class_conc_scale_idle"
    for g in graphs + [idle]:
        recreate_graph("class_template", g)
        run_batched(g, Q.LOAD_STUDENTS, [{"id": f"s{i:02d}", "alias": f"s{i:02d}"} for i in range(1, students + 1)])
    global _POOL
    _POOL = concurrent.futures.ProcessPoolExecutor(max_workers=1)
    try:
        result = asyncio.run(scale_async(graphs, idle, students, rounds))
    finally:
        _POOL.shutdown()
        for g in graphs + [idle]:
            delete_graph(g)
    saved = json.loads(OUT.read_text()) if OUT.exists() else {}
    saved["scale"] = result
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(saved, indent=2) + "\n")
    a, pw = result["all_classes"], result["probe_writes"]
    print(f"{classes} classes x {students} students for {result['load_window_s']}s: {result['queries']} queries, "
          f"{result['queries_per_s']}/s, all-class p50 {a['p50_ms']} / p95 {a['p95_ms']} ms, errors {result['errors']}")
    for g, v in result["per_class"].items():
        print(f"  {g}: p50 {v['p50_ms']} / p95 {v['p95_ms']} ms (n={v['n']})")
    for k, v in pw.items():
        if isinstance(v, dict):
            print(f"  probe writes, {k}: p50 {v['p50_ms']} / p95 {v['p95_ms']} ms")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--students", type=int, default=30)
    ap.add_argument("--rounds", type=int, default=6)
    ap.add_argument("--scale-classes", type=int, help="run only the scale test with this many class graphs")
    a = ap.parse_args(argv)
    if a.scale_classes:
        return scale(a.scale_classes, a.students, a.rounds)
    for g in GRAPHS:
        recreate_graph("class_template", g)
        run_batched(g, Q.LOAD_STUDENTS, [{"id": f"s{i:02d}", "alias": f"s{i:02d}"} for i in range(1, a.students + 1)])
    global _POOL
    _POOL = concurrent.futures.ProcessPoolExecutor(max_workers=1)
    try:
        result = asyncio.run(main_async(a.students, a.rounds))
    finally:
        _POOL.shutdown()
        for g in GRAPHS:
            delete_graph(g)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2) + "\n")
    iso = result["isolation"]
    print(f"{a.students} students in each of {len(GRAPHS)} graphs at once: {result['both_classes_wall_s']}s")
    for g, v in result["per_graph"].items():
        print(f"  {g}: all p50 {v['p50_ms']} / p95 {v['p95_ms']} ms | writes p50 {v['writes']['p50_ms']} / p95 {v['writes']['p95_ms']}")
    for k in ("baseline", "load_on_other_graph", "load_on_same_graph", "sessions_on_other_graph", "sessions_on_same_graph"):
        print(f"  probe writes into A, {k}: p50 {iso[k]['p50_ms']} / p95 {iso[k]['p95_ms']} ms")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
