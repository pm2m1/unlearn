"""Ten workers claim one task at the same moment: exactly one may win (SPEC "claim")."""

import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from conftest import build_class

from unlearn import queries as Q
from unlearn import tools as T
from unlearn.db import delete_graph, run

CLASS_ID = "pytest_claim"
WORKERS = 10
ROUNDS = 20


@pytest.fixture(scope="module")
def claim_class():
    build_class(f"class_{CLASS_ID}")
    yield CLASS_ID
    delete_graph(f"class_{CLASS_ID}")


def _race(class_id: str) -> list[dict]:
    barrier = threading.Barrier(WORKERS)

    def worker(n):
        barrier.wait()
        return T.claim(class_id, "Diagnoser", f"w{n}")["rows"]

    with ThreadPoolExecutor(WORKERS) as pool:
        return list(pool.map(worker, range(WORKERS)))


@pytest.mark.parametrize("round_no", range(ROUNDS))
def test_exactly_one_claim_wins(claim_class, round_no):
    task_id = f"race-{round_no}"
    T.create_task(claim_class, task_id, "diagnose", "sa", "Diagnoser", ts=round_no)
    results = _race(claim_class)
    winners = [r for r in results if r]
    assert len(winners) == 1, f"{len(winners)} workers claimed {task_id}"
    assert winners[0] == [{"id": task_id, "kind": "diagnose"}]
    rows, _ = run(f"class_{claim_class}", Q.TASK_STATE, {"id": task_id})
    assert rows[0]["state"] == "working" and rows[0]["claimed_by"].startswith("w")
