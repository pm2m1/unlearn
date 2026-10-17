"""Build `class_template`: the Fractions slice of `curriculum` plus curated REQUIRES, questions, skills and agents.

The template is deleted and rebuilt on every run, which keeps the script idempotent.
"""

import sys

from unlearn import queries as Q
from unlearn.curation import (
    PREREQ_CONSTRUCTS, SUBTOPICS, TOPIC, CurationError, load_questions, load_requires, load_skills,
)
from unlearn.db import create_indexes, delete_graph, run, run_batched

SOURCE = "curriculum"
GRAPH = "class_template"
AGENTS = ["Diagnoser", "Tutor", "Teacher"]
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
EMBED_BATCH = 100  # 384 floats per row makes 500-row batches ~2 MB of query text


def read_slice():
    constructs, _ = run(SOURCE, Q.SLICE_CONSTRUCTS,
                        {"topic": TOPIC, "subtopics": SUBTOPICS, "extra": list(PREREQ_CONSTRUCTS)})
    cids = [r["construct_id"] for r in constructs]
    missing = set(PREREQ_CONSTRUCTS) - set(cids)
    if missing:
        raise CurationError(f"prerequisite constructs not in curriculum: {sorted(missing)}")
    seen_in, _ = run(SOURCE, Q.SLICE_SEEN_IN, {"cids": cids})
    return constructs, seen_in


def validate(constructs, seen_in):
    cids = {r["construct_id"] for r in constructs}
    requires = load_requires()
    bad = [(r["construct_id"], r["prereq_id"]) for r in requires
           if r["construct_id"] not in cids or r["prereq_id"] not in cids]
    if bad:
        raise CurationError(f"REQUIRES edges outside the slice: {bad}")

    seen = {}
    for r in seen_in:
        seen.setdefault(r["cid"], set()).add(r["mid"])
    questions = load_questions(seen_in=seen)  # rejects any distractor without SEEN_IN to its construct
    outside = {q["construct_id"] for q in questions} - cids
    if outside:
        raise CurationError(f"questions on constructs outside the slice: {sorted(outside)}")

    skills = load_skills(questions=questions)
    template_mids = {r["mid"] for r in seen_in}
    unknown = {m for s in skills for m in s["misconceptions"]} - template_mids
    if unknown:
        raise CurationError(f"skills remediate misconceptions not in the template: {sorted(unknown)}")
    return requires, questions, skills


def embed(names: list[str]) -> list[list[float]]:
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(EMBED_MODEL, device="cpu")
    vectors = model.encode(names, batch_size=64, normalize_embeddings=True, show_progress_bar=False)
    return [v.tolist() for v in vectors]


def main():
    constructs, seen_in = read_slice()
    requires, questions, skills = validate(constructs, seen_in)

    delete_graph(GRAPH)
    create_indexes(GRAPH, Q.CLASS_INDEXES)

    run_batched(GRAPH, Q.LOAD_HIERARCHY, [
        {k: r[k] for k in ("subject_id", "subject", "topic_id", "topic", "subtopic_id", "subtopic", "construct_id", "construct")}
        for r in constructs
    ])
    run_batched(GRAPH, Q.LOAD_MISCONCEPTIONS, [
        {"mid": r["mid"], "mname": r["mname"], "cid": r["cid"], "pct": r["pct"]} for r in seen_in
    ])
    run_batched(GRAPH, Q.LOAD_REQUIRES, [
        {"construct_id": r["construct_id"], "prereq_id": r["prereq_id"], "note": r["note"], "confidence": r["confidence"]}
        for r in requires
    ])
    run_batched(GRAPH, Q.LOAD_QUESTIONS, [
        {"id": q["id"], "construct_id": q["construct_id"], "text": q["text"]} for q in questions
    ])
    run_batched(GRAPH, Q.LOAD_OPTIONS, [
        {"qid": q["id"], "key": o["key"], "text": o["text"], "correct": bool(o.get("correct")),
         "mid": o.get("misconception_id")}
        for q in questions for o in q["options"]
    ])
    run_batched(GRAPH, Q.LOAD_SKILLS, [{"name": s["name"], "description": s["description"]} for s in skills])
    run_batched(GRAPH, Q.LOAD_SKILL_STEPS, [
        {"name": s["name"], "order": i, "text": t} for s in skills for i, t in enumerate(s["steps"], 1)
    ])
    run_batched(GRAPH, Q.LOAD_REMEDIATES, [{"name": s["name"], "mid": m} for s in skills for m in s["misconceptions"]])
    run(GRAPH, Q.LOAD_AGENTS, {"names": AGENTS})

    misconceptions = {r["mid"]: r["mname"] for r in seen_in}
    ids = sorted(misconceptions)
    vectors = embed([misconceptions[i] for i in ids])
    run_batched(GRAPH, Q.LOAD_EMBEDDINGS, [{"id": i, "v": v} for i, v in zip(ids, vectors)], batch_size=EMBED_BATCH)

    nodes, _ = run(GRAPH, Q.COUNT_NODES_BY_LABEL)
    edges, _ = run(GRAPH, Q.COUNT_EDGES_BY_TYPE)
    embedded, _ = run(GRAPH, Q.COUNT_EMBEDDED)
    depth, _ = run(GRAPH, Q.REQUIRES_MAX_DEPTH)
    print("nodes:", {r["label"]: r["n"] for r in nodes})
    print("edges:", {r["type"]: r["n"] for r in edges})
    print("embedded misconceptions:", embedded[0]["n"], "| REQUIRES max depth:", depth[0]["depth"])


if __name__ == "__main__":
    try:
        main()
    except CurationError as e:
        sys.exit(f"template build failed: {e}")
