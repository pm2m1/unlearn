"""The eval (SPEC "Evaluation"): 30 simulated students x 3 seeds x 2 sessions, conditions A, B and C.

    python eval/run_eval.py                    # all three conditions (A and B need an LLM API key)
    python eval/run_eval.py --conditions C     # Unlearn alone, no LLM needed (template wording)
    python eval/run_eval.py --dry-run          # print the LLM call budget and stop

  A  no memory   eval/baselines.py: one LLM call per wrong answer, current question only
  B  vector RAG  eval/baselines.py: full attempt history + top-10 misconceptions retrieved by embedding
  C  Unlearn     the agents through the step API (graph tools), each student in its own sessions

Every condition faces the same seeded simulated students (eval/simulator.py, SPEC rates) and is scored by the
same judge. Metrics per seed, then mean and min-max across seeds:
  top-1 / top-3 misconception   a planted misconception is the first / among the first three predicted
  root-cause accuracy           the predicted prerequisite is the planted broken one
  questions to diagnosis        questions asked in session 1 before the diagnosis
  session-2 recall              session 2's opening message names a planted misconception (judge)
  p50 / p95 latency             wall time of one session-1 diagnosis
A and B use one fixed provider (the first configured), with the disk cache; if none is configured the run
stops before doing anything. Writes eval/results/eval.json and eval/results/eval.md.
"""

import argparse
import functools
import json
import statistics
import sys
import time
from pathlib import Path

from eval import baselines as BL
from eval.simulator import Simulator
from unlearn import llm
from unlearn import queries as Q
from unlearn import tools as T
from unlearn.agents import runner
from unlearn.db import copy_graph, delete_graph, run_batched

RESULTS = Path(__file__).resolve().parent / "results"
METRICS = ["top1_misconception", "top3_misconception", "root_cause_accuracy", "questions_to_diagnosis",
           "session2_recall", "latency_p50_ms", "latency_p95_ms"]
LABELS = {"A": "A. No memory", "B": "B. Vector RAG", "C": "C. Unlearn"}
CALLS_PER_STUDENT = {"A": BL.POOL_QUESTIONS + 1, "B": 2, "C": 6}  # upper bounds before retries and cache


def pct(xs, p):
    xs = sorted(xs)
    if not xs:
        return None
    k = (len(xs) - 1) * p
    lo, hi = int(k), min(int(k) + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


def unlearn_predictions(class_id: str, sid: str, root: dict | None) -> list[int]:
    """C's ranked misconceptions: those on its root cause by evidence, then the student's others by confidence."""
    ranked = [r["mid"] for r in T.showed_on(class_id, sid, root["id"])["rows"]] if root else []
    others, _ = T.run(T.graph_name(class_id), Q.STUDENT_SHOWED, {"sid": sid})
    return ranked + [r["mid"] for r in others if r["mid"] not in ranked]


def finish_review(class_id: str, task_id: str | None, writer) -> None:
    """Run the Teacher on an escalation here, as a full session would, so no task is left for another worker."""
    if task_id and T.claim_task(class_id, task_id, "Teacher", "eval")["rows"]:
        runner.Teacher(class_id, writer=writer).handle(task_id)


def run_c(class_id: str, student, writer, judge) -> dict:
    sid = student.id
    t0 = time.perf_counter()
    out = runner.start(class_id, sid, student.target, session_id=f"{sid}-eval-1", writer=writer)
    while out["kind"] == "question":
        out = runner.answer(class_id, f"{sid}-eval-1", out["question"]["id"], student.answer(out["question"]), writer=writer)
    latency = (time.perf_counter() - t0) * 1000
    root, asked = out["root"], out["asked"]
    predicted = unlearn_predictions(class_id, sid, root)
    if out.get("next_task"):
        tut = runner.remediate(class_id, f"{sid}-eval-1", writer=writer)
        if tut["kind"] == "check":
            done = runner.answer(class_id, f"{sid}-eval-1", tut["question"]["id"], student.answer(tut["question"]), writer=writer)
            finish_review(class_id, done.get("next_task"), writer)
    s2 = runner.start(class_id, sid, student.target, session_id=f"{sid}-eval-2", writer=writer)
    opening = s2["greeting"]
    while s2["kind"] == "question":
        s2 = runner.answer(class_id, f"{sid}-eval-2", s2["question"]["id"], student.answer(s2["question"]), writer=writer)
    return {"predicted": predicted, "root": root["id"] if root else None, "asked": asked, "latency_ms": latency,
            "recalled": judge.recalled(opening, student.misconceptions), "opening": opening}


def run_ab(cond: str, provider, sim, student, judge) -> dict:
    answers = BL.answer_session(student, BL.pool_questions(sim, student))
    t0 = time.perf_counter()
    dx = BL.condition_a(provider, answers) if cond == "A" else BL.condition_b(provider, judge, answers)
    latency = (time.perf_counter() - t0) * 1000
    opening = BL.opening_a(provider) if cond == "A" else BL.opening_b(provider, answers)
    return {"predicted": judge.misconception_ids(dx["misconceptions"]), "root": judge.construct_id(dx["root_cause"]),
            "asked": len(answers), "latency_ms": latency, "recalled": judge.recalled(opening, student.misconceptions),
            "opening": opening, "raw": dx}


def score(rows: list[dict], students: dict) -> dict:
    def mean(xs):
        return round(statistics.mean(xs), 3) if xs else None
    return {
        "top1_misconception": mean([bool(r["predicted"]) and r["predicted"][0] in students[r["sid"]].misconceptions for r in rows]),
        "top3_misconception": mean([any(m in students[r["sid"]].misconceptions for m in r["predicted"][:3]) for r in rows]),
        "root_cause_accuracy": mean([r["root"] == students[r["sid"]].root_cause for r in rows]),
        "questions_to_diagnosis": mean([r["asked"] for r in rows]),
        "session2_recall": mean([r["recalled"] for r in rows]),
        "latency_p50_ms": round(pct([r["latency_ms"] for r in rows], 0.5), 1),
        "latency_p95_ms": round(pct([r["latency_ms"] for r in rows], 0.95), 1),
    }


def summarise(per_seed: dict, conds: list[str]) -> dict:
    out = {}
    for c in conds:
        out[c] = {}
        for m in METRICS:
            xs = [per_seed[s][c][m] for s in per_seed if c in per_seed[s] and per_seed[s][c][m] is not None]
            out[c][m] = {"mean": round(statistics.mean(xs), 3), "min": min(xs), "max": max(xs)} if xs else None
    return out


def markdown(result: dict) -> str:
    conds = ["A", "B", "C"]
    rows = [("Top-1 misconception", "top1_misconception", "%"), ("Top-3 misconception", "top3_misconception", "%"),
            ("Root-cause accuracy", "root_cause_accuracy", "%"), ("Questions to diagnosis", "questions_to_diagnosis", ""),
            ("Session-2 recall", "session2_recall", "%"), ("p50 latency (ms)", "latency_p50_ms", ""),
            ("p95 latency (ms)", "latency_p95_ms", "")]

    def cell(c, m, unit):
        if c not in result["summary"]:
            return "not run"
        v = result["summary"][c][m]
        if v is None:
            return "–"
        f = (lambda x: f"{100 * x:.0f}%") if unit == "%" else (lambda x: f"{x:.1f}" if isinstance(x, float) else str(x))
        return f"{f(v['mean'])} ({f(v['min'])}–{f(v['max'])})"
    meta = result["meta"]
    lines = [f"# Eval results", "",
             f"{meta['students']} simulated students × seeds {meta['seeds']} × {meta['sessions']} sessions. "
             f"Mean (min–max across seeds). A/B model: {meta['llm'] or 'none'}; C: template wording. "
             f"n per condition: {meta.get('n_per_condition')}.", "",
             "| Metric | " + " | ".join(LABELS[c] for c in conds) + " |", "| --- | --- | --- | --- |"]
    lines += [f"| {name} | " + " | ".join(cell(c, m, u) for c in conds) + " |" for name, m, u in rows]
    for c, why in meta.get("not_run", {}).items():
        lines.append(f"\n{LABELS[c]} not run: {why}")
    lines.append("\nThe simulator uses the same option-to-misconception map as Unlearn, which favours Unlearn; see the README.")
    return "\n".join(lines) + "\n"


def eval_provider(which: str, model: str | None):
    """The one model A and B use, with no fallback. None if it isn't available."""
    if which == "ollama":
        prov = llm.ollama_provider(model)
        import httpx
        try:
            tags = httpx.get(prov.base_url.rsplit("/v1", 1)[0] + "/api/tags", timeout=5).json()
        except Exception:
            return None, "Ollama is not reachable at " + prov.base_url
        if prov.model not in {m["name"] for m in tags.get("models", [])}:
            return None, f"Ollama has no model {prov.model!r} (ollama pull {prov.model})"
        return prov, None
    prov = next(p for p in llm.PROVIDERS if p.name == which)
    if model:
        import dataclasses
        prov = dataclasses.replace(prov, default_model=model, model_env="")
    return (prov, None) if prov.key else (None, f"no {prov.key_env} in .env")


def calibrate(provider, sims: dict, n: int = 5) -> dict:
    """Time n real A/B prompts before the run: seconds and tokens per call, and whether the JSON parses."""
    BL.reset_stats()
    parsed = 0
    for i, (sim, student) in enumerate(list(sims.values())[:n]):
        answers = BL.answer_session(student, BL.pool_questions(sim, student))
        prompt = ("Attempt history:\n" + BL.history_text(answers) + '\n\nReply as JSON: {"misconceptions": [the 3 most likely], '
                  '"root_cause": "the earlier skill this student is most likely missing"} (calibration)')
        parsed += BL.parse_json(BL._call(provider, BL.DIAG_SYSTEM, prompt)) is not None
    calls = max(BL.STATS["calls"], 1)
    return {"calls": BL.STATS["calls"], "cached": BL.STATS["cached"], "json_valid": f"{parsed}/{n}",
            "seconds_per_call": round(BL.STATS["seconds"] / calls, 2), "tokens_per_call": round(BL.STATS["tokens"] / calls, 1)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--students", type=int, default=30)
    ap.add_argument("--seeds", default="0,1,2")
    ap.add_argument("--conditions", default="A,B,C")
    ap.add_argument("--llm", default="ollama", choices=["ollama", "gemini", "openrouter", "groq"],
                    help="the single model A and B use (C is template-only)")
    ap.add_argument("--model", help="model tag override (default: OLLAMA_MODEL or qwen3.5:27b-q4_K_M for ollama)")
    ap.add_argument("--max-calls", type=int, help="hard cap on uncached A/B LLM calls (free-tier quotas)")
    ap.add_argument("--out", default="eval", help="results file stem in eval/results (eval, crosscheck)")
    ap.add_argument("--no-calibrate", action="store_true", help="skip the 5 timing calls (quota-limited cross-checks)")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    seeds = [int(s) for s in a.seeds.split(",")]
    conds = [c.strip().upper() for c in a.conditions.split(",")]
    needs_llm = any(c in conds for c in "AB")
    provider, why = eval_provider(a.llm, a.model) if needs_llm else (None, None)

    n = a.students * len(seeds)
    budget = {c: CALLS_PER_STUDENT[c] * n for c in conds if c in "AB"}
    print(f"Eval: {a.students} students × seeds {seeds} × 2 sessions, conditions {conds}")
    print(f"A/B model: {f'{provider.name} / {provider.model}' if provider else (why or 'not needed')}; C: template wording")
    if budget:
        print("A/B LLM calls, upper bound before cache: " + ", ".join(f"{c} {v}" for c, v in budget.items())
              + f" | total {sum(budget.values())}" + (f" | capped at {a.max_calls}" if a.max_calls else ""))
    if needs_llm and provider is None:
        print(f"A and B need an LLM and {why}, so the eval stops here without running anything.")
        return 2
    if a.dry_run:
        return 0

    calibration = None
    if needs_llm and not a.no_calibrate:
        sims = {sid: (Simulator(seed=seeds[0]), Simulator(seed=seeds[0]).student(sid))
                for sid in [f"s{i:02d}" for i in range(1, a.students + 1)]}
        calibration = calibrate(provider, sims, n=min(5, a.students))
        upper = min(sum(budget.values()), a.max_calls or 10**9)
        eta = upper * calibration["seconds_per_call"]
        print(f"Calibration on 5 real prompts: {calibration['seconds_per_call']} s and {calibration['tokens_per_call']} "
              f"tokens per call, JSON valid {calibration['json_valid']}. Projected A/B time (upper bound, before cache): "
              f"{eta / 60:.1f} min", flush=True)
        BL.reset_stats(None if a.max_calls is None else max(a.max_calls - calibration["calls"], 0))  # cap includes calibration
    elif needs_llm:
        BL.reset_stats(a.max_calls)

    writer = functools.partial(llm.write, providers=[])  # C: template wording, graph-derived metrics
    per_seed, raw, stopped = {}, {}, None
    for seed in seeds:
        sim = Simulator(seed=seed)
        sids = [f"s{i:02d}" for i in range(1, a.students + 1)]
        students = {sid: sim.student(sid) for sid in sids}
        class_id = f"{a.out}_s{seed}"  # per output, so a cross-check can run alongside the main eval
        g = T.graph_name(class_id)
        delete_graph(g)
        copy_graph("class_template", g)
        run_batched(g, Q.LOAD_STUDENTS, [{"id": s, "alias": s} for s in sids])
        judge = BL.Judge(g)
        per_seed[seed], raw[seed] = {}, {}
        for c in conds:
            t0 = time.time()
            rows = []
            for sid in sids:
                student = Simulator(seed=seed).student(sid)  # fresh answer stream per condition, same planted state
                try:
                    r = run_c(class_id, student, writer, judge) if c == "C" else run_ab(c, provider, sim, student, judge)
                except BL.BudgetExceeded as e:
                    stopped = f"{e} during {LABELS[c]}, seed {seed}, after {len(rows)} students"
                    break
                rows.append({"sid": sid, **r})
            if rows:
                per_seed[seed][c] = score(rows, students)
                per_seed[seed][c]["n"] = len(rows)
                raw[seed][c] = rows
                print(f"seed {seed} {LABELS[c]} (n={len(rows)}): {json.dumps(per_seed[seed][c])} ({time.time() - t0:.1f}s)", flush=True)
            if stopped:
                print("STOPPED:", stopped)
                break
        delete_graph(g)
        if stopped:
            break

    ran = [c for c in conds if any(c in per_seed[s] for s in per_seed)]
    result = {
        "meta": {"students": a.students, "seeds": seeds, "sessions": 2, "conditions_run": ran,
                 "llm": f"{provider.name} / {provider.model}" if provider else None,
                 "llm_role": "A and B only, one model, no fallback; C uses template wording",
                 "n_per_condition": {c: sum(per_seed[s][c]["n"] for s in per_seed if c in per_seed[s]) for c in ran},
                 "llm_calls": {k: (round(v, 1) if isinstance(v, float) else v) for k, v in BL.STATS.items()} if needs_llm else None,
                 "calibration": calibration, "stopped": stopped,
                 "not_run": {c: why or "not requested" for c in "ABC" if c not in ran},
                 "judge": {"recall_max_distance": BL.RECALL_MAX_DISTANCE, "pool_questions": BL.POOL_QUESTIONS},
                 "simulator_bias": "the simulator uses Unlearn's option-to-misconception map, which favours C"},
        "per_seed": per_seed,
        "summary": summarise({s: v for s, v in per_seed.items()}, ran),
        "students": {seed: {c: [{k: v for k, v in r.items() if k not in ("raw",)} for r in rows]
                            for c, rows in conds_rows.items()} for seed, conds_rows in raw.items()},
    }
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / f"{a.out}.json").write_text(json.dumps(result, indent=2, default=str) + "\n")
    (RESULTS / f"{a.out}.md").write_text(markdown(result))
    print(markdown(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
