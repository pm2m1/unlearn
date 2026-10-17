"""The demo video's scenario replays exactly: same 40% check, different correct roots, recall in session 2."""

import importlib.util
from pathlib import Path

import pytest

from unlearn import tools as T
from unlearn.db import delete_graph

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def scenario():
    spec = importlib.util.spec_from_file_location("demo_scenario", ROOT / "scripts" / "demo_scenario.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.CLASS_ID = "pytest_video"
    yield mod
    delete_graph("class_pytest_video")


def test_same_score_different_roots_and_recall(scenario):
    checks = scenario.build()
    assert checks == {"asha": {"correct": 2, "total": 5}, "ben": {"correct": 2, "total": 5}}
    roots = {}
    for sid, p in scenario.STUDENTS.items():
        s1 = scenario.play(sid, 1)
        assert s1["root"] == p["root"] and 2 <= len(s1["chain"]) - 1 <= 3
        roots[sid] = s1["root"]
        s2 = scenario.play(sid, 2)
        planted = {r["mid"]: r["name"] for r in T.showed_on("pytest_video", sid, p["root"])["rows"]}
        assert any(planted[m] in s2["recall"] for m in p["mids"])
    assert roots["asha"] != roots["ben"]
    # Asha's root sits outside the Fractions topic.
    from unlearn.curation import PREREQ_CONSTRUCTS
    assert roots["asha"] in PREREQ_CONSTRUCTS and roots["ben"] not in PREREQ_CONSTRUCTS
