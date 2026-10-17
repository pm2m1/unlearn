"""The simulator is seeded, plants observable misconceptions, and answers by the SPEC's rates."""

import pytest

from eval.simulator import Simulator


@pytest.fixture(scope="module")
def sim():
    return Simulator(seed=7)


def test_same_seed_same_students_and_answers(sim):
    a, b = Simulator(seed=7).student("s01"), Simulator(seed=7).student("s01")
    assert (a.root_cause, a.misconceptions, a.target) == (b.root_cause, b.misconceptions, b.target)
    qids = sorted(sim.bank)[:30]
    assert [a.answer(q) for q in qids] == [b.answer(q) for q in qids]
    assert Simulator(seed=8).student("s01").misconceptions != a.misconceptions or \
        Simulator(seed=8).student("s01").root_cause != a.root_cause


def test_planted_state_is_consistent(sim):
    for s in sim.cohort([f"s{i:02d}" for i in range(1, 31)]):
        assert 1 <= len(s.misconceptions) <= 3
        assert set(s.misconceptions) <= sim.distractor_mids[s.root_cause]  # observable on the root cause
        hops = sim.dependants(s.root_cause, 4)
        assert 1 <= hops[s.target] <= 4
        if any(h >= 2 for h in hops.values()):
            assert hops[s.target] >= 2  # the diagnosis has to trace back at least 2 hops
        assert not s.knows(s.root_cause) and not s.knows(s.target)


def test_answer_rates(sim):
    s = sim.student("rates")
    root_q = next(q for q in sim.bank.values() if q["construct_id"] == s.root_cause and any(
        o.get("misconception_id") in s.misconceptions for o in q["options"]))
    planted_keys = {o["key"] for o in root_q["options"] if o.get("misconception_id") in s.misconceptions}
    known_q = next(q for q in sim.bank.values() if s.knows(q["construct_id"]) and not any(
        o.get("misconception_id") in s.misconceptions for o in q["options"]))
    correct_key = next(o["key"] for o in known_q["options"] if o.get("correct"))
    n = 4000
    planted = sum(s.answer(root_q) in planted_keys for _ in range(n)) / n
    correct = sum(s.answer(known_q) == correct_key for _ in range(n)) / n
    k, n_opts = len(planted_keys), len(root_q["options"])
    # Guess lands on a planted option, or no guess: pick planted (0.85), else a random wrong one may be planted.
    expected = 0.1 * k / n_opts + 0.9 * (0.85 + 0.15 * k / (n_opts - 1))
    assert planted == pytest.approx(expected, abs=0.03)
    assert correct == pytest.approx(0.9 * 0.9 + 0.1 / len(known_q["options"]), abs=0.03)
