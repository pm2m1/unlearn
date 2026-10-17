"""Fixture class graphs built with the production load queries and synthetic data."""

import pytest

from unlearn import queries as Q
from unlearn.db import create_indexes, delete_graph, run, run_batched

# Five constructs. REQUIRES: 1 -> 2 -> 3 -> 4 and 1 -> 5.
CONSTRUCTS = {
    1: "Add fractions with unlike denominators",
    2: "Identify equivalent fractions",
    3: "Find the lowest common multiple",
    4: "Identify multiples of a number",
    5: "Add fractions with the same denominator",
}
REQUIRES = [(1, 2), (2, 3), (3, 4), (1, 5)]
MISCONCEPTIONS = {
    101: "Adds the numerators and adds the denominators when adding fractions",
    102: "Multiplies the denominators but adds the numerators",
    201: "Thinks adding the same number to numerator and denominator makes an equivalent fraction",
    202: "Swaps numerator and denominator to make an equivalent fraction",
    301: "Multiplies the two numbers together to find the lowest common multiple",
    302: "Gives the highest common factor instead of the lowest common multiple",
    401: "Believes a number is a multiple of its last digit",
    402: "Thinks the first multiple of a number is double the number",
    501: "Adds the denominators when adding fractions with the same denominator",
    502: "Multiplies the numerators when adding fractions with the same denominator",
}
STUDENTS = [("sa", "Asha"), ("sb", "Ben"), ("sc", "Chen"), ("sd", "Dara")]


def build_class(name: str, embed_misconceptions: bool = False) -> None:
    """Two questions per construct: option A is correct, B indicates misconception c01, C indicates c02."""
    delete_graph(name)
    create_indexes(name, Q.CLASS_INDEXES)
    run_batched(name, Q.LOAD_HIERARCHY, [
        {"subject_id": 900, "subject": "Number", "topic_id": 901, "topic": "Fractions",
         "subtopic_id": 902, "subtopic": "Fixture", "construct_id": c, "construct": n}
        for c, n in CONSTRUCTS.items()
    ])
    run_batched(name, Q.LOAD_MISCONCEPTIONS, [
        {"mid": m, "mname": n, "cid": m // 100, "pct": 100.0} for m, n in MISCONCEPTIONS.items()
    ])
    run_batched(name, Q.LOAD_REQUIRES, [
        {"construct_id": a, "prereq_id": b, "note": "fixture", "confidence": "high"} for a, b in REQUIRES
    ])
    questions = [{"id": f"q-{c}-{i}", "construct_id": c, "text": f"Fixture question {i} on {c}"}
                 for c in CONSTRUCTS for i in (1, 2)]
    run_batched(name, Q.LOAD_QUESTIONS, questions)
    run_batched(name, Q.LOAD_OPTIONS, [
        row for q in questions for row in (
            {"qid": q["id"], "key": "A", "text": "right", "correct": True, "mid": None},
            {"qid": q["id"], "key": "B", "text": "wrong 1", "correct": False, "mid": q["construct_id"] * 100 + 1},
            {"qid": q["id"], "key": "C", "text": "wrong 2", "correct": False, "mid": q["construct_id"] * 100 + 2},
        )
    ])
    run_batched(name, Q.LOAD_SKILLS, [{"name": "Fraction wall", "description": "fixture"}])
    run_batched(name, Q.LOAD_REMEDIATES, [{"name": "Fraction wall", "mid": m} for m in MISCONCEPTIONS])
    run(name, Q.LOAD_AGENTS, {"names": ["Diagnoser", "Tutor", "Teacher"]})
    run_batched(name, Q.LOAD_STUDENTS, [{"id": s, "alias": a} for s, a in STUDENTS])
    if embed_misconceptions:
        from unlearn.embed import embed

        ids = sorted(MISCONCEPTIONS)
        vectors = embed([MISCONCEPTIONS[i] for i in ids])
        run_batched(name, Q.LOAD_EMBEDDINGS, [{"id": i, "v": v} for i, v in zip(ids, vectors)])


@pytest.fixture(scope="module")
def fixture_class():
    """Yields the class_id of a fresh fixture class graph and deletes it afterwards."""
    class_id = "pytest_tools"
    build_class(f"class_{class_id}", embed_misconceptions=True)
    yield class_id
    delete_graph(f"class_{class_id}")
