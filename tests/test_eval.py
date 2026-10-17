"""The eval harness runs end to end with a fake LLM (test only: no numbers from it are reported)."""

import json

import pytest

from eval import baselines as BL
from eval import run_eval
from unlearn import llm


@pytest.fixture
def fake_llm(monkeypatch, tmp_path):
    fake = llm.Provider("fake", "FAKE", "http://unused", "FAKE_MODEL", "fake-1")
    calls = []

    def complete(provider, messages):
        calls.append(messages[-1]["content"])
        if "Reply as JSON" in messages[-1]["content"]:
            return json.dumps({"misconception_ids": [15341, 99999999], "root_cause_id": 345}), False
        return "Welcome back! Let's keep practising fractions today.", False

    monkeypatch.setattr(run_eval, "eval_provider", lambda which, model: (fake, None))
    monkeypatch.setattr(llm, "complete", complete)
    monkeypatch.setattr(run_eval, "RESULTS", tmp_path)
    return calls, tmp_path


def test_no_model_stops_before_running(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(run_eval, "eval_provider", lambda which, model: (None, "Ollama is not reachable"))
    monkeypatch.setattr(run_eval, "RESULTS", tmp_path)
    assert run_eval.main(["--students", "2", "--seeds", "0", "--out", "pytest_eval"]) == 2
    assert "stops here" in capsys.readouterr().out
    assert not (tmp_path / "pytest_eval.json").exists()


def test_harness_runs_all_conditions(fake_llm):
    calls, out = fake_llm
    # Own output name: its scratch graphs (class_pytest_eval_s0) never collide with a real eval run.
    assert run_eval.main(["--students", "2", "--seeds", "0", "--out", "pytest_eval"]) == 0
    result = json.loads((out / "pytest_eval.json").read_text())
    assert set(result["summary"]) == {"A", "B", "B+", "C"}
    for c in ("A", "B", "B+", "C"):
        assert set(result["summary"][c]) == set(run_eval.METRICS)
    assert result["meta"]["llm"] == "fake / fake-1"
    assert result["meta"]["calibration"]["json_valid"] == "2/2"
    assert "| Root-cause accuracy |" in (out / "pytest_eval.md").read_text()
    assert any("Candidate misconceptions retrieved" in c for c in calls)  # B saw retrieved misconceptions
    assert any("PREREQUISITE GRAPH" in c for c in calls)                   # B+ saw the graph as text
    # Ids that weren't offered are dropped, never snapped to a neighbour.
    rows = result["students"]["0"]["B"]
    assert all(99999999 not in r["predicted"] for r in rows)


def test_judge_recall_matches_close_sentences_only():
    from unlearn.db import run
    from unlearn import queries as Q
    judge = BL.Judge("class_template")
    rows, _ = run("class_template", "MATCH (m:Misconception {id:15341}) RETURN m.name AS n")
    name = rows[0]["n"]
    assert judge.recalled(f"Last time you showed: {name}.", [15341])
    assert not judge.recalled("Welcome back! Let's keep practising fractions today.", [15341])


def test_call_cap_stops_cleanly(fake_llm):
    calls, out = fake_llm
    assert run_eval.main(["--students", "3", "--seeds", "0", "--conditions", "A,B", "--max-calls", "4",
                          "--out", "pytest_capped"]) == 0
    result = json.loads((out / "pytest_capped.json").read_text())
    total = result["meta"]["llm_calls"]["calls"] + result["meta"]["calibration"]["calls"]
    assert total <= 4 and "cap" in result["meta"]["stopped"]  # the cap includes the calibration calls
