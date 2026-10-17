"""Baselines A (no memory) and B (vector RAG) for the eval, and the judge every condition is scored with.

Both baselines see the same question pool as Unlearn and use the same LLM (one fixed provider, disk-cached
through llm.complete). Neither can choose questions adaptively, since that needs the graph: each asks the
same seeded sample of POOL_QUESTIONS from the target and everything it depends on.

  A  no memory   one LLM call per wrong answer, seeing only that question and answer; its diagnosis is the
                 latest call's. In session 2 it writes an opening with no context.
  B  vector RAG  one LLM call after the session, seeing the full attempt history as text plus the top-10
                 misconceptions retrieved by embedding "question + chosen option" for each answer (FalkorDB's
                 vector index over all class misconceptions). In session 2 it writes an opening from the history.

The judge maps free text to ids the same way for every condition: each guessed misconception to its nearest
misconception, the guessed prerequisite to its nearest construct, and a session-2 opening to the
misconceptions its sentences are close to (cosine distance <= RECALL_MAX_DISTANCE).
"""

import json
import random
import re

import numpy as np

from unlearn import llm
from unlearn import queries as Q
from unlearn.db import run
from unlearn.embed import embed

POOL_QUESTIONS = 6
RETRIEVE_K = 10
RECALL_MAX_DISTANCE = 0.35


# --- judge -------------------------------------------------------------------------------------------

class Judge:
    def __init__(self, graph: str):
        self.graph = graph
        rows, _ = run(graph, Q.CLASS_CONSTRUCTS)
        self.construct_ids = [r["id"] for r in rows]
        self.construct_vecs = np.array(embed([r["name"] for r in rows]))

    def nearest_misconceptions(self, text: str, k: int) -> list[dict]:
        rows, _ = run(self.graph, Q.NEAREST_MISCONCEPTIONS, {"k": k, "v": embed([text])[0]})
        return rows

    def misconception_ids(self, guesses: list[str]) -> list[int]:
        out = []
        for g in guesses:
            if g and g.strip():
                rows = self.nearest_misconceptions(g, 1)
                if rows and rows[0]["id"] not in out:
                    out.append(rows[0]["id"])
        return out

    def construct_id(self, text: str | None) -> int | None:
        if not text or not text.strip():
            return None
        v = np.array(embed([text])[0])
        return self.construct_ids[int(np.argmax(self.construct_vecs @ v))]

    def recalled(self, message: str, planted: list[int]) -> bool:
        for sentence in re.split(r"[.;:\n!?]", message or ""):
            if len(sentence.strip()) < 12:
                continue
            for r in self.nearest_misconceptions(sentence.strip(), 3):
                if r["id"] in planted and r["score"] <= RECALL_MAX_DISTANCE:
                    return True
        return False


# --- shared ---------------------------------------------------------------------------------------------

def pool_questions(sim, student) -> list[dict]:
    """The same seeded sample for A and B: questions on the target and every construct it depends on."""
    constructs = {student.target} | set(_prerequisites(sim, student.target))
    pool = sorted(q for q, v in sim.bank.items() if v["construct_id"] in constructs)
    rng = random.Random(f"pool:{sim.seed}:{student.id}")
    return [sim.bank[q] for q in rng.sample(pool, min(POOL_QUESTIONS, len(pool)))]


def _prerequisites(sim, target: int) -> list[int]:
    import networkx as nx
    return list(nx.descendants(sim.g, target))  # edge a -> b means a REQUIRES b


def _ask(provider, system: str, user: str) -> dict:
    text, _ = llm.complete(provider, [{"role": "system", "content": system}, {"role": "user", "content": user}])
    m = re.search(r"\{.*\}", text, re.S)
    try:
        return json.loads(m.group(0)) if m else {}
    except json.JSONDecodeError:
        return {}


def _say(provider, system: str, user: str) -> str:
    text, _ = llm.complete(provider, [{"role": "system", "content": system}, {"role": "user", "content": user}])
    return text


def _render(q: dict, key: str) -> str:
    opts = "; ".join(f"{o['key']}) {o['text']}" for o in q["options"])
    chosen = next(o for o in q["options"] if o["key"] == key)
    return f"Question: {q['text']}\nOptions: {opts}\nStudent chose: {key}) {chosen['text']}"


DIAG_SYSTEM = ("You diagnose school maths misconceptions. Reply with JSON only. Describe misconceptions as short "
               "statements about what the student believes or does wrong.")
OPEN_SYSTEM = "You are a maths tutor. Write the first message of a new tutoring session, at most 60 words."


def answer_session(student, questions: list[dict]) -> list[tuple[dict, str, bool]]:
    out = []
    for q in questions:
        key = student.answer(q)
        out.append((q, key, bool(next(o for o in q["options"] if o["key"] == key).get("correct"))))
    return out


# --- condition A: no memory -----------------------------------------------------------------------------

def condition_a(provider, answers) -> dict:
    """One call per wrong answer, each seeing only that question; the diagnosis is the latest call's."""
    last = {}
    calls = 0
    for q, key, correct in answers:
        if correct:
            continue
        calls += 1
        last = _ask(provider, DIAG_SYSTEM, _render(q, key) + '\nReply as JSON: {"misconceptions": [up to 3, most likely '
                    'first], "prerequisite": "the earlier skill this student is most likely missing"}')
    return {"misconceptions": last.get("misconceptions") or [], "root_cause": last.get("prerequisite"), "calls": calls}


def opening_a(provider) -> str:
    return _say(provider, OPEN_SYSTEM, "A student you have taught before starts a new session. You have no notes "
                "about them. Write your opening message.")


# --- condition B: vector RAG -------------------------------------------------------------------------------

def retrieve(judge: Judge, answers) -> list[str]:
    """Top-10 misconceptions over the session: each answer's 'question + chosen option' embedded and searched."""
    best: dict[int, tuple[float, str]] = {}
    for q, key, _ in answers:
        chosen = next(o for o in q["options"] if o["key"] == key)
        for r in judge.nearest_misconceptions(f"{q['text']} {chosen['text']}", RETRIEVE_K):
            if r["id"] not in best or r["score"] < best[r["id"]][0]:
                best[r["id"]] = (r["score"], r["name"])
    return [name for _, name in sorted(best.values())[:RETRIEVE_K]]


def history_text(answers) -> str:
    return "\n".join(f"{i}. {_render(q, key)} ({'correct' if ok else 'wrong'})" for i, (q, key, ok) in enumerate(answers, 1))


def condition_b(provider, judge: Judge, answers) -> dict:
    candidates = retrieve(judge, answers)
    out = _ask(provider, DIAG_SYSTEM, "Attempt history:\n" + history_text(answers)
               + "\n\nCandidate misconceptions retrieved from a misconception database (most similar first):\n"
               + "\n".join(f"- {c}" for c in candidates)
               + '\n\nReply as JSON: {"misconceptions": [the 3 most likely, most likely first], '
                 '"root_cause": "the earlier skill this student is most likely missing"}')
    return {"misconceptions": out.get("misconceptions") or [], "root_cause": out.get("root_cause"), "calls": 1,
            "retrieved": candidates}


def opening_b(provider, answers) -> str:
    return _say(provider, OPEN_SYSTEM, "Notes from this student's previous session (their answers):\n"
                + history_text(answers) + "\n\nWrite your opening message for the new session, referring to what "
                "they struggled with.")
