"""Copy class_template to class_<id> with GRAPH.COPY and add simulated students (id and alias only).

Deletes and recreates class_<id> if it already exists.
"""

import argparse

from unlearn import queries as Q
from unlearn.db import create_indexes, list_graphs, recreate_graph, run, run_batched

TEMPLATE = "class_template"

# Synthetic first names. No real students or personal data.
ALIASES = [
    "Asha", "Ben", "Chen", "Dara", "Eli", "Fatima", "Gus", "Hana", "Ivo", "Jaya",
    "Kofi", "Lena", "Mateo", "Nia", "Omar", "Priya", "Quinn", "Rosa", "Sami", "Tara",
    "Uma", "Vik", "Wren", "Xia", "Yusuf", "Zara", "Arlo", "Bea", "Cyrus", "Dina",
]


def index_set(graph_name: str) -> set[tuple]:
    rows, _ = run(graph_name, Q.LIST_INDEXES)
    return {(r["label"], p, t) for r in rows for p, types in r["types"].items() for t in types}


def new_class(class_id: str, students: int) -> dict:
    if TEMPLATE not in list_graphs():
        raise SystemExit(f"{TEMPLATE} missing: run scripts/04_build_template.py first")
    if students > len(ALIASES):
        raise SystemExit(f"at most {len(ALIASES)} students")
    name = f"class_{class_id}"
    replaced = recreate_graph(TEMPLATE, name)

    # GRAPH.COPY should carry indexes; check, and recreate any that did not survive.
    expected, copied = index_set(TEMPLATE), index_set(name)
    lost = expected - copied
    if lost:
        create_indexes(name, Q.CLASS_INDEXES)

    rows = [{"id": f"s{i:02d}", "alias": ALIASES[i - 1]} for i in range(1, students + 1)]
    run_batched(name, Q.LOAD_STUDENTS, rows)
    return {"graph": name, "replaced": replaced, "indexes_copied": len(copied & expected),
            "indexes_expected": len(expected), "indexes_recreated": sorted(lost), "students": len(rows)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", required=True)
    ap.add_argument("--students", type=int, default=30)
    args = ap.parse_args()
    report = new_class(args.id, args.students)
    print(report)
    nodes, _ = run(report["graph"], Q.COUNT_NODES_BY_LABEL)
    print("nodes:", {r["label"]: r["n"] for r in nodes})


if __name__ == "__main__":
    main()
