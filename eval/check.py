"""make eval-check: re-run every simulated eval and fail if any committed number differs.

    python -m eval.check              # everything (A, B and B+ replayed from the committed LLM reply cache)
    python -m eval.check --skip-llm   # C, noise, random baseline and design checks only

1. Graph: the eval reads class_template from the local FalkorDB, not from the commit. Its fingerprint must equal
   the one recorded in eval.json, or nothing below means anything (rebuild with `make seed`).
2. C (Unlearn): re-run on eval.json's seeds. Every student's predictions, root, questions asked, recall verdict
   and opening text, and every summary and per-seed metric, must match.
3. A, B, B+: replayed with UNLEARN_LLM_CACHE_ONLY=1 from .cache/llm, which is committed (model replies only;
   a fresh model call at temperature 0.3 wouldn't reproduce anyway). B+ runs on eval.json's B+ seeds.
   A reply missing from the cache fails the check.
4. Bootstrap: every metric's 95% interval, recomputed from the re-run students, must match eval.json's.
5. noise.json, random_baseline.json and design_checks.json: re-run into scratch files and compared value by
   value.
Latency is never compared: it is wall time. Nothing in eval/results is written.
"""

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

from eval import bootstrap as BS
from eval import design_checks as DC
from eval import noise as NZ
from eval import random_baseline as RB
from eval import run_eval as RE
from eval.provenance import graph_fingerprint

SKIP = {"provenance", "run_at", "latency_ms", "latency_p50_ms", "latency_p95_ms", "latency_n", "latency_pooled",
        "clean_baselines_from"}
STUDENT_KEYS = ("sid", "predicted", "root", "asked", "recalled", "opening", "json_ok", "misconceptions_unmapped",
                "root_unmapped", "planted")


def diff(a, b, path="", out=None, skip=SKIP):
    """Every path where a and b differ (keys in skip are ignored at any depth)."""
    out = [] if out is None else out
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b), key=str):
            if k in skip:
                continue
            if k not in a or k not in b:
                out.append(f"{path}/{k}: only in {'committed' if k in a else 're-run'}")
            else:
                diff(a[k], b[k], f"{path}/{k}", out, skip)
    elif isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        for i, (x, y) in enumerate(zip(a, b)):
            diff(x, y, f"{path}[{i}]", out, skip)
    elif a != b:
        out.append(f"{path}: committed {json.dumps(a)[:120]} -> re-run {json.dumps(b)[:120]}")
    return out


def check_eval(committed: dict, conds: list[str]) -> list[str]:
    meta = committed["meta"]
    seeds = ",".join(str(s) for s in meta["seeds"])
    stem = "check_eval"
    args = ["--conditions", ",".join(conds), "--seeds", seeds, "--out", stem, "--no-calibrate"]
    if any(c in ("A", "B", "B+") for c in conds):
        args += ["--model", meta["llm"].split(" / ", 1)[1]]
    if "B+" in conds:
        args += ["--bplus-seeds", ",".join(str(s) for s in meta["seeds_per_condition"]["B+"])]
    RE.main(args)
    try:
        rerun = json.loads((RE.RESULTS / f"{stem}.json").read_text())
    finally:
        for ext in ("json", "md"):
            (RE.RESULTS / f"{stem}.{ext}").unlink(missing_ok=True)
    problems = []
    for c in conds:
        problems += diff(committed["summary"][c], rerun["summary"][c], f"summary/{c}")
        for s in meta["seeds_per_condition"][c]:
            s = str(s)
            problems += diff(committed["per_seed"][s][c], rerun["per_seed"][s][c], f"per_seed/{s}/{c}")
            pick = lambda rows: [{k: r.get(k) for k in STUDENT_KEYS} for r in rows]  # noqa: E731
            problems += diff(pick(committed["students"][s][c]), pick(rerun["students"][s][c]), f"students/{s}/{c}")
            # Bootstrap intervals, recomputed from the re-run students.
            got = BS.metric_intervals(BS.scores_for(rerun, c, [s]))
            problems += diff(committed["bootstrap"]["per_seed"][s][c], got, f"bootstrap/per_seed/{s}/{c}")
        seeds_c = [str(s) for s in meta["seeds_per_condition"][c]]
        got = BS.metric_intervals(BS.scores_for(rerun, c, seeds_c))
        problems += diff(committed["bootstrap"]["overall"][c], got, f"bootstrap/overall/{c}")
    return problems


def check_file(name: str, run, committed_path: Path) -> list[str]:
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / name
        run(["--out", str(out)])
        return diff(json.loads(committed_path.read_text()), json.loads(out.read_text()), name)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--skip-llm", action="store_true", help="don't replay A, B and B+")
    a = ap.parse_args(argv)
    committed = json.loads((RE.RESULTS / "eval.json").read_text())
    recorded = (committed["meta"].get("provenance") or {}).get("graph", {}).get("sha256")
    now = graph_fingerprint()["sha256"]
    if recorded != now:
        print(f"FAIL: class_template here ({now[:12]}) is not the graph eval.json was run on "
              f"({(recorded or 'none recorded')[:12]}). Rebuild it (make seed) or re-run the eval.")
        return 1
    report = {}
    report["C"] = check_eval(committed, ["C"])
    if a.skip_llm:
        print("A, B and B+ skipped (--skip-llm): their numbers were NOT checked.")
    else:
        os.environ["UNLEARN_LLM_CACHE_ONLY"] = "1"
        try:
            report["A, B, B+"] = check_eval(committed, ["A", "B", "B+"])
        except Exception as e:  # llm.CacheMiss, or no cache at all
            report["A, B, B+"] = [f"could not replay from the LLM cache: {type(e).__name__}: {e}"]
        finally:
            os.environ.pop("UNLEARN_LLM_CACHE_ONLY", None)
    report["noise.json"] = check_file("noise.json", NZ.main, RE.RESULTS / "noise.json")
    report["random_baseline.json"] = check_file("random_baseline.json", RB.main, RE.RESULTS / "random_baseline.json")
    report["design_checks.json"] = check_file("design_checks.json", DC.main, RE.RESULTS / "design_checks.json")

    print(f"\ngraph {now[:12]} matches eval.json")
    failed = False
    for part, problems in report.items():
        print(f"{part}: {'OK' if not problems else f'{len(problems)} difference(s)'}")
        for p in problems[:20]:
            print("   ", p)
        failed |= bool(problems)
    print("\nFAIL" if failed else "\nPASS: every committed number reproduced (latency is not compared)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
