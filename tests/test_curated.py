"""The curated DRAFT files validate, and class_template / class_demo were built from them."""

from collections import Counter
from pathlib import Path

import networkx as nx
import pandas as pd
import pytest

from unlearn import queries as Q
from unlearn.curation import load_questions, load_requires, load_skills, requires_graph
from unlearn.db import list_graphs, run

RAW = Path(__file__).resolve().parents[1] / "data" / "raw"


def test_requires_is_a_deep_enough_dag():
    rows = load_requires()
    g = requires_graph(rows)
    assert 40 <= len(rows) <= 60
    assert nx.is_directed_acyclic_graph(g)
    assert nx.dag_longest_path_length(g) >= 3


def test_questions_verify_against_eedi_seen_in():
    m = pd.read_csv(RAW / "misconception-map.csv")
    seen_in = m.groupby("ConstructId").MisconceptionId.apply(set).to_dict()
    questions = load_questions(seen_in=seen_in)
    per_construct = Counter(q["construct_id"] for q in questions)
    assert len(per_construct) == 40 and set(per_construct.values()) == {3}


def test_skills_cover_every_question_misconception():
    skills = load_skills(questions=load_questions())
    assert 6 <= len(skills) <= 8


@pytest.mark.parametrize("graph", ["class_template", "class_demo"])
def test_class_graphs_built(graph):
    assert graph in list_graphs()
    nodes = {r["label"]: r["n"] for r in run(graph, Q.COUNT_NODES_BY_LABEL)[0]}
    assert nodes["Construct"] == 40 and nodes["Question"] == 120 and nodes["Agent"] == 3
    assert nodes.get("Student", 0) == (30 if graph == "class_demo" else 0)
    req = run(graph, Q.REQUIRES_PROPS)[0][0]
    assert req["n"] == len(load_requires()) and req["weights"] == [1] and req["sources"] == ["curated"]
    indexes = {(r["label"], p) for r in run(graph, Q.LIST_INDEXES)[0] for p in r["properties"]}
    assert ("Misconception", "embedding") in indexes and ("Task", "state") in indexes
