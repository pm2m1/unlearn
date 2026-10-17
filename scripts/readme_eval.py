"""The README's eval tables, generated from eval/results/*.json so the numbers can't drift from the data.

    python scripts/readme_eval.py            # print the block
    python scripts/readme_eval.py --write    # replace the block between the markers in README.md

Reads eval.json (A, B, B+, C), random_baseline.json (random guess from the same candidate lists) and
crosscheck.json (the tiny Gemini Flash cross-check, shown only as a footnote).
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "eval" / "results"
START, END = "<!-- eval:start -->", "<!-- eval:end -->"
LABELS = {"A": "A. No memory", "B": "B. Vector RAG", "B+": "B+. LLM + graph as text", "C": "C. Unlearn"}
ROWS = [("Top-1 misconception", "top1_misconception", "%"), ("Top-3 misconception", "top3_misconception", "%"),
        ("Root-cause accuracy", "root_cause_accuracy", "%"), ("Questions to diagnosis", "questions_to_diagnosis", "q"),
        ("Session-2 recall", "session2_recall", "%"), ("p50 latency per diagnosis", "latency_p50_ms", "ms"),
        ("p95 latency per diagnosis", "latency_p95_ms", "ms")]


def fmt(x, unit):
    if x is None:
        return "–"
    if unit == "%":
        return f"{100 * x:.0f}%"
    if unit == "ms":
        return f"{x / 1000:.1f} s" if x >= 1000 else f"{x:.0f} ms"
    return f"{x:.1f}"


def cell(summary, c, m, unit, multi):
    v = (summary.get(c) or {}).get(m)
    if v is None:
        return "–"
    if not multi or v["min"] == v["max"]:
        return fmt(v["mean"], unit)
    lo, hi = fmt(v["min"], unit), fmt(v["max"], unit)
    return f"{fmt(v['mean'], unit)} ({lo}–{hi})"


def random_column(rb, seeds_of):
    """Expected score of a uniform pick from what each condition is scored on, over the seeds it ran."""
    def mean(key, c):
        xs = [rb["per_seed"][str(s)][c][key] for s in seeds_of[c] if str(s) in rb["per_seed"]]
        return sum(xs) / len(xs) if xs else None
    return mean


def rfmt(x):
    return "–" if x is None else f"{100 * x:.1f}%" if x < 0.1 else f"{100 * x:.0f}%"


def seed_table(ev, conds, seeds_of) -> list[str]:
    """A condition that ran on fewer seeds (B+) is compared on those seeds only: same students for every condition."""
    short = sorted({tuple(seeds_of[c]) for c in conds if len(seeds_of[c]) < len(ev["meta"]["seeds"])})
    out = []
    for seeds in short:
        partial = [c for c in conds if tuple(seeds_of[c]) == seeds]
        label = ", ".join(map(str, seeds))
        ps = ev["per_seed"]
        n = {c: sum(ps[str(s)][c]["n"] for s in seeds) for c in conds}
        out += ["", f"**{' and '.join(partial)} ran on seed {label} only**, so {'its' if len(partial) == 1 else 'their'} "
                f"column above is not comparable with the other columns' three-seed means. On seed {label}, the same "
                f"{n[partial[0]]} students for every condition:", "",
                "| Seed " + label + " | " + " | ".join(f"{LABELS[c]} (n={n[c]})" for c in conds) + " |",
                "|" + " --- |" * (len(conds) + 1)]
        for row_label, m, unit in ROWS[:6]:
            vals = []
            for c in conds:
                xs = [ps[str(s)][c][m] for s in seeds if ps[str(s)][c][m] is not None]
                vals.append(fmt(sum(xs) / len(xs), unit) if xs else "–")
            out.append(f"| {row_label} | " + " | ".join(vals) + " |")
    return out


def block() -> str:
    ev = json.loads((RESULTS / "eval.json").read_text())
    rb = json.loads((RESULTS / "random_baseline.json").read_text())
    meta, summary = ev["meta"], ev["summary"]
    conds = [c for c in LABELS if c in summary]
    seeds_of = meta.get("seeds_per_condition") or {c: meta["seeds"] for c in conds}
    n = meta["n_per_condition"]
    head = "| Metric | " + " | ".join(f"{LABELS[c]} (n={n[c]}, seed{'s' * (len(seeds_of[c]) > 1)} {', '.join(map(str, seeds_of[c]))})" for c in conds) \
           + " | Random guess (A / B / B+) |"
    lines = [head, "|" + " --- |" * (len(conds) + 2)]
    rnd = random_column(rb, seeds_of)
    for label, m, unit in ROWS:
        cells = [cell(summary, c, m, unit, len(seeds_of[c]) > 1) for c in conds]
        if m in ("top1_misconception", "top3_misconception", "root_cause_accuracy"):
            r = " / ".join(rfmt(rnd(m, c)) for c in ("A", "B", "B+"))
        else:
            r = "–"
        lines.append(f"| {label} | " + " | ".join(cells) + f" | {r} |")
    sizes = {k: sum(rb["per_seed"][str(s)]["candidate_list_sizes"][k] for s in meta["seeds"]) / len(meta["seeds"])
             for k in ("prerequisites", "A_misconceptions", "B_misconceptions", "Bplus_misconceptions", "Bplus_constructs")}
    on_list = {k: sum(rb["per_seed"][str(s)]["planted_misconception_on_list"][k] for s in meta["seeds"]) / len(meta["seeds"])
               for k in ("A", "B", "B+")}
    lines += ["", f"Mean (min–max across seeds) where a condition ran on more than one seed. Model for A, B and B+: "
              f"`{meta['llm'].split(' / ')[-1]}` (local, Ollama, thinking off), one model, no fallback. C: template wording; "
              "its metrics come from the graph."]
    lines += seed_table(ev, conds, seeds_of)
    lines += ["",
              f"Candidate lists, averaged over the same students: {sizes['prerequisites']:.1f} root-cause candidates "
              f"(the target's prerequisites), {sizes['A_misconceptions']:.1f} misconception candidates for A and "
              f"{sizes['B_misconceptions']:.0f} for B. A planted misconception is on A's list for "
              f"{100 * on_list['A']:.0f}% of students and on B's for {100 * on_list['B']:.0f}%, which caps A's and B's "
              "misconception scores whatever the model does. **B+ is not capped:** it is scored on every ID it was "
              f"shown, B's lists plus its graph text ({sizes['Bplus_misconceptions']:.0f} misconceptions and "
              f"{sizes['Bplus_constructs']:.0f} constructs), and every planted misconception "
              f"({100 * on_list['B+']:.0f}%) is in it. The random-guess column picks uniformly from those same sets."]
    cc_path = RESULTS / "crosscheck.json"
    if cc_path.exists():
        cc = json.loads(cc_path.read_text())
        cn = cc["meta"]["n_per_condition"]
        ccs = [c for c in ("A", "B") if c in cc["summary"]]
        lines += ["", f"<sup>Footnote: cross-check with `{cc['meta']['llm'].split(' / ')[-1]}` on seed 0 "
                  f"({', '.join(f'{c}: n={cn[c]}' for c in ccs)}), first scoring method, **on the pre-review data** (before "
                  "REVIEW.md's 2 edge deletions and 9 option removals). **Indicative only, n too small to "
                  "conclude.** The Gemini free tier allows 20 requests per model per day.</sup>", "",
                  "| Cross-check metric | " + " | ".join(f"{LABELS[c]} (n={cn[c]})" for c in ccs) + " |",
                  "|" + " --- |" * (len(ccs) + 1)]
        for label, m, unit in ROWS[:3]:
            lines.append(f"| {label} | " + " | ".join(cell(cc["summary"], c, m, unit, False) for c in ccs) + " |")
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    text = block()
    if argv and "--write" in argv:
        readme = ROOT / "README.md"
        s = readme.read_text()
        head, rest = s.split(START, 1)
        _, tail = rest.split(END, 1)
        readme.write_text(f"{head}{START}\n{text}{END}{tail}")
        print("README.md eval tables updated")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
