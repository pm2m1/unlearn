"""Derive Construct -[:SHARES_MISCONCEPTION {n}]-> Construct in pandas and write both directions."""

from pathlib import Path

import pandas as pd

from unlearn import queries as Q
from unlearn.db import run, run_batched

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
GRAPH = "curriculum"
MIN_SHARED = 2


def shared_pairs(misc: pd.DataFrame) -> pd.DataFrame:
    """One row per ordered (a, b) construct pair sharing >= MIN_SHARED misconceptions."""
    edges = misc[["MisconceptionId", "ConstructId"]].drop_duplicates()
    pairs = edges.merge(edges, on="MisconceptionId", suffixes=("_a", "_b"))
    # Keep a < b so each pair is counted once, then mirror it.
    pairs = pairs[pairs.ConstructId_a < pairs.ConstructId_b]
    counts = pairs.groupby(["ConstructId_a", "ConstructId_b"]).size().reset_index(name="n")
    counts = counts[counts.n >= MIN_SHARED]
    forward = counts.rename(columns={"ConstructId_a": "a", "ConstructId_b": "b"})
    backward = counts.rename(columns={"ConstructId_a": "b", "ConstructId_b": "a"})
    return pd.concat([forward, backward[["a", "b", "n"]]], ignore_index=True)


def main():
    misc = pd.read_csv(RAW / "misconception-map.csv")
    both = shared_pairs(misc)
    rows = [{"a": int(r.a), "b": int(r.b), "n": int(r.n)} for r in both.itertuples()]
    n = run_batched(GRAPH, Q.LOAD_SHARES_MISCONCEPTION, rows)
    print(f"SHARES_MISCONCEPTION: {len(rows) // 2} pairs, {len(rows)} directed edges in {n} batches")

    rows, _ = run(GRAPH, Q.COUNT_SHARES_MISCONCEPTION)
    print("in graph:", rows[0])


if __name__ == "__main__":
    main()
