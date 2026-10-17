"""Two design checks behind README "Design decisions worth knowing" (template wording, no LLM calls).

    python eval/design_checks.py                 # both, seeds 0-2; writes eval/results/design_checks.json
    python eval/design_checks.py --only recall   # or --only thresholds

recall      The eval's 90 students (30 x seeds 0-2) each run session 1. On the same histories, three recall rules
            pick what session 2 opens with (the opening names the top 2):
              spec       RECALL_SPEC_RULE: confidence > 0.6 (seen twice), newest first
              strongest  RECALL_STRONGEST_FIRST: seen once or more, strongest first
              root_first RECALL (current): seen once or more, on the last diagnosed root first
            recall: the opening names a planted misconception. precision: named misconceptions that were planted,
            over students who were named anything. empty: students the rule names nothing for.
thresholds  Every planted (root, target within 4 hops) pair the simulator can make, one fresh student each, one
            session. The Diagnoser stops at root_cause evidence >= EVIDENCE_MIN leading by >= LEAD_MIN; counts
            how often the planted root is root_cause's top row, at the current 1.5 / 0.5 and the looser 1.0 / 0.33.
"""

import argparse
import functools
import json
import statistics
from pathlib import Path

from eval.simulator import Simulator
from unlearn import llm
from unlearn import queries as Q
from unlearn import tools as T
from unlearn.agents import diagnoser, runner
from unlearn.db import delete_graph, recreate_graph, run, run_batched

OUT = Path(__file__).resolve().parent / "results" / "design_checks.json"
WRITER = functools.partial(llm.write, providers=[])
RULES = {"spec": Q.RECALL_SPEC_RULE, "strongest": Q.RECALL_STRONGEST_FIRST, "root_first": Q.RECALL}
THRESHOLDS = {"1.5/0.5": (1.5, 0.5), "1.0/0.33": (1.0, 0.33)}
NAMED = 2  # the session-2 opening names the top 2


def session_one(class_id: str, student, sess: str) -> None:
    """Session 1 as the eval's C runs it: diagnosis, then the Tutor's check question."""
    out = runner.start(class_id, student.id, student.target, session_id=sess, writer=WRITER)
    while out["kind"] == "question":
        out = runner.answer(class_id, sess, out["question"]["id"], student.answer(out["question"]), writer=WRITER)
    if out.get("next_task"):
        tut = runner.remediate(class_id, sess, writer=WRITER)
        if tut["kind"] == "check":
            runner.answer(class_id, sess, tut["question"]["id"], student.answer(tut["question"]), writer=WRITER)


def recall_check(seeds: list[int]) -> dict:
    res = {k: {"recall": [], "precision": [], "empty": 0} for k in RULES}
    for seed in seeds:
        class_id = f"design_recall_s{seed}"
        g = T.graph_name(class_id)
        recreate_graph("class_template", g)
        try:
            sids = [f"s{i:02d}" for i in range(1, 31)]
            run_batched(g, Q.LOAD_STUDENTS, [{"id": s, "alias": s} for s in sids])
            for sid in sids:
                student = Simulator(seed=seed).student(sid)  # the eval's students
                session_one(class_id, student, f"{sid}-1")
                planted = {r["name"] for r in run(g, Q.MISCONCEPTION_NAMES, {"ids": student.misconceptions})[0]}
                for k, q in RULES.items():
                    named = [r["misconception"] for r in run(g, q, {"sid": sid})[0]][:NAMED]
                    hits = [n in planted for n in named]
                    res[k]["recall"].append(any(hits))
                    if named:
                        res[k]["precision"].append(sum(hits) / len(named))
                    else:
                        res[k]["empty"] += 1
        finally:
            delete_graph(g)
    return {k: {"recall": round(statistics.mean(v["recall"]), 3), "precision": round(statistics.mean(v["precision"]), 3),
                "empty": v["empty"], "n": len(v["recall"])} for k, v in res.items()}


def threshold_check(seeds: list[int]) -> dict:
    out = {}
    for label, (ev_min, lead_min) in THRESHOLDS.items():
        diagnoser.EVIDENCE_MIN, diagnoser.LEAD_MIN = ev_min, lead_min
        out[label] = {}
        for seed in seeds:
            sim = Simulator(seed=seed)
            pairs = [(r, t) for r in sim.candidates for t in sorted(sim.dependants(r, 4))]
            class_id = f"design_thr_s{seed}"
            g = T.graph_name(class_id)
            recreate_graph("class_template", g)
            try:
                run_batched(g, Q.LOAD_STUDENTS, [{"id": f"b{i}", "alias": f"B{i}"} for i in range(len(pairs))])
                top1 = 0
                for i, (root, target) in enumerate(pairs):
                    s = sim.student(f"b{i}", root_cause=root, target=target)
                    res = runner.run_session_sync(class_id, f"b{i}", target, lambda _s, q, s=s: s.answer(q),
                                                  session_id=f"b{i}-1", writer=WRITER)
                    rows = [st for st in res.steps if st.agent == "Diagnoser" and st.tool == "root_cause"][-1].rows
                    top1 += bool(rows) and rows[0]["id"] == root
                out[label][str(seed)] = {"top1": top1, "pairs": len(pairs)}
            finally:
                delete_graph(g)
    diagnoser.EVIDENCE_MIN, diagnoser.LEAD_MIN = THRESHOLDS["1.5/0.5"]
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seeds", default="0,1,2")
    ap.add_argument("--only", choices=["recall", "thresholds"])
    a = ap.parse_args(argv)
    seeds = [int(s) for s in a.seeds.split(",")]
    result = json.loads(OUT.read_text()) if OUT.exists() else {}
    if a.only != "thresholds":
        result["recall"] = recall_check(seeds)
        print("recall rules:", json.dumps(result["recall"]))
    if a.only != "recall":
        result["thresholds"] = threshold_check(seeds)
        print("thresholds:", json.dumps(result["thresholds"]))
    result["method"] = __doc__.split("\n\n")[1]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
