"""Collapse the 57 curated REQUIRES edges onto Eedi SubTopics: eval/real/subtopic_edges.csv.

    python eval/real/build_subtopic_edges.py

The NeurIPS 2020 data tags questions down to SubTopic (subject_metadata Level 3), not to our constructs, so the
real-data eval runs on a SubTopic graph. A SubTopic REQUIRES another when at least one of its constructs REQUIRES
a construct in the other (data/curated/requires.csv, construct-map.csv from the Eedi Misconceptions Graph). Edges
inside one SubTopic are dropped by the collapse. The one cycle, 226 <-> 227, keeps 227 -> 226 (Simplifying
requires Equivalent) and drops 226 -> 227. Also lists the Fractions SubTopics (Topic 39) with none of our
constructs, which sit outside the graph.
"""

import csv
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / "subtopic_edges.csv"
DROPPED = {(226, 227): "cycle with 227 -> 226; keep Simplifying requires Equivalent, drop Equivalent requires Simplifying"}
# Fractions (Topic 39) SubTopics in subject_metadata.csv with no construct in our graph
UNMAPPED = {225: "Fractions of an Amount", 229: "Converting Mixed Number and Improper Fractions",
            231: "Multiplying Fractions", 232: "Dividing Fractions", 1162: "Fractions-Others",
            1982: "Mixed operation Fractions"}


def main() -> int:
    cm = {int(r["ConstructId"]): r for r in csv.DictReader(open(ROOT / "data/raw/construct-map.csv"))}
    sub = lambda c: int(cm[c]["SubTopicSubjectId"])
    name = {int(r["SubTopicSubjectId"]): r["SubTopicName"] for r in cm.values()}
    edges = defaultdict(list)
    for r in csv.DictReader(open(ROOT / "data/curated/requires.csv")):
        c, p = int(r["construct_id"]), int(r["prereq_id"])
        if sub(c) != sub(p):
            edges[(sub(c), sub(p))].append(f"{c}>{p}({r['confidence']})")
    with OUT.open("w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["kind", "from_subtopic", "from_name", "to_subtopic", "to_name", "n_construct_edges", "construct_edges", "decision", "note"])
        for (a, b), ce in sorted(edges.items()):
            w.writerow(["edge", a, name[a], b, name[b], len(ce), "; ".join(ce),
                        "drop" if (a, b) in DROPPED else "keep", DROPPED.get((a, b), "")])
        for s, n in UNMAPPED.items():
            w.writerow(["unmapped", s, n, "", "", 0, "", "outside graph", "Fractions SubTopic with none of our 40 constructs"])
    print(f"wrote {OUT}: {len(edges)} edges, {len(UNMAPPED)} unmapped SubTopics")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
