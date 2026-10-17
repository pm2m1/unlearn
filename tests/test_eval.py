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
            return json.dumps({"misconceptions": ["Adds the numerators and adds the denominators"],
                               "prerequisite": "Find the lowest common multiple",
                               "root_cause": "Find the lowest common multiple"}), False
        return "Welcome back! Let's keep practising fractions today.", False

    monkeypatch.setattr(llm, "available", lambda: [fake])
    monkeypatch.setattr(llm, "complete", complete)
    monkeypatch.setattr(run_eval, "RESULTS", tmp_path)
    return calls, tmp_path


def test_no_key_stops_before_running(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(llm, "available", lambda: [])
    monkeypatch.setattr(run_eval, "RESULTS", tmp_path)
    assert run_eval.main(["--students", "2", "--seeds", "0"]) == 2
    assert "stops here" in capsys.readouterr().out
    assert not (tmp_path / "eval.json").exists()


def test_harness_runs_all_conditions(fake_llm):
    calls, out = fake_llm
    assert run_eval.main(["--students", "2", "--seeds", "0"]) == 0
    result = json.loads((out / "eval.json").read_text())
    assert set(result["summary"]) == {"A", "B", "C"}
    for c in "ABC":
        assert set(result["summary"][c]) == set(run_eval.METRICS)
    assert result["meta"]["llm"] == "fake / fake-1"
    assert "| Root-cause accuracy |" in (out / "eval.md").read_text()
    assert any("Candidate misconceptions retrieved" in c for c in calls)  # B saw retrieved misconceptions


def test_judge_recall_matches_close_sentences_only():
    from unlearn.db import run
    from unlearn import queries as Q
    judge = BL.Judge("class_template")
    rows, _ = run("class_template", "MATCH (m:Misconception {id:15341}) RETURN m.name AS n")
    name = rows[0]["n"]
    assert judge.recalled(f"Last time you showed: {name}.", [15341])
    assert not judge.recalled("Welcome back! Let's keep practising fractions today.", [15341])
