"""The 16 agent tools. Each wraps fixed Cypher from queries.py and returns a receipt.

Every tool returns {cypher, params, rows, node_ids}:
  cypher    list of query strings run, in order
  params    list of the params for each query
  rows      the tool's result rows
  node_ids  [{label, id}] for the domain nodes the result points at, so the UI can draw the path
Every class tool takes class_id and runs against graph class_<class_id>.
"""

import json
import time

from unlearn import queries as Q
from unlearn.db import run

PROPOSAL_KINDS = {"regroup", "skip_ahead", "assign_practice"}
DECISIONS = {"approved", "rejected"}
MASTERY_CORRECT = 2
MASTERY_MAX_CONFIDENCE = 0.6


def now_ms() -> int:
    return time.time_ns() // 1_000_000


def graph_name(class_id: str) -> str:
    return f"class_{class_id}"


class _Receipt:
    """Collects every query a tool runs so the receipt shows all of them."""

    def __init__(self, graph: str):
        self.graph, self.cypher, self.params = graph, [], []

    def run(self, query: str, params: dict | None = None) -> list[dict]:
        rows, receipt = run(self.graph, query, params)
        self.cypher.append(query.strip())
        self.params.append(receipt["params"])
        return rows

    def done(self, rows: list[dict], node_ids: list[dict]) -> dict:
        seen, unique = set(), []
        for n in node_ids:
            key = (n["label"], n["id"])
            if n["id"] is not None and key not in seen:
                seen.add(key)
                unique.append(n)
        return {"cypher": self.cypher, "params": self.params, "rows": rows, "node_ids": unique}


def _ids(label: str, values) -> list[dict]:
    return [{"label": label, "id": v} for v in values]


# --- Diagnosis ----------------------------------------------------------------

def record_attempt(class_id: str, student_id: str, question_id: str, key: str,
                   session_id: str, ts: int | None = None) -> dict:
    """Record an answer, update SHOWED for the misconception behind it, and mark MASTERED when earned."""
    ts = ts if ts is not None else now_ms()
    r = _Receipt(graph_name(class_id))
    rows = r.run(Q.RECORD_ATTEMPT, {"sid": student_id, "qid": question_id, "key": key, "ts": ts, "sess": session_id})
    if not rows:
        raise ValueError(f"no student {student_id!r}, question {question_id!r} or option {key!r}")
    row = rows[0]
    if row["mid"] is not None:
        r.run(Q.UPDATE_SHOWED, {"sid": student_id, "mid": row["mid"], "ts": ts})

    ev = r.run(Q.MASTERY_EVIDENCE, {"sid": student_id, "qid": question_id})[0]
    max_conf = ev["max_confidence"] or 0.0
    row["mastered"] = None
    if ev["correct"] >= MASTERY_CORRECT and max_conf <= MASTERY_MAX_CONFIDENCE:
        evidence = f"{ev['correct']} correct, max misconception confidence {max_conf:.2f}"
        r.run(Q.MARK_MASTERED, {"sid": student_id, "cid": ev["cid"], "ts": ts, "evidence": evidence})
        row["mastered"] = ev["cid"]
    nodes = _ids("Student", [student_id]) + _ids("Question", [question_id]) + _ids("Misconception", [row["mid"]])
    nodes += _ids("Construct", [row["mastered"]])
    return r.done([row], nodes)


def diagnose_text(class_id: str, construct_id: int, explanation: str) -> dict:
    """Map a free-text explanation to the closest misconceptions seen in this construct."""
    from unlearn.embed import embed

    r = _Receipt(graph_name(class_id))
    rows = r.run(Q.DIAGNOSE_TEXT, {"v": embed([explanation])[0], "cid": construct_id})
    return r.done(rows, _ids("Misconception", [x["id"] for x in rows]) + _ids("Construct", [construct_id]))


def next_question(class_id: str, student_id: str, construct_id: int) -> dict:
    """The unattempted question on this construct that probes the most unshown misconceptions."""
    r = _Receipt(graph_name(class_id))
    rows = r.run(Q.NEXT_QUESTION, {"sid": student_id, "cid": construct_id})
    for row in rows:
        row["unprobed"] = int(row["unprobed"])  # sum() comes back as a float
        row["options"] = r.run(Q.QUESTION_OPTIONS, {"qid": row["id"]})
    return r.done(rows, _ids("Question", [x["id"] for x in rows]) + _ids("Construct", [construct_id]))


# --- Root cause ---------------------------------------------------------------

def root_cause(class_id: str, student_id: str, construct_id: int) -> dict:
    """Deepest unmastered prerequisite with misconception evidence, plus the REQUIRES chain."""
    r = _Receipt(graph_name(class_id))
    rows = r.run(Q.ROOT_CAUSE, {"sid": student_id, "cid": construct_id})
    nodes = _ids("Student", [student_id]) + _ids("Construct", [construct_id])
    if rows:
        chain = r.run(Q.ROOT_CAUSE_CHAIN, {"cid": construct_id, "pid": rows[0]["id"]})
        rows[0]["chain"] = chain[0]["chain"] if chain else []
        rows[0]["chain_ids"] = chain[0]["ids"] if chain else []
        nodes += _ids("Construct", rows[0]["chain_ids"])
    nodes += _ids("Construct", [x["id"] for x in rows])
    return r.done(rows, nodes)


def probe_frontier(class_id: str, student_id: str, construct_id: int) -> dict:
    """Deepest unmastered, unattempted prerequisites to ask about next."""
    r = _Receipt(graph_name(class_id))
    rows = r.run(Q.PROBE_FRONTIER, {"sid": student_id, "cid": construct_id})
    return r.done(rows, _ids("Construct", [construct_id] + [x["id"] for x in rows]))


# --- Teaching and memory ------------------------------------------------------

def learning_path(class_id: str, student_id: str, target_id: int, to_id: int | None = None) -> dict:
    """Teaching order (deepest first) for every unmastered construct the target depends on.

    With to_id, also returns the shortest REQUIRES chain from the target down to that construct.
    """
    r = _Receipt(graph_name(class_id))
    rows = r.run(Q.LEARNING_PATH, {"sid": student_id, "tid": target_id})
    nodes = _ids("Construct", [x["id"] for x in rows])
    if to_id is not None:
        sp = r.run(Q.LEARNING_PATH_SP, {"tid": target_id, "mid": to_id})
        rows = [{**x, "shortest_chain": sp[0]["chain"] if sp else None} for x in rows] if rows else []
    return r.done(rows, nodes)


def recall(class_id: str, student_id: str) -> dict:
    """What the tutor remembers: confident misconceptions with their latest events."""
    r = _Receipt(graph_name(class_id))
    rows = r.run(Q.RECALL, {"sid": student_id})
    return r.done(rows, _ids("Student", [student_id]))


def pick_skill(class_id: str, misconception_id: int) -> dict:
    """The remediation skill with the best success rate for this misconception."""
    r = _Receipt(graph_name(class_id))
    rows = r.run(Q.PICK_SKILL, {"mid": misconception_id})
    return r.done(rows, _ids("Skill", [x["skill"] for x in rows]) + _ids("Misconception", [misconception_id]))


def update_skill(class_id: str, name: str, ok: bool) -> dict:
    """Update a skill's success rate after a check question. The +2/+3 prior keeps one result from swinging it to 0 or 1."""
    r = _Receipt(graph_name(class_id))
    r.run(Q.UPDATE_SKILL, {"name": name, "ok": 1.0 if ok else 0.0})
    rows = r.run(Q.SKILL_BY_NAME, {"name": name})
    return r.done(rows, _ids("Skill", [name]))


def start_session(class_id: str, student_id: str, session_id: str, ts: int | None = None) -> dict:
    """Helper, not one of the 16 tools: open a Session for episodic memory."""
    r = _Receipt(graph_name(class_id))
    rows = r.run(Q.START_SESSION, {"sid": student_id, "sess": session_id, "ts": ts if ts is not None else now_ms()})
    return r.done(rows, _ids("Student", [student_id]))


def log_event(class_id: str, session_id: str, event_id: str, type_: str, summary: str,
              misconception_id: int | None = None, construct_id: int | None = None, ts: int | None = None) -> dict:
    """Helper, not one of the 16 tools: log an Event in a session, ABOUT a misconception and/or construct."""
    r = _Receipt(graph_name(class_id))
    rows = r.run(Q.LOG_EVENT, {"sess": session_id, "id": event_id, "type": type_, "summary": summary,
                               "mid": misconception_id, "cid": construct_id,
                               "ts": ts if ts is not None else now_ms()})
    return r.done(rows, _ids("Misconception", [misconception_id]) + _ids("Construct", [construct_id]))


# --- Teacher analytics --------------------------------------------------------

def cohorts(class_id: str) -> dict:
    """Rebuild SHARES_GAP edges between students, then group them with WCC."""
    r = _Receipt(graph_name(class_id))
    r.run(Q.COHORTS_CLEAR)
    r.run(Q.COHORTS_LINK)
    rows = r.run(Q.COHORTS_WCC)
    return r.done(rows, [])


def keystones(class_id: str) -> dict:
    """PageRank on REQUIRES: the constructs most of the topic depends on. Writes c.pagerank for the top 10."""
    r = _Receipt(graph_name(class_id))
    rows = r.run(Q.KEYSTONES)
    r.run(Q.SET_PAGERANK, {"rows": [{"id": x["id"], "score": x["score"]} for x in rows]})
    return r.done(rows, _ids("Construct", [x["id"] for x in rows]))


def bridges() -> dict:
    """Betweenness on the curriculum's SHARES_MISCONCEPTION edges (fixed seed)."""
    r = _Receipt("curriculum")
    rows = r.run(Q.BRIDGES)
    return r.done(rows, [])


# --- Coordination -------------------------------------------------------------

def create_task(class_id: str, task_id: str, kind: str, student_id: str, agent: str, ts: int | None = None) -> dict:
    """Helper, not one of the 16 tools: open the first task of a chain."""
    r = _Receipt(graph_name(class_id))
    rows = r.run(Q.CREATE_TASK, {"id": task_id, "kind": kind, "sid": student_id, "agent": agent,
                                 "ts": ts if ts is not None else now_ms()})
    return r.done(rows, _ids("Task", [task_id]) + _ids("Student", [student_id]))


def claim(class_id: str, agent: str, worker: str) -> dict:
    """Claim the oldest submitted task for an agent. At most one worker wins a task."""
    r = _Receipt(graph_name(class_id))
    rows = r.run(Q.CLAIM, {"agent": agent, "worker": worker})
    return r.done(rows, _ids("Task", [x["id"] for x in rows]))


def handoff(class_id: str, prev_task_id: str, student_id: str, to_agent: str, kind: str,
            task_id: str, ts: int | None = None) -> dict:
    """Complete prev_task_id and open the next task for to_agent, keeping the chain."""
    r = _Receipt(graph_name(class_id))
    rows = r.run(Q.HANDOFF, {"prev": prev_task_id, "sid": student_id, "to": to_agent, "id": task_id,
                             "kind": kind, "ts": ts if ts is not None else now_ms()})
    return r.done(rows, _ids("Task", [prev_task_id, task_id]) + _ids("Student", [student_id]))


def propose(class_id: str, proposal_id: str, kind: str, payload: dict, student_ids: list[str],
            ts: int | None = None) -> dict:
    """Write a pending Proposal for the teacher. Only allowlisted kinds."""
    if kind not in PROPOSAL_KINDS:
        raise ValueError(f"proposal kind {kind!r} not in {sorted(PROPOSAL_KINDS)}")
    r = _Receipt(graph_name(class_id))
    r.run(Q.PROPOSE, {"id": proposal_id, "kind": kind, "json": json.dumps(payload), "sids": student_ids,
                      "ts": ts if ts is not None else now_ms()})
    rows = [{"id": proposal_id, "kind": kind, "state": "pending"}]
    return r.done(rows, _ids("Proposal", [proposal_id]) + _ids("Student", student_ids))


def decide(class_id: str, proposal_id: str, decision: str, ts: int | None = None) -> dict:
    """Approve or reject a pending proposal. Returns nothing if it was not pending."""
    if decision not in DECISIONS:
        raise ValueError(f"decision must be one of {sorted(DECISIONS)}")
    r = _Receipt(graph_name(class_id))
    rows = r.run(Q.DECIDE, {"id": proposal_id, "decision": decision, "ts": ts if ts is not None else now_ms()})
    for row in rows:
        row["payload"] = json.loads(row["payload"])
    return r.done(rows, _ids("Proposal", [proposal_id]))


TOOLS = [record_attempt, diagnose_text, next_question, root_cause, probe_frontier, learning_path, recall,
         pick_skill, update_skill, cohorts, keystones, bridges, handoff, claim, propose, decide]
