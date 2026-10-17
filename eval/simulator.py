"""Rule-based, seeded student simulator (SPEC "Evaluation").

Each simulated student has one planted broken prerequisite (the true root cause) and 1-3 planted
misconceptions, drawn from the distractors on that prerequisite's questions so they can be observed.
The student "knows" every construct except the broken one and the constructs that depend on it.

answer(question) picks an option key:
  1. With probability 0.1, guess uniformly among all options.
  2. If an option indicates a planted misconception, pick it with probability 0.85.
  3. On a known construct, answer correctly with probability 0.9.
  4. Otherwise pick a random wrong option.

The simulator reads the curated files, not the graph: it is the ground truth the agents are scored
against, so it must not share their queries. It does share the option-to-misconception map, which
favours Unlearn (SPEC says to state this in the README).
"""

import json
import random
from dataclasses import dataclass, field

import networkx as nx

from unlearn.curation import CURATED, load_requires, requires_graph

GUESS_RATE = 0.1
PICK_PLANTED = 0.85
KNOWN_CORRECT = 0.9
MAX_HOPS = 4  # root_cause walks REQUIRES*1..4


def load_bank() -> dict[str, dict]:
    with open(CURATED / "questions.json") as f:
        return {q["id"]: q for q in json.load(f)}


@dataclass
class SimStudent:
    id: str
    root_cause: int                 # the planted broken prerequisite
    misconceptions: list[int]       # planted misconception ids
    target: int                     # a construct that depends on root_cause within MAX_HOPS
    unknown: set[int]               # root_cause plus every construct that depends on it
    bank: dict[str, dict] = field(repr=False)
    rng: random.Random = field(repr=False)

    def knows(self, construct_id: int) -> bool:
        return construct_id not in self.unknown

    def answer(self, question: dict | str) -> str:
        """Return the option key this student picks. Accepts a question id or any dict with an "id"."""
        q = self.bank[question if isinstance(question, str) else question["id"]]
        options = q["options"]
        wrong = [o for o in options if not o.get("correct")]
        if self.rng.random() < GUESS_RATE:
            return self.rng.choice(options)["key"]
        planted = [o for o in wrong if o.get("misconception_id") in self.misconceptions]
        if planted and self.rng.random() < PICK_PLANTED:
            return self.rng.choice(planted)["key"]
        if self.knows(q["construct_id"]) and self.rng.random() < KNOWN_CORRECT:
            return next(o for o in options if o.get("correct"))["key"]
        return self.rng.choice(wrong)["key"]


class Simulator:
    """Builds reproducible students: the same seed and ids always give the same students and answers."""

    def __init__(self, seed: int = 0):
        self.seed = seed
        self.bank = load_bank()
        self.g = requires_graph(load_requires())  # edge a -> b means a REQUIRES b
        by_construct: dict[int, set[int]] = {}
        for q in self.bank.values():
            mids = {o["misconception_id"] for o in q["options"] if o.get("misconception_id") is not None}
            by_construct.setdefault(q["construct_id"], set()).update(mids)
        self.distractor_mids = by_construct
        # A construct can be a planted root cause if something depends on it and its questions have distractors.
        self.candidates = sorted(c for c in self.g.nodes if self.g.in_degree(c) > 0 and by_construct.get(c))

    def dependants(self, construct_id: int, max_hops: int | None = None) -> dict[int, int]:
        """Constructs that REQUIRE construct_id (directly or not), with their shortest hop count."""
        hops = nx.single_source_shortest_path_length(self.g.reverse(copy=False), construct_id, cutoff=max_hops)
        hops.pop(construct_id, None)
        return hops

    def student(self, student_id: str, root_cause: int | None = None, target: int | None = None) -> SimStudent:
        rng = random.Random(f"{self.seed}:{student_id}")
        root = root_cause if root_cause is not None else rng.choice(self.candidates)
        reach = self.dependants(root, MAX_HOPS)
        if target is None:
            # Prefer a target 2+ hops above the root cause, so the diagnosis has to trace back.
            deep = sorted(c for c, h in reach.items() if h >= 2)
            target = rng.choice(deep or sorted(reach))
        elif target not in reach:
            raise ValueError(f"target {target} does not depend on {root} within {MAX_HOPS} hops")
        pool = sorted(self.distractor_mids[root])
        planted = rng.sample(pool, k=min(len(pool), rng.randint(1, 3)))
        unknown = {root} | set(self.dependants(root))
        return SimStudent(student_id, root, planted, target, unknown, self.bank, rng)

    def cohort(self, student_ids: list[str]) -> list[SimStudent]:
        return [self.student(sid) for sid in student_ids]
