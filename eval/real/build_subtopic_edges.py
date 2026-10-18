"""Collapse the 57 curated REQUIRES edges onto Eedi SubTopics: eval/real/subtopic_edges.csv.

    python eval/real/build_subtopic_edges.py

The NeurIPS 2020 data tags questions down to SubTopic (subject_metadata Level 3), not to our constructs, so the
real-data eval runs on a SubTopic graph. A SubTopic REQUIRES another when at least one of its constructs REQUIRES
a construct in the other (data/curated/requires.csv, construct-map.csv from the Eedi Misconceptions Graph). Edges
inside one SubTopic are dropped by the collapse. Parth's review (eval/real/EDGE_REVIEW.md) keeps an edge only
if the target SubTopic is a genuine prerequisite and drops edges that exist only because of where Eedi files a
construct: 9 of the 13 are kept (the primary graph). The sensitivity graph is the 13 minus edge 4 (226 -> 227),
12 edges. Also lists the Fractions SubTopics (Topic 39) with none of our constructs, which sit outside the graph.
"""

import csv
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / "subtopic_edges.csv"
# Parth's review, 2026-10-18 (EDGE_REVIEW.md). Edge 4 is the only one also left out of the sensitivity graph.
DROPPED = {
    (226, 227): "only from 3342 Read fractions, which Eedi files under 227; also makes the 226 <-> 227 cycle",
    (228, 204): "one construct edge (3839 > 3193) collapsed onto the broadest SubTopic; 228 already reaches 204 via 226 and 220",
    (228, 227): "only from 3342 Read fractions, not Simplifying",
    (230, 227): "only from 3342 Read fractions, not Simplifying",
}
NOT_IN_SENSITIVITY = {(226, 227)}
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
        w.writerow(["kind", "from_subtopic", "from_name", "to_subtopic", "to_name", "n_construct_edges", "construct_edges",
                    "decision", "in_sensitivity", "note"])
        for (a, b), ce in sorted(edges.items()):
            w.writerow(["edge", a, name[a], b, name[b], len(ce), "; ".join(ce),
                        "drop" if (a, b) in DROPPED else "keep", "no" if (a, b) in NOT_IN_SENSITIVITY else "yes",
                        DROPPED.get((a, b), "")])
        for s, n in UNMAPPED.items():
            w.writerow(["unmapped", s, n, "", "", 0, "", "outside graph", "", "Fractions SubTopic with none of our 40 constructs"])
    kept = len(edges) - len(DROPPED)
    print(f"wrote {OUT}: {len(edges)} edges ({kept} kept, {len(edges) - len(NOT_IN_SENSITIVITY)} in the sensitivity graph), "
          f"{len(UNMAPPED)} unmapped SubTopics")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
