"""Bootstrap 95% confidence intervals for the saved eval results (no LLM calls, nothing re-run).

    python eval/bootstrap.py            # adds "bootstrap" to eval/results/eval.json

Each student's score is recomputed from the saved predictions: A, B and B+ rows carry the planted state, and
C's is rebuilt from the seeded simulator (planted state never depends on the answers). The pooled means must
match the saved summary, or the script stops. Then 1000 resamples of students, with replacement, give the
2.5th and 97.5th percentiles of each metric: overall (every seed the condition ran) and per seed. Latency
intervals resample the same pooled timings the tables report (run_eval.py --pool-latency).
"""

import json
import random
import statistics

from eval import run_eval as RE
from eval.simulator import Simulator

RESAMPLES = 1000
SEED = 0
METRICS = ("top1_misconception", "top3_misconception", "root_cause_accuracy", "questions_to_diagnosis",
           "session2_recall")


def student_scores(row: dict, planted_root: int, planted_mids: list[int]) -> dict:
    """One student's values, scored exactly as run_eval.score does."""
    p = row["predicted"]
    return {"top1_misconception": float(bool(p) and p[0] in planted_mids),
            "top3_misconception": float(any(m in planted_mids for m in p[:3])),
            "root_cause_accuracy": float(row["root"] == planted_root),
            "questions_to_diagnosis": float(row["asked"]),
            "session2_recall": float(bool(row["recalled"]))}


def scores_for(result: dict, cond: str, seeds: list[str], noise: float = 0.0) -> list[dict]:
    out = []
    for seed in seeds:
        for row in result["students"].get(seed, {}).get(cond, []):
            if row.get("planted"):
                root, mids = row["planted"]["root"], row["planted"]["misconceptions"]
            else:
                st = Simulator(seed=int(seed), noise=noise).student(row["sid"])
                root, mids = st.root_cause, st.misconceptions
            out.append(student_scores(row, root, mids))
    return out


def interval(values: list[float], stat=statistics.mean, resamples: int = RESAMPLES, seed: int = SEED) -> list[float]:
    rng = random.Random(seed)
    n = len(values)
    draws = sorted(stat([values[rng.randrange(n)] for _ in range(n)]) for _ in range(resamples))
    return [round(draws[int(0.025 * resamples)], 4), round(draws[int(0.975 * resamples) - 1], 4)]


def metric_intervals(scores: list[dict]) -> dict:
    return {m: interval([s[m] for s in scores]) for m in METRICS}


def latency_intervals(runs: dict, cond: str, seeds: list[str], pooled: bool) -> dict:
    xs = [x for stem, r in runs.items() if pooled or stem == "eval"
          for s in seeds for x in RE._lat(r["students"].get(s, {}).get(cond, []))]
    if len(xs) < 2:
        return {}
    return {"latency_p50_ms": interval(xs, lambda v: RE.pct(v, 0.5)),
            "latency_p95_ms": interval(xs, lambda v: RE.pct(v, 0.95)), "latency_n": len(xs)}


def main() -> int:
    path = RE.RESULTS / "eval.json"
    result = json.loads(path.read_text())
    meta = result["meta"]
    per_cond = meta.get("seeds_per_condition") or {c: meta["seeds"] for c in meta["conditions_run"]}
    pooled_runs = (result.get("latency_pooled") or {}).get("runs", ["eval"])
    runs = {stem: (result if stem == "eval" else json.loads((RE.RESULTS / f"{stem}.json").read_text()))
            for stem in pooled_runs}
    boot = {"resamples": RESAMPLES, "seed": SEED, "level": 0.95, "method": __doc__.split("\n\n")[2].strip(),
            "overall": {}, "per_seed": {}}
    for c in meta["conditions_run"]:
        seeds = [str(s) for s in per_cond[c]]
        scores = scores_for(result, c, seeds)
        for m in METRICS:  # the recomputed scores must reproduce the saved summary
            assert abs(statistics.mean(s[m] for s in scores) - result["summary"][c][m]["mean"]) < 0.002, (c, m)
        boot["overall"][c] = {**metric_intervals(scores), **latency_intervals(runs, c, seeds, c in RE.POOLED)}
        for s in seeds:
            boot["per_seed"].setdefault(s, {})[c] = {**metric_intervals(scores_for(result, c, [s])),
                                                     **latency_intervals(runs, c, [s], c in RE.POOLED)}
        print(c, {m: v for m, v in boot["overall"][c].items() if m != "latency_n"})
    result["bootstrap"] = boot
    path.write_text(json.dumps(result, indent=2, default=str) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
