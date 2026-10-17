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
        self.construct_names = {r["id"]: r["name"] for r in rows}
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


class BudgetExceeded(RuntimeError):
    pass


# Every A/B LLM call goes through _call: it counts uncached calls, enforces an optional cap (the Gemini
# cross-check has a free-tier quota), and records time, tokens and JSON parse failures.
STATS = {"calls": 0, "cached": 0, "seconds": 0.0, "tokens": 0, "json_failures": 0, "limit": None}


def reset_stats(limit: int | None = None) -> None:
    STATS.update(calls=0, cached=0, seconds=0.0, tokens=0, json_failures=0, limit=limit)


def _call(provider, system: str, user: str) -> str:
    import time
    if STATS["limit"] is not None and STATS["calls"] >= STATS["limit"]:
        raise BudgetExceeded(f"LLM call cap {STATS['limit']} reached")
    from openai import APITimeoutError, InternalServerError, RateLimitError
    # Free tiers rate-limit per minute and hosted models have demand spikes (503): wait and retry the SAME model,
    # never another one.
    for attempt in range(4):
        try:
            t0 = time.perf_counter()
            text, cached = llm.complete(provider, [{"role": "system", "content": system}, {"role": "user", "content": user}])
            break
        except (RateLimitError, InternalServerError, APITimeoutError):
            if attempt == 3:
                raise
            time.sleep(20 * (attempt + 1))
    if cached:
        STATS["cached"] += 1
    else:
        STATS["calls"] += 1
        STATS["seconds"] += time.perf_counter() - t0
        STATS["tokens"] += llm.LAST_USAGE.get("tokens") or 0
    return text


def parse_json(text: str) -> dict | None:
    m = re.search(r"\{.*\}", text, re.S)
    try:
        return json.loads(m.group(0)) if m else None
    except json.JSONDecodeError:
        return None


def _ask(provider, system: str, user: str) -> dict:
    out = parse_json(_call(provider, system, user))
    if out is None:
        STATS["json_failures"] += 1
    return out or {}


def _say(provider, system: str, user: str) -> str:
    return _call(provider, system, user)


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


# --- candidates with IDs (the scoring fix) --------------------------------------------------------------
# The first eval asked for free text and snapped every guess to its nearest id, so a vague answer still "scored".
# Now A, B and B+ get candidate lists with ids and must answer with ids; an id that isn't on the list is unmapped.

def prerequisite_candidates(sim, student, names: dict[int, str]) -> list[tuple[int, str]]:
    """Root-cause candidates: every construct the target depends on (from requires.csv), with ids."""
    return [(c, names[c]) for c in sorted(_prerequisites(sim, student.target))]


def retrieved(judge: Judge, answers, k: int = RETRIEVE_K) -> list[tuple[int, str]]:
    """Top-k misconceptions with ids over these answers: each 'question + chosen option' embedded and searched."""
    best: dict[int, tuple[float, str]] = {}
    for q, key, _ in answers:
        chosen = next(o for o in q["options"] if o["key"] == key)
        for r in judge.nearest_misconceptions(f"{q['text']} {chosen['text']}", k):
            if r["id"] not in best or r["score"] < best[r["id"]][0]:
                best[r["id"]] = (r["score"], r["name"])
    return [(i, name) for i, (_, name) in sorted(best.items(), key=lambda kv: kv[1][0])[:k]]


def _listing(title: str, items: list[tuple[int, str]]) -> str:
    return f"{title}:\n" + "\n".join(f"[{i}] {name}" for i, name in items)


ID_REPLY = ('Reply as JSON with ids from the lists above only: {"misconception_ids": [up to 3 ids, most likely first], '
            '"root_cause_id": the id of the earlier skill this student is most likely missing}')


def map_ids(out: dict | None, misconceptions: list[tuple[int, str]], constructs: list[tuple[int, str]]) -> dict:
    """Keep only ids that were offered. Anything else is unmapped, not snapped to a neighbour."""
    allowed_m, allowed_c = {i for i, _ in misconceptions}, {i for i, _ in constructs}

    def as_int(x):
        try:
            return int(str(x).strip().strip("[]"))
        except (TypeError, ValueError):
            return None
    raw_m = (out or {}).get("misconception_ids") or []
    mids = []
    for x in raw_m if isinstance(raw_m, list) else [raw_m]:
        i = as_int(x)
        if i in allowed_m and i not in mids:
            mids.append(i)
    root = as_int((out or {}).get("root_cause_id"))
    return {"predicted": mids, "root": root if root in allowed_c else None, "json_ok": out is not None,
            "misconceptions_unmapped": not mids, "root_unmapped": root not in allowed_c}


# --- condition A: no memory -----------------------------------------------------------------------------

def condition_a(provider, judge: Judge, answers, constructs) -> dict:
    """One call per wrong answer, each seeing only that question (and its own retrieved candidates)."""
    last, calls = {"predicted": [], "root": None, "json_ok": True, "misconceptions_unmapped": True,
                   "root_unmapped": True}, 0
    for q, key, correct in answers:
        if correct:
            continue
        cands = retrieved(judge, [(q, key, correct)])
        calls += 1
        text = _call(provider, DIAG_SYSTEM, _render(q, key) + "\n\n" + _listing("Candidate misconceptions", cands)
                     + "\n\n" + _listing("Candidate earlier skills", constructs) + "\n\n" + ID_REPLY)
        out = parse_json(text)
        if out is None:
            STATS["json_failures"] += 1
        last = {**map_ids(out, cands, constructs), "raw": text}
    return {**last, "calls": calls}


def opening_a(provider) -> str:
    return _say(provider, OPEN_SYSTEM, "A student you have taught before starts a new session. You have no notes "
                "about them. Write your opening message.")


# --- condition B: vector RAG, and B+: vector RAG plus the graph as text --------------------------------------

def history_text(answers) -> str:
    return "\n".join(f"{i}. {_render(q, key)} ({'correct' if ok else 'wrong'})" for i, (q, key, ok) in enumerate(answers, 1))


def condition_b(provider, judge: Judge, answers, constructs, graph_text: str | None = None) -> dict:
    """B: attempt history + retrieved misconceptions + candidate skills. B+: the same, after the curated graph as
    text (every REQUIRES edge and every construct's misconceptions with SEEN_IN.w), put first so a local model
    can reuse its prompt cache across students."""
    cands = retrieved(judge, answers)
    body = ("Attempt history:\n" + history_text(answers) + "\n\n" + _listing("Candidate misconceptions retrieved "
            "from a misconception database (most similar first)", cands) + "\n\n"
            + _listing("Candidate earlier skills", constructs) + "\n\n" + ID_REPLY)
    text = _call(provider, DIAG_SYSTEM, (graph_text + "\n\n" if graph_text else "") + body)
    out = parse_json(text)
    if out is None:
        STATS["json_failures"] += 1
    return {**map_ids(out, cands, constructs), "raw": text, "calls": 1, "retrieved": [i for i, _ in cands]}


def graph_as_text(graph: str) -> str:
    """B+'s knowledge: the class graph's curated REQUIRES edges and every construct's misconceptions with weights."""
    from unlearn import queries as Q
    req, _ = run(graph, Q.ALL_REQUIRES)
    seen, _ = run(graph, Q.ALL_SEEN_IN)
    lines = ["PREREQUISITE GRAPH. Each line: a skill, then the earlier skill it requires (curated).",
             *[f"[{r['a']}] {r['a_name']} REQUIRES [{r['b']}] {r['b_name']}" for r in req], "",
             "MISCONCEPTIONS PER SKILL. Each line: a skill, then misconceptions seen in it with weight w (the "
             "misconception's share of its occurrences that fall on this skill).", ""]
    by = {}
    for r in seen:
        by.setdefault((r["cid"], r["cname"]), []).append(f"[{r['mid']}] {r['mname']} (w {r['w']:.2f})")
    for (cid, cname), ms in sorted(by.items()):
        lines.append(f"[{cid}] {cname}: " + "; ".join(ms))
    return "\n".join(lines)


def opening_b(provider, answers) -> str:
    return _say(provider, OPEN_SYSTEM, "Notes from this student's previous session (their answers):\n"
                + history_text(answers) + "\n\nWrite your opening message for the new session, referring to what "
                "they struggled with.")


# --- the first eval's free-text versions, kept so the audit can rebuild their exact (cached) prompts --------

def condition_a_text_prompts(answers) -> list[str]:
    """The first eval's A prompts, one per wrong answer."""
    return [_render(q, key) + '\nReply as JSON: {"misconceptions": [up to 3, most likely first], "prerequisite": '
            '"the earlier skill this student is most likely missing"}' for q, key, correct in answers if not correct]


def retrieve_names(judge: Judge, answers) -> list[str]:
    """The first eval's retriever exactly (ties broken by name), so its cached B prompts can be rebuilt."""
    best: dict[int, tuple[float, str]] = {}
    for q, key, _ in answers:
        chosen = next(o for o in q["options"] if o["key"] == key)
        for r in judge.nearest_misconceptions(f"{q['text']} {chosen['text']}", RETRIEVE_K):
            if r["id"] not in best or r["score"] < best[r["id"]][0]:
                best[r["id"]] = (r["score"], r["name"])
    return [name for _, name in sorted(best.values())[:RETRIEVE_K]]


def condition_b_text_prompt(judge: Judge, answers) -> str:
    candidates = retrieve_names(judge, answers)
    return ("Attempt history:\n" + history_text(answers)
            + "\n\nCandidate misconceptions retrieved from a misconception database (most similar first):\n"
            + "\n".join(f"- {c}" for c in candidates)
            + '\n\nReply as JSON: {"misconceptions": [the 3 most likely, most likely first], '
              '"root_cause": "the earlier skill this student is most likely missing"}')
