"""Is the simulator rigged in our favour? C (Unlearn) under a noisier simulator, against the clean baselines.

    python eval/noise.py [--levels 0,0.2,0.4] [--seeds 0,1,2]     # writes eval/results/noise.json

The simulator picks wrong answers through the same option-to-misconception map Unlearn reads. noise=p adds
answers that map can't explain (eval/simulator.py): a uniformly random wrong option outside the student's
planted misconceptions with probability p, and a correct answer slipping to a random wrong option with
probability p/2. Only C is re-run (template wording, no LLM calls). A, B and B+ are their saved clean-simulator
scores from eval/results/eval.json; B+ ran on seed 0 only, so it is compared with C's seed 0 at the same p.
"""

import argparse
import json
import statistics

from eval import bootstrap as BS
from eval import run_eval as RE

OUT = RE.RESULTS / "noise.json"
COMPARED = ("top1_misconception", "top3_misconception", "root_cause_accuracy", "session2_recall")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--levels", default="0,0.2,0.4")
    ap.add_argument("--seeds", default="0,1,2")
    a = ap.parse_args(argv)
    clean = json.loads((RE.RESULTS / "eval.json").read_text())
    seeds = [s.strip() for s in a.seeds.split(",")]
    base = {c: {m: clean["summary"][c][m]["mean"] for m in COMPARED} for c in ("A", "B")}
    base["B+"] = {m: clean["per_seed"]["0"]["B+"][m] for m in COMPARED}
    levels = {}
    for p in [float(x) for x in a.levels.split(",")]:
        stem = f"noise_tmp_p{p}"
        RE.main(["--conditions", "C", "--seeds", a.seeds, "--noise", str(p), "--out", stem, "--no-calibrate"])
        r = json.loads((RE.RESULTS / f"{stem}.json").read_text())
        for ext in ("json", "md"):
            (RE.RESULTS / f"{stem}.{ext}").unlink()
        scores = BS.scores_for(r, "C", seeds, noise=p)
        seed0 = BS.scores_for(r, "C", ["0"], noise=p)
        c = {m: round(statistics.mean(s[m] for s in scores), 3) for m in BS.METRICS}
        c0 = {m: round(statistics.mean(s[m] for s in seed0), 3) for m in COMPARED}
        levels[str(p)] = {
            "C": c, "C_ci95": BS.metric_intervals(scores), "C_seed0": c0, "n": len(scores),
            "beats_clean": {m: {"A": c[m] > base["A"][m], "B": c[m] > base["B"][m], "B+ (seed 0)": c0[m] > base["B+"][m]}
                            for m in COMPARED},
        }
        print(f"p={p}: " + ", ".join(f"{m} {c[m]:.0%}" for m in COMPARED))
    OUT.write_text(json.dumps({"method": __doc__.split("\n\n")[2].strip(), "seeds": [int(s) for s in seeds],
                               "clean_baselines": base, "levels": levels}, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
