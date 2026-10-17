"""Load Subject → Topic → SubTopic → Construct and Misconception -[:SEEN_IN]-> Construct into `curriculum`."""

from pathlib import Path

import pandas as pd
from unlearn import queries as Q
from unlearn.db import create_indexes, run, run_batched

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
GRAPH = "curriculum"


def main():
    constructs = pd.read_csv(RAW / "construct-map.csv")
    misc = pd.read_csv(RAW / "misconception-map.csv")

    create_indexes(GRAPH, Q.CURRICULUM_INDEXES)

    hierarchy = [
        {
            "subject_id": int(r.SubjectSubjectId), "subject": r.SubjectName,
            "topic_id": int(r.TopicSubjectId), "topic": r.TopicName,
            "subtopic_id": int(r.SubTopicSubjectId), "subtopic": r.SubTopicName,
            "construct_id": int(r.ConstructId), "construct": r.ConstructName,
        }
        for r in constructs.itertuples()
    ]
    n = run_batched(GRAPH, Q.LOAD_HIERARCHY, hierarchy)
    print(f"hierarchy: {len(hierarchy)} rows in {n} batches")

    seen_in = [
        {
            "mid": int(r.MisconceptionId), "mname": r.MisconceptionName,
            "cid": int(r.ConstructId), "pct": float(r.PercentageMisconceptionExistsInThisConstruct),
        }
        for r in misc.itertuples()
    ]
    n = run_batched(GRAPH, Q.LOAD_MISCONCEPTIONS, seen_in)
    print(f"misconceptions: {len(seen_in)} rows in {n} batches")

    rows, _ = run(GRAPH, Q.COUNT_NODES_BY_LABEL)
    print("nodes:", {r["label"]: r["n"] for r in rows})
    rows, _ = run(GRAPH, Q.COUNT_SEEN_IN)
    print("SEEN_IN edges:", rows[0]["n"])


if __name__ == "__main__":
    main()
