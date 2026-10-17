"""Random-guess baseline for the eval's candidate lists (no LLM calls).

    python eval/random_baseline.py [--seeds 0,1,2] [--students 30]

For the same simulated students and answers the eval uses, the expected score of picking uniformly from the lists
each condition is shown:
  root cause            1 / |the target's prerequisites|  (the same list for A, B and B+; the planted root is on it)
  top-1 misconception   |planted ∩ candidates| / |candidates|
  top-3 misconception   1 - C(n-k, 3) / C(n, 3)  for n candidates of which k are planted (picks without replacement)
A's misconception list is the one retrieved for its last wrong answer (A's diagnosis is that call's); a student with
no wrong answer gets no A diagnosis, so 0. B and B+ share the session's top-10. C searches the whole graph, so it has
no list and no random-guess score. Writes eval/results/random_baseline.json.
"""

import argparse
import json
import statistics
from math import comb
from pathlib import Path

from eval import baselines as BL
from eval.simulator import Simulator
from unlearn.db import delete_graph, recreate_graph

OUT = Path(__file__).resolve().parent / "results" / "random_baseline.json"


def top_k_hit(n: int, k: int, picks: int) -> float:
    if n == 0 or k == 0:
        return 0.0
    picks = min(picks, n)
    return 1 - comb(n - k, picks) / comb(n, picks)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seeds", default="0,1,2")
    ap.add_argument("--students", type=int, default=30)
    a = ap.parse_args(argv)
    g = "class_random_baseline"
    recreate_graph("class_template", g)
    try:
        judge = BL.Judge(g)
        per_seed = {}
        for seed in [int(s) for s in a.seeds.split(",")]:
            sim = Simulator(seed=seed)
            rows = []
            for i in range(1, a.students + 1):
                student = Simulator(seed=seed).student(f"s{i:02d}")  # the same answer stream run_ab uses
                answers = BL.answer_session(student, BL.pool_questions(sim, student))
                prereqs = BL.prerequisite_candidates(sim, student, judge.construct_names)
                planted = set(student.misconceptions)
                wrong = [x for x in answers if not x[2]]
                a_cands = [i for i, _ in BL.retrieved(judge, wrong[-1:])] if wrong else []
                b_cands = [i for i, _ in BL.retrieved(judge, answers)]
                ka, kb = len(planted & set(a_cands)), len(planted & set(b_cands))
                rows.append({
                    "root": 1 / len(prereqs) if student.root_cause in {c for c, _ in prereqs} else 0.0,
                    "a_top1": ka / len(a_cands) if a_cands else 0.0, "a_top3": top_k_hit(len(a_cands), ka, 3),
                    "b_top1": kb / len(b_cands) if b_cands else 0.0, "b_top3": top_k_hit(len(b_cands), kb, 3),
                    "n_prereqs": len(prereqs), "n_a": len(a_cands), "n_b": len(b_cands),
                    "a_has_planted": ka > 0, "b_has_planted": kb > 0})
            mean = lambda key: round(statistics.mean(r[key] for r in rows), 3)  # noqa: E731
            per_seed[seed] = {
                "A": {"top1_misconception": mean("a_top1"), "top3_misconception": mean("a_top3"), "root_cause_accuracy": mean("root")},
                "B_and_Bplus": {"top1_misconception": mean("b_top1"), "top3_misconception": mean("b_top3"), "root_cause_accuracy": mean("root")},
                "candidate_list_sizes": {"prerequisites": mean("n_prereqs"), "A_misconceptions": mean("n_a"),
                                         "B_misconceptions": mean("n_b")},
                "planted_misconception_on_list": {"A": mean("a_has_planted"), "B_and_Bplus": mean("b_has_planted")},
                "n": len(rows)}
            print(f"seed {seed}: {json.dumps(per_seed[seed])}")
    finally:
        delete_graph(g)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"method": __doc__.split("\n\n")[1], "per_seed": per_seed}, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
