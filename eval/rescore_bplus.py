"""Re-score B+ in a saved eval run on every id it was shown, from the LLM disk cache only (no LLM calls).

    python eval/rescore_bplus.py [--stem eval]

The first B+ run kept only ids from B's retrieved list, although its prompt lists every misconception and construct
with its id. This replays each seed B+ ran on in the eval's order (A, B, B+ share one simulator per seed), with every
completion served from the cache; a cache miss stops the script. A and B must reproduce their saved predictions.
Only B+'s scoring fields change (predicted, root, json_ok, *_unmapped). Its latency and openings are the saved ones.
It was run on the pre-review data (merged into eval/results/eval_pre_review.json); run_eval.py now scores B+ this way.
"""

import argparse
import json

from eval import baselines as BL
from eval import run_eval as RE
from eval.simulator import Simulator
from unlearn import llm
from unlearn import queries as Q
from unlearn import tools as T
from unlearn.db import delete_graph, recreate_graph, run_batched

SCORING = ("predicted", "root", "json_ok", "misconceptions_unmapped", "root_unmapped")


def cache_only():
    real = llm.complete

    def complete(provider, messages):
        if not llm._cache_path(provider, messages).exists():
            raise RuntimeError("cache miss: re-scoring must not call the LLM")
        return real(provider, messages)
    llm.complete = complete


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--stem", default="eval")
    a = ap.parse_args(argv)
    cache_only()
    path = RE.RESULTS / f"{a.stem}.json"
    result = json.loads(path.read_text())
    meta = result["meta"]
    provider, why = RE.eval_provider(meta["llm"].split(" / ")[0], meta["llm"].split(" / ")[-1])
    assert provider, why
    changed = {}
    for seed, conds in result["students"].items():
        if "B+" not in conds:
            continue
        sim = Simulator(seed=int(seed))
        sids = [r["sid"] for r in conds["B+"]]
        students = {sid: sim.student(sid) for sid in sids}
        g = T.graph_name(f"rescore_{a.stem}_s{seed}")
        recreate_graph("class_template", g)
        try:
            run_batched(g, Q.LOAD_STUDENTS, [{"id": s, "alias": s} for s in sids])
            judge, graph_text = BL.Judge(g), BL.graph_as_text(g)
            for c in ("A", "B", "B+"):
                for saved in conds[c]:
                    r = RE.run_ab(c, provider, sim, Simulator(seed=int(seed)).student(saved["sid"]), judge, graph_text)
                    if c != "B+":
                        assert r["predicted"] == saved["predicted"] and r["root"] == saved["root"], (seed, c, saved["sid"])
                        continue
                    assert r["opening"] == saved["opening"], (seed, saved["sid"])
                    changed[(seed, saved["sid"])] = {k: (saved[k], r[k]) for k in SCORING if saved[k] != r[k]}
                    saved.update({k: r[k] for k in SCORING})
        finally:
            delete_graph(g)
        before = result["per_seed"][seed]["B+"]
        after = {**RE.score(conds["B+"], students), "n": before["n"]}
        for k in ("latency_p50_ms", "latency_p95_ms", "latency_n"):
            assert after[k] == before[k]
        result["per_seed"][seed]["B+"] = after
        print(f"seed {seed} B+ before: " + json.dumps({k: before[k] for k in after if before.get(k) != after[k]}))
        print(f"seed {seed} B+ after:  " + json.dumps({k: after[k] for k in after if before.get(k) != after[k]}))
    print(f"students whose B+ scoring fields changed: {sum(bool(v) for v in changed.values())}/{len(changed)}")
    result["summary"] = RE.summarise(result["per_seed"], meta["conditions_run"])
    meta["bplus_rescored"] = ("B+ re-scored from the LLM cache on every id it was shown (eval/rescore_bplus.py); the "
                              "first scoring kept only ids on B's retrieved list")
    path.write_text(json.dumps(result, indent=2, default=str) + "\n")
    (RE.RESULTS / f"{a.stem}.md").write_text(RE.markdown(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
