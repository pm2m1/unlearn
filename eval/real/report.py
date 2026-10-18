"""Write the tables in eval/real/RESULTS.md from eval/results/real/*.json (between the GENERATED markers).

    python -m eval.real.report [--dev]     # --dev prints the dev-split tables instead of writing RESULTS.md
"""

import argparse
import json

from eval.real.data import CACHE, ROOT
from eval.real.run import OUT

RESULTS = ROOT / "eval/real/RESULTS.md"
START, END = "<!-- GENERATED: tables (python -m eval.real.report) -->", "<!-- END GENERATED -->"
NAMES = {"M0": "M0 question difficulty", "M0b": "M0b running accuracy", "M1": "M1 BKT",
         "M2-nograph": "M2-nograph (ablation)", "M2": "M2 graph-structure prior, correctness-only",
         "M3": "M3 BKT + graph prior", "M2 (12 edges)": "M2, 12-edge graph", "M3 (12 edges)": "M3, 12-edge graph"}


def iv(x, ci):
    return f"{x:.4f} [{ci[0]:.4f}, {ci[1]:.4f}]"


def task_a(a: dict) -> list[str]:
    out = []
    for s in ("all", "first 2 quizzes", "later quizzes"):
        d = a[s]
        out += [f"**{s.capitalize()}** ({d['n_answers']:,} answers, {d['n_students']:,} students)", "",
                "| Model | AUC | Log-loss | Accuracy |", "| --- | --- | --- | --- |"]
        for m, v in d["models"].items():
            out.append(f"| {NAMES.get(m, m)} | {iv(v['auc'], v['auc_ci'])} | {iv(v['logloss'], v['logloss_ci'])} | "
                       f"{iv(v['accuracy'], v['accuracy_ci'])} |")
        out += ["", "| Comparison (AUC) | Difference [95% CI] | Verdict |", "| --- | --- | --- |"]
        for k, v in d["differences"].items():
            out.append(f"| {k} | {v['auc_diff']:+.4f} [{v['ci'][0]:+.4f}, {v['ci'][1]:+.4f}] | {v['verdict']} |")
        out.append("")
    out += ["**A3: does the graph help more at cold start?**", "", "| Contrast | Difference [95% CI] |", "| --- | --- |"]
    for k, v in a["contrasts"].items():
        out.append(f"| {k} | {v['auc_diff']:+.4f} [{v['ci'][0]:+.4f}, {v['ci'][1]:+.4f}] |")
    m3 = a["m3"]
    out += ["", f"M3's β chosen on train: {m3['primary']['beta']} (9 edges), {m3['sensitivity']['beta']} (12 edges). "
            f"M2's coefficients (logit(M0), evidence, mastered, prerequisite suspicion): {a['m2']['primary']['coef']}.", ""]
    return out


def task_b(b: dict) -> list[str]:
    out = ["| Cell | Diagnosed / test students | Roots | Method | Evaluable | Lift [95% CI] | Difficulty-adjusted lift [95% CI] |",
           "| --- | --- | --- | --- | --- | --- | --- |"]
    for cell, v in b.items():
        if cell == "meta":
            continue
        roots = ", ".join(f"{k}: {n}" for k, n in v["roots"].items())
        diagnosed = f"{v['n_diagnosed']:,} / {v['n_test_students']:,}"
        fmt = lambda x, c: "n/a" if x is None else f"{x:+.4f} [{c[0]:+.4f}, {c[1]:+.4f}]"
        for i, m in enumerate(("unlearn", "random", "bkt", "unlearn_confident", "unlearn - random", "unlearn - bkt")):
            r = v[m]
            n = r.get("n_evaluable", r.get("n_paired"))
            flag = " (underpowered)" if r.get("underpowered") else ""
            first = (cell, diagnosed, roots) if i == 0 else ("", "", "")
            out.append(f"| {first[0]} | {first[1]} | {first[2]} | {m}{flag} | {n:,} | {fmt(r['lift'], r['lift_ci'])} | "
                       f"{fmt(r['adjusted_lift'], r['adjusted_lift_ci'])} |")
    return out


def tables(a: dict, b: dict) -> str:
    meta = a["meta"]
    head = [f"Run {meta['run_at']} on {meta['split']}, commit `{meta['commit'][:7]}`"
            f"{' (with uncommitted changes)' if meta['uncommitted_changes'] else ''}.", ""]
    for label, s in (("Primary", "all"), ("Key secondary (cold start)", "first 2 quizzes")):
        d = a[s]["differences"]["M2 - M2-nograph"]
        head.append(f"- **{label}:** M2 − M2-nograph AUC on {s} = {d['auc_diff']:+.4f} "
                    f"[95% CI {d['ci'][0]:+.4f}, {d['ci'][1]:+.4f}]: **{d['verdict']}**.")
    head += ["", "### Task A: next-answer prediction", ""]
    return "\n".join(head + task_a(a) + ["### Task B: is the diagnosed root real?", ""] + task_b(b))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dev", action="store_true")
    args = ap.parse_args()
    src = CACHE / "dev" if args.dev else OUT
    a, b = (json.loads((src / f).read_text()) for f in ("task_a.json", "task_b.json"))
    body = tables(a, b)
    if args.dev:
        print(body)
        return 0
    text = RESULTS.read_text() if RESULTS.exists() else f"# Real-data results\n\n{START}\n{END}\n"
    pre, rest = text.split(START, 1)
    RESULTS.write_text(pre + START + "\n" + body + "\n" + END + rest.split(END, 1)[1])
    print(f"wrote tables into {RESULTS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
