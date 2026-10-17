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
  p50 / p95 latency             wall time of one session-1 diagnosis, timed only when every LLM call in it was fresh
A run whose A/B prompts are mostly cached times few diagnoses, so --pool-latency pools every timed diagnosis of
A, B and B+ across saved runs of the same model (each fresh call is timed once, in the run that made it):
    python eval/run_eval.py --pool-latency eval_pre_review,eval   # writes latency_pooled into eval.json
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
from unlearn.db import delete_graph, recreate_graph, run_batched

RESULTS = Path(__file__).resolve().parent / "results"
METRICS = ["top1_misconception", "top3_misconception", "root_cause_accuracy", "questions_to_diagnosis",
           "session2_recall", "latency_p50_ms", "latency_p95_ms"]
LABELS = {"A": "A. No memory", "B": "B. Vector RAG", "B+": "B+. LLM + graph as text", "C": "C. Unlearn"}
ORDER = ["A", "B", "B+", "C"]
CALLS_PER_STUDENT = {"A": BL.POOL_QUESTIONS + 1, "B": 2, "B+": 2, "C": 6}  # upper bounds before retries and cache
BPLUS_MAX_MIN = 75  # B+ projected over this many minutes -> seed 0 only


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


def run_ab(cond: str, provider, sim, student, judge, graph_text: str | None = None) -> dict:
    """A, B or B+ for one student. Predictions are the ids the model chose from its candidate lists."""
    answers = BL.answer_session(student, BL.pool_questions(sim, student))
    constructs = BL.prerequisite_candidates(sim, student, judge.construct_names)
    cached_before = BL.STATS["cached"]
    t0 = time.perf_counter()
    if cond == "A":
        dx = BL.condition_a(provider, judge, answers, constructs)
    else:
        dx = BL.condition_b(provider, judge, answers, constructs, graph_text if cond == "B+" else None)
    # A diagnosis served (even partly) from the disk cache, or one that made no call (A with no wrong answer), says
    # nothing about latency: leave it out.
    latency = (time.perf_counter() - t0) * 1000 if BL.STATS["cached"] == cached_before and dx["calls"] else None
    opening = BL.opening_a(provider) if cond == "A" else BL.opening_b(provider, answers)  # B+ opens as B does
    return {"predicted": dx["predicted"], "root": dx["root"], "asked": len(answers), "latency_ms": latency,
            "recalled": judge.recalled(opening, student.misconceptions), "opening": opening,
            "json_ok": dx["json_ok"], "misconceptions_unmapped": dx["misconceptions_unmapped"],
            "root_unmapped": dx["root_unmapped"], "raw": (dx.get("raw") or "")[:600],
            "planted": {"root": student.root_cause, "misconceptions": student.misconceptions}}


def _round(x):
    return None if x is None else round(x, 1)


def score(rows: list[dict], students: dict) -> dict:
    def mean(xs):
        return round(statistics.mean(xs), 3) if xs else None
    return {
        "top1_misconception": mean([bool(r["predicted"]) and r["predicted"][0] in students[r["sid"]].misconceptions for r in rows]),
        "top3_misconception": mean([any(m in students[r["sid"]].misconceptions for m in r["predicted"][:3]) for r in rows]),
        "root_cause_accuracy": mean([r["root"] == students[r["sid"]].root_cause for r in rows]),
        "questions_to_diagnosis": mean([r["asked"] for r in rows]),
        "session2_recall": mean([r["recalled"] for r in rows]),
        "latency_p50_ms": _round(pct([r["latency_ms"] for r in rows if r["latency_ms"] is not None], 0.5)),
        "latency_p95_ms": _round(pct([r["latency_ms"] for r in rows if r["latency_ms"] is not None], 0.95)),
        "latency_n": sum(r["latency_ms"] is not None for r in rows),
        # scoring audit (A, B, B+): outputs that weren't valid JSON, or named no offered id
        "invalid_json": sum(r.get("json_ok") is False for r in rows),
        "misconceptions_unmapped": sum(bool(r.get("misconceptions_unmapped")) for r in rows),
        "root_unmapped": sum(bool(r.get("root_unmapped")) for r in rows),
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
    conds = ORDER
    rows = [("Top-1 misconception", "top1_misconception", "%"), ("Top-3 misconception", "top3_misconception", "%"),
            ("Root-cause accuracy", "root_cause_accuracy", "%"), ("Questions to diagnosis", "questions_to_diagnosis", ""),
            ("Session-2 recall", "session2_recall", "%"), ("p50 latency (ms)", "latency_p50_ms", ""),
            ("p95 latency (ms)", "latency_p95_ms", "")]

    pooled = (result.get("latency_pooled") or {}).get("overall", {})

    def cell(c, m, unit):
        if c not in result["summary"]:
            return "not run"
        if m.startswith("latency_"):
            if c in pooled:
                v = pooled[c][m.replace("latency_", "")]
                return "–" if v is None else f"{v:.1f} (n={pooled[c]['n']})"
            n = sum(result["per_seed"][s][c]["latency_n"] for s in result["per_seed"] if c in result["per_seed"][s])
            n_note = f" n={n}"
        else:
            n_note = ""
        v = result["summary"][c][m]
        if v is None:
            return "–"
        f = (lambda x: f"{100 * x:.0f}%") if unit == "%" else (lambda x: f"{x:.1f}" if isinstance(x, float) else str(x))
        return f"{f(v['mean'])} ({f(v['min'])}–{f(v['max'])}{n_note})"
    meta = result["meta"]
    lines = [f"# Eval results", "",
             f"{meta['students']} simulated students × seeds {meta['seeds']} × {meta['sessions']} sessions. "
             f"Mean (min–max across seeds). A/B model: {meta['llm'] or 'none'}; C: template wording. "
             f"n per condition: {meta.get('n_per_condition')}.", "",
             "| Metric | " + " | ".join(LABELS[c] for c in conds) + " |", "| --- " * (len(conds) + 1) + "|"]
    lines += [f"| {name} | " + " | ".join(cell(c, m, u) for c in conds) + " |" for name, m, u in rows]
    for c, why in meta.get("not_run", {}).items():
        lines.append(f"\n{LABELS[c]} not run: {why}")
    if pooled:
        lines.append(f"\nLatency: p50 / p95 over every timed diagnosis in {', '.join(result['latency_pooled']['runs'])} "
                     "(A, B, B+; C from this run only), n = diagnoses timed.")
    lines.append("\nThe simulator uses the same option-to-misconception map as Unlearn, which favours Unlearn; see the README.")
    return "\n".join(lines) + "\n"


POOLED = ("A", "B", "B+")  # C makes no LLM calls: its latency comes from the current run only


def _lat(rows: list[dict]) -> list[float]:
    return [r["latency_ms"] for r in rows if r["latency_ms"] is not None and r["latency_ms"] >= 1]  # < 1 ms: no call


def pool_latency(stems: list[str], out: str) -> int:
    """Pool A's, B's and B+'s timed diagnoses across saved runs into out's latency_pooled (no LLM calls)."""
    runs = {stem: json.loads((RESULTS / f"{stem}.json").read_text()) for stem in stems}
    assert len({r["meta"]["llm"] for r in runs.values()}) == 1, "runs used different A/B models"
    result = runs[out] if out in runs else json.loads((RESULTS / f"{out}.json").read_text())

    def stats(seeds):
        cell = {}
        for c in result["meta"]["conditions_run"]:
            srcs = stems if c in POOLED else [out]
            by = {stem: _lat([r for s in seeds for r in runs.get(stem, result)["students"].get(s, {}).get(c, [])])
                  for stem in srcs}
            xs = [x for v in by.values() for x in v]
            cell[c] = {"p50_ms": _round(pct(xs, 0.5)), "p95_ms": _round(pct(xs, 0.95)), "n": len(xs),
                       "n_by_run": {k: len(v) for k, v in by.items()}}
        return cell
    seeds = [str(s) for s in result["meta"]["seeds"]]
    result["latency_pooled"] = {
        "runs": stems, "model": result["meta"]["llm"],
        "rule": "every diagnosis timed in any of the runs (no cached call, at least one call), pooled; C from "
                f"{out} only, since it makes no LLM calls",
        "overall": stats(seeds), "per_seed": {s: stats([s]) for s in seeds}}
    (RESULTS / f"{out}.json").write_text(json.dumps(result, indent=2, default=str) + "\n")
    (RESULTS / f"{out}.md").write_text(markdown(result))
    print(json.dumps(result["latency_pooled"]["overall"]))
    return 0


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
    prov = next(p for p in llm.hosted_providers() if p.name == which)  # first model of that provider
    if model:
        import dataclasses
        prov = dataclasses.replace(prov, default_model=model, model_env="")
    return (prov, None) if prov.key else (None, f"no {prov.key_env} in .env")


def time_bplus(provider, seed: int, n: int) -> dict:
    """Time n real (uncached) B+ prompts on a scratch copy of the template: B+ prompts carry the whole graph."""
    g = T.graph_name(f"bplus_timing_s{seed}")
    recreate_graph("class_template", g)
    try:
        judge, text = BL.Judge(g), BL.graph_as_text(g)
        sim = Simulator(seed=seed)
        BL.reset_stats()
        for i in range(1, n + 1):
            student = Simulator(seed=seed).student(f"s{i:02d}")
            answers = BL.answer_session(student, BL.pool_questions(sim, student))
            constructs = BL.prerequisite_candidates(sim, student, judge.construct_names)
            BL.condition_b(provider, judge, answers, constructs, text + f"\n(timing {time.time_ns()})")
        calls = max(BL.STATS["calls"], 1)
        return {"calls": BL.STATS["calls"], "seconds_per_call": round(BL.STATS["seconds"] / calls, 1),
                "prompt_tokens": llm.LAST_USAGE.get("prompt_tokens")}
    finally:
        delete_graph(g)


def calibrate(provider, sims: dict, n: int = 5) -> dict:
    """Time n real A/B prompts before the run: seconds and tokens per call, and whether the JSON parses."""
    BL.reset_stats()
    parsed = 0
    for i, (sim, student) in enumerate(list(sims.values())[:n]):
        answers = BL.answer_session(student, BL.pool_questions(sim, student))
        prompt = ("Attempt history:\n" + BL.history_text(answers) + '\n\nReply as JSON: {"misconceptions": [the 3 most likely], '
                  f'"root_cause": "the earlier skill this student is most likely missing"}} (calibration {time.time_ns()})')  # never cached
        parsed += BL.parse_json(BL._call(provider, BL.DIAG_SYSTEM, prompt)) is not None
    calls = max(BL.STATS["calls"], 1)
    return {"calls": BL.STATS["calls"], "cached": BL.STATS["cached"], "json_valid": f"{parsed}/{n}",
            "seconds_per_call": round(BL.STATS["seconds"] / calls, 2), "tokens_per_call": round(BL.STATS["tokens"] / calls, 1)}


def merge(stems: list[str], out: str) -> int:
    """Combine runs made seed by seed (same model, same code) into one result: per-seed rows kept as they are,
    the summary and n per condition recomputed."""
    parts = [json.loads((RESULTS / f"{stem}.json").read_text()) for stem in stems]
    llms = {p["meta"]["llm"] for p in parts}
    assert len(llms) == 1, f"runs used different A/B models: {llms}"
    per_seed, students = {}, {}
    for p in parts:
        for seed, conds in p["per_seed"].items():
            assert seed not in per_seed, f"seed {seed} appears in more than one run"
            per_seed[seed], students[seed] = conds, p["students"][seed]
    ran = [c for c in ORDER if any(c in v for v in per_seed.values())]
    meta = {**parts[0]["meta"], "seeds": sorted(int(s_) for s_ in per_seed), "conditions_run": ran,
            "n_per_condition": {c: sum(v[c]["n"] for v in per_seed.values() if c in v) for c in ran},
            "seeds_per_condition": {c: sorted(int(s_) for s_, v in per_seed.items() if c in v) for c in ran},
            "merged_from": stems, "calibration": [p["meta"].get("calibration") for p in parts],
            "llm_calls": [p["meta"].get("llm_calls") for p in parts],
            "not_run": {c: "not requested" for c in ORDER if c not in ran}}
    result = {"meta": meta, "per_seed": per_seed, "summary": summarise(per_seed, ran), "students": students}
    (RESULTS / f"{out}.json").write_text(json.dumps(result, indent=2, default=str) + "\n")
    (RESULTS / f"{out}.md").write_text(markdown(result))
    print(markdown(result))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--students", type=int, default=30)
    ap.add_argument("--seeds", default="0,1,2")
    ap.add_argument("--conditions", default="A,B,B+,C")
    ap.add_argument("--llm", default="ollama", choices=["ollama", "gemini", "openrouter", "groq"],
                    help="the single model A and B use (C is template-only)")
    ap.add_argument("--model", help="model tag override (default: OLLAMA_MODEL or qwen3.5:27b-q4_K_M for ollama)")
    ap.add_argument("--max-calls", type=int, help="hard cap on uncached A/B LLM calls (free-tier quotas)")
    ap.add_argument("--out", default="eval", help="results file stem in eval/results (eval, crosscheck)")
    ap.add_argument("--no-calibrate", action="store_true", help="skip the 5 timing calls (quota-limited cross-checks)")
    ap.add_argument("--merge", help="comma-separated result stems to combine into --out (e.g. eval_seed0,eval_seeds12)")
    ap.add_argument("--pool-latency", help="comma-separated result stems whose A/B/B+ timings to pool into --out")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    if a.merge:
        return merge(a.merge.split(","), a.out)
    if a.pool_latency:
        return pool_latency(a.pool_latency.split(","), a.out)
    seeds = [int(s) for s in a.seeds.split(",")]
    conds = [c.strip().upper() for c in a.conditions.split(",")]
    needs_llm = any(c in ("A", "B", "B+") for c in conds)
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

    bplus_seeds = seeds
    if "B+" in conds and not a.dry_run:
        bplus = time_bplus(provider, seeds[0], min(2, a.students))
        projected = bplus["seconds_per_call"] * a.students * len(seeds) / 60
        print(f"B+ timing on {bplus['calls']} real prompts ({bplus['prompt_tokens']} prompt tokens each): "
              f"{bplus['seconds_per_call']} s per call. Projected B+ time for {len(seeds)} seed(s): {projected:.0f} min", flush=True)
        if projected > BPLUS_MAX_MIN and len(seeds) > 1:
            bplus_seeds = seeds[:1]
            print(f"Over {BPLUS_MAX_MIN} min, so B+ runs on seed {seeds[0]} only.", flush=True)
        calibration = {**(calibration or {}), "bplus": bplus, "bplus_seeds": bplus_seeds}
        BL.reset_stats(BL.STATS["limit"])

    writer = functools.partial(llm.write, providers=[])  # C: template wording, graph-derived metrics
    per_seed, raw, stopped = {}, {}, None
    for seed in seeds:
        sim = Simulator(seed=seed)
        sids = [f"s{i:02d}" for i in range(1, a.students + 1)]
        students = {sid: sim.student(sid) for sid in sids}
        class_id = f"{a.out}_s{seed}"  # per output, so a cross-check can run alongside the main eval
        g = T.graph_name(class_id)
        recreate_graph("class_template", g)
        run_batched(g, Q.LOAD_STUDENTS, [{"id": s, "alias": s} for s in sids])
        judge = BL.Judge(g)
        graph_text = BL.graph_as_text(g) if "B+" in conds else None
        per_seed[seed], raw[seed] = {}, {}
        for c in conds:
            if c == "B+" and seed not in bplus_seeds:
                continue
            t0 = time.time()
            rows = []
            for sid in sids:
                student = Simulator(seed=seed).student(sid)  # fresh answer stream per condition, same planted state
                try:
                    r = run_c(class_id, student, writer, judge) if c == "C" else run_ab(c, provider, sim, student, judge, graph_text)
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

    ran = [c for c in ORDER if c in conds and any(c in per_seed[s] for s in per_seed)]
    result = {
        "meta": {"students": a.students, "seeds": seeds, "sessions": 2, "conditions_run": ran,
                 "llm": f"{provider.name} / {provider.model}" if provider else None,
                 "llm_role": "A and B only, one model, no fallback; C uses template wording",
                 "n_per_condition": {c: sum(per_seed[s][c]["n"] for s in per_seed if c in per_seed[s]) for c in ran},
                 "seeds_per_condition": {c: sorted(int(s) for s in per_seed if c in per_seed[s]) for c in ran},
                 "llm_calls": {k: (round(v, 1) if isinstance(v, float) else v) for k, v in BL.STATS.items()} if needs_llm else None,
                 "calibration": calibration, "stopped": stopped,
                 "not_run": {c: why or "not requested" for c in ORDER if c not in ran},
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
