"""The SubTopic REQUIRES graph from eval/real/subtopic_edges.csv: primary (9 edges) or sensitivity (12 edges)."""

import csv
from pathlib import Path

EDGES_CSV = Path(__file__).resolve().parent / "subtopic_edges.csv"
MAX_HOPS = 4  # ROOT_CAUSE walks REQUIRES*1..4


def edges(variant: str = "primary") -> list[tuple[int, int]]:
    """(needs, prerequisite) pairs. primary: the reviewed keeps; sensitivity: the 13 minus edge 4."""
    col, want = {"primary": ("decision", "keep"), "sensitivity": ("in_sensitivity", "yes")}[variant]
    with EDGES_CSV.open() as f:
        return [(int(r["from_subtopic"]), int(r["to_subtopic"])) for r in csv.DictReader(f)
                if r["kind"] == "edge" and r[col] == want]


def is_acyclic(es: list[tuple[int, int]]) -> bool:
    out, nodes = {}, {n for e in es for n in e}
    for a, b in es:
        out.setdefault(a, []).append(b)
    state = {}

    def visit(n) -> bool:
        if state.get(n) == 1:
            return False
        if state.get(n) == 2:
            return True
        state[n] = 1
        ok = all(visit(m) for m in out.get(n, []))
        state[n] = 2
        return ok

    return all(visit(n) for n in nodes)


class Graph:
    """prereqs[x]: {prerequisite: min hops} within MAX_HOPS; dependents[x]: the SubTopics that require x."""

    def __init__(self, variant: str = "primary"):
        self.variant = variant
        self.edges = edges(variant)
        assert is_acyclic(self.edges), f"{variant} graph has a cycle"
        out = {}
        for a, b in self.edges:
            out.setdefault(a, set()).add(b)
        self.prereqs = {}
        for x in {n for e in self.edges for n in e}:
            hops, frontier = {}, {x}
            for d in range(1, MAX_HOPS + 1):
                frontier = {m for n in frontier for m in out.get(n, ())} - set(hops) - {x}
                for m in frontier:
                    hops[m] = d
            self.prereqs[x] = hops
        self.dependents = {x: {y for y, p in self.prereqs.items() if x in p} for x in self.prereqs}
        self.root_candidates = sorted(x for x, d in self.dependents.items() if d)
