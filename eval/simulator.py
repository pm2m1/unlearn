"""Rule-based, seeded student simulator (SPEC "Evaluation").

Each simulated student has one planted broken prerequisite (the true root cause) and 1-3 planted
misconceptions, drawn from the distractors on that prerequisite's questions so they can be observed.
The student "knows" every construct except the broken one and the constructs that depend on it.

answer(question) picks an option key:
  1. With probability 0.1, guess uniformly among all options.
  2. If an option indicates a planted misconception, pick it with probability 0.85.
  3. On a known construct, answer correctly with probability 0.9.
  4. Otherwise pick a random wrong option.

noise=p (default 0, the eval's setting) adds answers the option-to-misconception map doesn't explain: with
probability p the answer is a uniformly random wrong option that indicates none of the student's planted
misconceptions, and a correct answer slips to a random wrong option with probability p/2. At p = 0 no extra
random numbers are drawn, so every existing run reproduces exactly.

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
    guess_rate: float = GUESS_RATE
    pick_planted: float = PICK_PLANTED
    known_correct: float = KNOWN_CORRECT
    # Noiseless students draw their (only) random choice from a per-question seed, so the same question always
    # gets the same answer, however many requests or processes ask it. The demo scenario relies on this.
    per_question_seed: str | None = None
    noise: float = 0.0

    def knows(self, construct_id: int) -> bool:
        return construct_id not in self.unknown

    def answer(self, question: dict | str) -> str:
        """Return the option key this student picks. Accepts a question id or any dict with an "id"."""
        q = self.bank[question if isinstance(question, str) else question["id"]]
        if self.per_question_seed is not None:
            self.rng = random.Random(f"{self.per_question_seed}:{q['id']}")
        options = q["options"]
        wrong = [o for o in options if not o.get("correct")]
        if self.noise and self.rng.random() < self.noise:
            unexplained = [o for o in wrong if o.get("misconception_id") not in self.misconceptions] or wrong
            return self.rng.choice(unexplained)["key"]
        key = self._rule_answer(q, options, wrong)
        if self.noise and key == next(o for o in options if o.get("correct"))["key"] and self.rng.random() < self.noise / 2:
            return self.rng.choice(wrong)["key"]
        return key

    def _rule_answer(self, q: dict, options: list[dict], wrong: list[dict]) -> str:
        if self.rng.random() < self.guess_rate:
            return self.rng.choice(options)["key"]
        planted = [o for o in wrong if o.get("misconception_id") in self.misconceptions]
        if planted and self.rng.random() < self.pick_planted:
            return self.rng.choice(planted)["key"]
        if self.knows(q["construct_id"]) and self.rng.random() < self.known_correct:
            return next(o for o in options if o.get("correct"))["key"]
        return self.rng.choice(wrong)["key"]


class Simulator:
    """Builds reproducible students: the same seed and ids always give the same students and answers.

    noiseless=True drops the guess rate and makes the planted and known rules certain, for tests.
    noise=p adds unexplained wrong answers and slips (see the module docstring); 0 by default.
    """

    def __init__(self, seed: int = 0, noiseless: bool = False, noise: float = 0.0):
        self.seed = seed
        self.noiseless = noiseless
        self.noise = noise
        self.rates = {"guess_rate": 0.0, "pick_planted": 1.0, "known_correct": 1.0} if noiseless else {}
        self.bank = load_bank()
        self.g = requires_graph(load_requires())  # edge a -> b means a REQUIRES b
        by_construct: dict[int, set[int]] = {}
        for q in self.bank.values():
            mids = {o["misconception_id"] for o in q["options"] if o.get("misconception_id") is not None}
            by_construct.setdefault(q["construct_id"], set()).update(mids)
        self.distractor_mids = by_construct
        # A construct can be a planted root cause if something depends on it and its questions have distractors.
        self.candidates = sorted(c for c in self.g.nodes if self.g.in_degree(c) > 0 and by_construct.get(c))

    def prerequisites_of(self, target: int) -> set[int]:
        """Every construct the target depends on (its prerequisites, any depth)."""
        return set(nx.descendants(self.g, target))

    def dependants(self, construct_id: int, max_hops: int | None = None) -> dict[int, int]:
        """Constructs that REQUIRE construct_id (directly or not), with their shortest hop count."""
        hops = nx.single_source_shortest_path_length(self.g.reverse(copy=False), construct_id, cutoff=max_hops)
        hops.pop(construct_id, None)
        return hops

    def student(self, student_id: str, root_cause: int | None = None, target: int | None = None,
                misconceptions: list[int] | None = None) -> SimStudent:
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
        if misconceptions is not None:
            if not set(misconceptions) <= set(pool):
                raise ValueError(f"misconceptions {misconceptions} are not distractors on {root}")
            planted = list(misconceptions)
        unknown = {root} | set(self.dependants(root))
        per_q = f"{self.seed}:{student_id}" if self.noiseless else None
        return SimStudent(student_id, root, planted, target, unknown, self.bank, rng, **self.rates, per_question_seed=per_q,
                          noise=self.noise)

    def cohort(self, student_ids: list[str]) -> list[SimStudent]:
        return [self.student(sid) for sid in student_ids]
