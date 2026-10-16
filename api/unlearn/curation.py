"""Validation for the hand-curated files in data/curated/. Every loader and test goes through here."""

import csv
import json
import re
from fractions import Fraction
from math import gcd, lcm
from pathlib import Path

import networkx as nx

ROOT = Path(__file__).resolve().parents[2]
CURATED = ROOT / "data" / "curated"

# The class topic slice: four Fractions subtopics plus hand-picked prerequisites.
TOPIC = "Fractions"
SUBTOPICS = [
    "Equivalent Fractions",
    "Adding and Subtracting Fractions",
    "Simplifying Fractions",
    "Ordering Fractions",
]
PREREQ_CONSTRUCTS = {
    3378: "Know times tables up to 12 x 12",
    342: "Identify multiples of a number",
    345: "Identify the Lowest Common Multiple of two numbers",
    331: "Identify factors of a number",
    338: "Identify the Highest Common Factor of two numbers",
    164: "Carry out mental divisions when the answer is an integer",
    3193: "Express a division as a fraction",
}


class CurationError(ValueError):
    pass


# --- REQUIRES -----------------------------------------------------------------

def load_requires(path: Path = CURATED / "requires.csv") -> list[dict]:
    with open(path, newline="") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["construct_id"] = int(r["construct_id"])
        r["prereq_id"] = int(r["prereq_id"])
        if r["confidence"] not in {"high", "medium", "low"}:
            raise CurationError(f"bad confidence {r['confidence']!r} on {r['construct_id']}->{r['prereq_id']}")
    check_dag(rows)
    return rows


def requires_graph(rows: list[dict]) -> nx.DiGraph:
    g = nx.DiGraph()
    g.add_edges_from((r["construct_id"], r["prereq_id"]) for r in rows)
    return g


def check_dag(rows: list[dict]) -> None:
    g = requires_graph(rows)
    if not nx.is_directed_acyclic_graph(g):
        raise CurationError(f"REQUIRES has a cycle: {nx.find_cycle(g)}")
    if any(r["construct_id"] == r["prereq_id"] for r in rows):
        raise CurationError("REQUIRES has a self-loop")
