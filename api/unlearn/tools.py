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


def next_question(class_id: str, student_id: str, construct_id: int, session_id: str) -> dict:
    """A question on this construct not yet asked in this session: never-attempted first, then least recently
    attempted, then the one whose options probe the most misconceptions the student hasn't shown."""
    r = _Receipt(graph_name(class_id))
    rows = r.run(Q.NEXT_QUESTION, {"sid": student_id, "cid": construct_id, "sess": session_id})
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
    """The remediation skill with the best success rate for this misconception, with its steps."""
    r = _Receipt(graph_name(class_id))
    rows = r.run(Q.PICK_SKILL, {"mid": misconception_id})
    for row in rows:
        row["steps"] = [x["text"] for x in r.run(Q.SKILL_STEPS, {"name": row["skill"]})]
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

def create_task(class_id: str, task_id: str, kind: str, student_id: str, agent: str, ts: int | None = None,
                construct_id: int | None = None, session_id: str | None = None) -> dict:
    """Helper, not one of the 16 tools: open the first task of a chain. Later tasks inherit its construct and session."""
    r = _Receipt(graph_name(class_id))
    rows = r.run(Q.CREATE_TASK, {"id": task_id, "kind": kind, "sid": student_id, "agent": agent,
                                 "ts": ts if ts is not None else now_ms(), "cid": construct_id, "sess": session_id})
    return r.done(rows, _ids("Task", [task_id]) + _ids("Student", [student_id]))


def claim(class_id: str, agent: str, worker: str, session_id: str | None = None) -> dict:
    """Claim the oldest submitted task for an agent (only in one session, if given). At most one worker wins a task."""
    r = _Receipt(graph_name(class_id))
    if session_id is None:
        rows = r.run(Q.CLAIM, {"agent": agent, "worker": worker})
    else:
        rows = r.run(Q.CLAIM_IN_SESSION, {"agent": agent, "worker": worker, "sess": session_id})
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
    """Write a pending Proposal for the teacher. Only allowlisted kinds, with the payload their executor needs."""
    if kind not in PROPOSAL_KINDS:
        raise ValueError(f"proposal kind {kind!r} not in {sorted(PROPOSAL_KINDS)}")
    if not student_ids:
        raise ValueError("a proposal needs at least one student")
    if kind == "regroup" and len(set(student_ids)) < 2:
        raise ValueError("regroup needs at least two students")
    if kind in ("skip_ahead", "assign_practice") and not isinstance(payload.get("construct_id"), int):
        raise ValueError(f"{kind} needs an integer payload['construct_id']")
    r = _Receipt(graph_name(class_id))
    r.run(Q.PROPOSE, {"id": proposal_id, "kind": kind, "json": json.dumps(payload), "sids": student_ids,
                      "ts": ts if ts is not None else now_ms()})
    rows = [{"id": proposal_id, "kind": kind, "state": "pending"}]
    return r.done(rows, _ids("Proposal", [proposal_id]) + _ids("Student", student_ids))


def decide(class_id: str, proposal_id: str, decision: str, ts: int | None = None) -> dict:
    """Approve or reject a pending proposal. Returns nothing if it was not pending.

    Approval runs the executor for the proposal's kind and logs an Event; rejection only changes state.
    """
    if decision not in DECISIONS:
        raise ValueError(f"decision must be one of {sorted(DECISIONS)}")
    ts = ts if ts is not None else now_ms()
    r = _Receipt(graph_name(class_id))
    rows = r.run(Q.DECIDE, {"id": proposal_id, "decision": decision, "ts": ts})
    nodes = _ids("Proposal", [proposal_id])
    for row in rows:
        row["payload"] = json.loads(row["payload"])
        if decision == "approved":
            row["applied"], more = _execute(r, proposal_id, row["kind"], row["payload"], ts)
            nodes += more
    return r.done(rows, nodes)


def _execute(r: _Receipt, proposal_id: str, kind: str, payload: dict, ts: int) -> tuple[dict, list[dict]]:
    """Apply an approved proposal. The change is read from the graph (FOR edges), not trusted from the caller."""
    cid = payload.get("construct_id")
    if kind == "regroup":
        gid = payload.get("group_id") or f"g-{proposal_id}"
        out = r.run(Q.EXEC_REGROUP, {"pid": proposal_id, "gid": gid})[0]
        summary = f"Teacher approved regroup: group {gid} with {', '.join(out['members'])}"
        nodes = _ids("Group", [gid]) + _ids("Student", out["members"])
    elif kind == "skip_ahead":
        rows = r.run(Q.EXEC_SKIP_AHEAD, {"pid": proposal_id, "cid": cid, "ts": ts})
        out = {"construct_id": cid, "students": [x["student_id"] for x in rows]}
        summary = f"Teacher approved skip_ahead: construct {cid} marked mastered for {', '.join(out['students'])}"
        nodes = _ids("Construct", [cid]) + _ids("Student", out["students"])
    else:  # assign_practice
        aid = payload.get("assignment_id") or f"a-{proposal_id}"
        out = r.run(Q.EXEC_ASSIGN_PRACTICE, {"pid": proposal_id, "cid": cid, "aid": aid, "ts": ts})[0]
        summary = f"Teacher approved assign_practice: construct {cid} for {', '.join(out['students'])}"
        nodes = _ids("Assignment", [aid]) + _ids("Construct", [cid]) + _ids("Student", out["students"])
    ev = r.run(Q.LOG_PROPOSAL_EVENT, {"pid": proposal_id, "id": f"{proposal_id}-applied", "type": "proposal_applied",
                                      "ts": ts, "summary": summary, "cid": cid})[0]
    out["event_id"] = ev["id"]
    return out, nodes + _ids("Event", [ev["id"]])


# --- Agent helpers (not among the 16 tools) -----------------------------------

def task_context(class_id: str, task_id: str) -> dict:
    """The student, construct and session a task is about."""
    r = _Receipt(graph_name(class_id))
    rows = r.run(Q.TASK_CONTEXT, {"id": task_id})
    return r.done(rows, _ids("Task", [task_id]) + _ids("Student", [x["student_id"] for x in rows]))


def sessions(class_id: str, student_id: str) -> dict:
    """The student's sessions, oldest first."""
    r = _Receipt(graph_name(class_id))
    return r.done(r.run(Q.STUDENT_SESSIONS, {"sid": student_id}), _ids("Student", [student_id]))


def complete_task(class_id: str, task_id: str) -> dict:
    """End a chain: mark the last task completed without handing off."""
    r = _Receipt(graph_name(class_id))
    return r.done(r.run(Q.COMPLETE_TASK, {"id": task_id}), _ids("Task", [task_id]))


def fail_task(class_id: str, task_id: str, error: str) -> dict:
    r = _Receipt(graph_name(class_id))
    return r.done(r.run(Q.FAIL_TASK, {"id": task_id, "error": error[:500]}), _ids("Task", [task_id]))


def chain(class_id: str, root_task_id: str) -> dict:
    """Every task handed off from root_task_id, in order, with its agent and state."""
    r = _Receipt(graph_name(class_id))
    rows = r.run(Q.CHAIN, {"root": root_task_id})
    open_ = r.run(Q.CHAIN_OPEN, {"root": root_task_id})[0]["open"]
    return {**r.done(rows, _ids("Task", [x["id"] for x in rows])), "open": open_}


def showed_on(class_id: str, student_id: str, construct_id: int) -> dict:
    """The student's misconceptions on one construct, strongest weighted evidence first."""
    r = _Receipt(graph_name(class_id))
    rows = r.run(Q.SHOWED_ON, {"sid": student_id, "cid": construct_id})
    return r.done(rows, _ids("Misconception", [x["mid"] for x in rows]) + _ids("Construct", [construct_id]))


def proposals(class_id: str, state: str | None = "pending") -> dict:
    r = _Receipt(graph_name(class_id))
    rows = r.run(Q.PROPOSALS, {"state": state})
    for row in rows:
        row["payload"] = json.loads(row["payload"])
    return r.done(rows, _ids("Proposal", [x["id"] for x in rows]))


def name_vocabulary(class_id: str) -> dict:
    """Every construct and misconception name in the class graph, for the receipt check."""
    r = _Receipt(graph_name(class_id))
    return r.done(r.run(Q.NAME_VOCABULARY), [])


def reset_student(class_id: str, student_id: str) -> dict:
    """Demo helper: forget one student's sessions, attempts, evidence, tasks and proposals."""
    r = _Receipt(graph_name(class_id))
    for q in (Q.RESET_STUDENT_PROPOSALS, Q.RESET_STUDENT_TASKS, Q.RESET_STUDENT_SESSIONS,
              Q.RESET_STUDENT_EDGES, Q.RESET_STUDENT_GROUPS):
        r.run(q, {"sid": student_id})
    return r.done([], _ids("Student", [student_id]))


def claim_task(class_id: str, task_id: str, agent: str, worker: str) -> dict:
    """Claim one specific submitted task. Empty rows if someone else already has it."""
    r = _Receipt(graph_name(class_id))
    rows = r.run(Q.CLAIM_TASK, {"id": task_id, "agent": agent, "worker": worker})
    return r.done(rows, _ids("Task", [task_id]))


def set_pending(class_id: str, task_id: str, question_id: str | None, construct_id: int | None) -> dict:
    """Record the question a task is waiting on, or clear it."""
    r = _Receipt(graph_name(class_id))
    rows = r.run(Q.SET_PENDING, {"id": task_id, "qid": question_id, "cid": construct_id})
    return r.done(rows, _ids("Task", [task_id]) + _ids("Question", [question_id]))


def set_tutor_plan(class_id: str, task_id: str, skill: str | None, misconception_id: int, root_id: int) -> dict:
    r = _Receipt(graph_name(class_id))
    rows = r.run(Q.SET_TUTOR_PLAN, {"id": task_id, "skill": skill, "mid": misconception_id, "root": root_id})
    return r.done(rows, _ids("Task", [task_id]))


def session_tasks(class_id: str, session_id: str) -> dict:
    r = _Receipt(graph_name(class_id))
    rows = r.run(Q.SESSION_TASKS, {"sess": session_id})
    return r.done(rows, _ids("Task", [x["id"] for x in rows]))


def session_state(class_id: str, student_id: str, session_id: str) -> dict:
    """This session's attempts in order, and the constructs they rule out (answered right, plus their prerequisites)."""
    r = _Receipt(graph_name(class_id))
    attempts = r.run(Q.SESSION_ATTEMPTS, {"sid": student_id, "sess": session_id})
    ruled_out = r.run(Q.SESSION_RULED_OUT, {"sid": student_id, "sess": session_id})
    rows = [{"attempts": attempts, "ruled_out": ruled_out[0]["ids"] if ruled_out else []}]
    return r.done(rows, _ids("Student", [student_id]) + _ids("Question", [a["qid"] for a in attempts]))


def session_lookup(class_id: str, session_id: str) -> dict:
    r = _Receipt(graph_name(class_id))
    rows = r.run(Q.SESSION_LOOKUP, {"sess": session_id})
    return r.done(rows, _ids("Student", [x["student_id"] for x in rows]))


def student_graph(class_id: str, student_id: str, target_id: int, session_id: str | None = None) -> dict:
    """The student's slice under a target for the graph panel: constructs, REQUIRES edges, the student's
    misconceptions on them, mastered constructs, this session's attempts, and root_cause with its chain."""
    r = _Receipt(graph_name(class_id))
    constructs = r.run(Q.SLICE_FOR_TARGET, {"tid": target_id})
    cids = [x["id"] for x in constructs]
    edges = r.run(Q.SLICE_EDGES, {"tid": target_id})
    showed = r.run(Q.STUDENT_SHOWED_ON_SLICE, {"sid": student_id, "cids": cids})
    mastered = r.run(Q.STUDENT_MASTERED_ON_SLICE, {"sid": student_id, "cids": cids})
    attempts = r.run(Q.SESSION_ATTEMPTS, {"sid": student_id, "sess": session_id}) if session_id else []
    rc = r.run(Q.ROOT_CAUSE, {"sid": student_id, "cid": target_id})
    chain = r.run(Q.ROOT_CAUSE_CHAIN, {"cid": target_id, "pid": rc[0]["id"]}) if rc else []
    row = {"target": target_id, "constructs": constructs, "requires": edges, "showed": showed,
           "mastered": mastered, "attempts": attempts, "root_cause": rc,
           "chain_ids": chain[0]["ids"] if chain else []}
    return r.done([row], _ids("Student", [student_id]) + _ids("Construct", cids))


def class_students(class_id: str) -> dict:
    r = _Receipt(graph_name(class_id))
    rows = r.run(Q.CLASS_STUDENTS)
    return r.done(rows, _ids("Student", [x["id"] for x in rows]))


def targets(class_id: str) -> dict:
    r = _Receipt(graph_name(class_id))
    rows = r.run(Q.TARGETS)
    return r.done(rows, _ids("Construct", [x["id"] for x in rows]))


def proposal_lookup(class_id: str, proposal_id: str) -> dict:
    r = _Receipt(graph_name(class_id))
    return r.done(r.run(Q.PROPOSAL_LOOKUP, {"id": proposal_id}), _ids("Proposal", [proposal_id]))


# Query text -> its name in queries.py, so traces can print "ROOT_CAUSE" instead of the Cypher.
QUERY_NAMES = {v.strip(): k for k, v in vars(Q).items() if k.isupper() and isinstance(v, str)}


def query_names(receipt: dict) -> list[str]:
    return [QUERY_NAMES.get(c, "?") for c in receipt["cypher"]]


TOOLS = [record_attempt, diagnose_text, next_question, root_cause, probe_frontier, learning_path, recall,
         pick_skill, update_skill, cohorts, keystones, bridges, handoff, claim, propose, decide]
