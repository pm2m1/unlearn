"""Diagnoser: recall, then ask adaptive questions until root_cause is confident, then hand off to the Tutor.

Steppable: begin(task_id) opens the diagnosis and returns the first question; answer(task_id, ...) records
one answer and returns the next question or the diagnosis. Nothing is kept in memory between steps. The
question being waited on is stored on the Task, and the search state is rebuilt each step from this
session's ATTEMPTED edges (session_state).

SPEC loop: recall -> (choose a construct) -> next_question -> record_attempt -> root_cause.

Which construct to ask about is a top-down search over the REQUIRES graph, read with learning_path:
  - Start under the target and ask about the closest prerequisite not yet asked this session.
  - A correct answer rules that construct out, with everything it depends on (if you can do X you can
    do what X needs).
  - A wrong answer makes it a suspect, and the search continues below it.
  - When nothing is left to ask below the deepest suspect, ask it again to confirm.
probe_frontier is the fallback when there is no suspect and learning_path has nothing left.

Stops when root_cause's top evidence is >= EVIDENCE_MIN and leads the runner-up by >= LEAD_MIN and the
leader is the deepest suspect with nothing unasked below it, or after MAX_QUESTIONS questions.
"""

from unlearn import tools
from unlearn.agents.base import Agent, StepError

# root_cause evidence is weighted by SEEN_IN.w (share of the misconception's pct within the slice). The median
# prerequisite distractor has w = 1.0, so two hits score 1.5 * 1.0 = 1.5: the SPEC's own 1.5 / 0.5 bar again.
EVIDENCE_MIN = 1.5
LEAD_MIN = 0.5
MAX_QUESTIONS = 6


def confident(rows: list[dict]) -> bool:
    if not rows or rows[0]["evidence"] < EVIDENCE_MIN:
        return False
    runner_up = rows[1]["evidence"] if len(rows) > 1 else 0.0
    return rows[0]["evidence"] - runner_up >= LEAD_MIN


class Diagnoser(Agent):
    name = "Diagnoser"

    # --- steps ---

    def begin(self, task_id: str) -> dict:
        """Open the diagnosis: recall what we remember, then pick the first question."""
        ctx = self.context(task_id)
        rec = self.call(task_id, tools.recall, self.class_id, ctx["student_id"])
        greeting = self.say(task_id, "recall", {"recall": rec["rows"], "session_n": ctx["session_n"]}, rec["rows"])
        return {**self._advance(task_id, ctx), "recall": rec["rows"], "greeting": greeting}

    def answer(self, task_id: str, question_id: str, key: str, explanation: str | None = None) -> dict:
        """Record the answer to the pending question, then return the next question or the diagnosis."""
        c = self.class_id
        ctx = self.context(task_id)
        if ctx["state"] != "working" or ctx["pending_qid"] is None:
            raise StepError(f"task {task_id} is not waiting for an answer")
        if question_id != ctx["pending_qid"]:
            raise StepError(f"task {task_id} is waiting for {ctx['pending_qid']}, not {question_id}")
        sid, sess, on = ctx["student_id"], ctx["session"], ctx["pending_cid"]
        row = self.call(task_id, tools.record_attempt, c, sid, question_id, key, sess)["rows"][0]
        asked = len(self.call(task_id, tools.session_state, c, sid, sess)["rows"][0]["attempts"])
        summary = f"Picked {key} on {question_id}" + (f": {row['misconception']}" if row["mid"] else " (correct)")
        self.call(task_id, tools.log_event, c, sess, f"{task_id}-a{asked}", "attempt", summary,
                  misconception_id=row["mid"], construct_id=on)
        heard = None
        if explanation and explanation.strip():
            # Free text is mapped to this construct's misconceptions and logged; it doesn't add SHOWED evidence.
            heard = self.call(task_id, tools.diagnose_text, c, on, explanation.strip())["rows"]
            if heard:
                self.call(task_id, tools.log_event, c, sess, f"{task_id}-x{asked}", "explanation",
                          f"Explanation on {question_id} closest to: {heard[0]['name']}",
                          misconception_id=heard[0]["id"], construct_id=on)
        self.call(task_id, tools.set_pending, c, task_id, None, None)
        out = self._advance(task_id, ctx)
        return {**out, "answer": {"question_id": question_id, "key": key, "correct": bool(row["correct"]),
                                  "misconception": row["misconception"], "mastered": row["mastered"]},
                "explanation_matches": heard}

    # --- internals ---

    def _advance(self, task_id: str, ctx: dict) -> dict:
        """Ask the next question (stored as pending on the task), or finish with the diagnosis."""
        c, sid, cid, sess = self.class_id, ctx["student_id"], ctx["construct_id"], ctx["session"]
        rc = self.call(task_id, tools.root_cause, c, sid, cid)
        state = self.call(task_id, tools.session_state, c, sid, sess)["rows"][0]
        asked = len(state["attempts"])
        picked = None
        if asked < MAX_QUESTIONS:
            suspects = []
            for a in state["attempts"]:
                if a["correct"]:
                    if a["construct_id"] in suspects:
                        suspects.remove(a["construct_id"])
                elif a["construct_id"] not in suspects and a["construct_id"] != cid:
                    suspects.append(a["construct_id"])
            probed = {a["construct_id"] for a in state["attempts"]}
            picked = self._choose(task_id, sid, cid, sess, rc["rows"], set(state["ruled_out"]), suspects, probed)
        if picked:
            on, question = picked
            self.call(task_id, tools.set_pending, c, task_id, question["id"], on)
            return {"kind": "question", "task_id": task_id, "question": question, "construct_id": on, "asked": asked}
        return self._finish(task_id, ctx, rc["rows"], asked)

    def _finish(self, task_id: str, ctx: dict, rc_rows: list[dict], asked: int) -> dict:
        c, sid, sess = self.class_id, ctx["student_id"], ctx["session"]
        top = rc_rows[0] if rc_rows else None
        message = self.say(task_id, "diagnosis", {"root": top}, rc_rows)
        if top is None:
            self.call(task_id, tools.complete_task, c, task_id)
            return {"kind": "diagnosis", "task_id": task_id, "root": None, "candidates": [], "message": message,
                    "asked": asked, "next_task": None}
        self.call(task_id, tools.log_event, c, sess, f"{task_id}-dx", "diagnosis",
                  f"Root cause {top['name']} (evidence {top['evidence']:.2f}) after {asked} questions",
                  construct_id=top["id"])
        nxt = self.call(task_id, tools.handoff, c, task_id, sid, "Tutor", "remediate", f"{sess}-remediate")
        return {"kind": "diagnosis", "task_id": task_id, "root": top, "candidates": rc_rows, "message": message,
                "asked": asked, "next_task": nxt["rows"][0]["id"]}

    def _ask_on(self, task_id: str, sid: str, construct: int, sess: str):
        rows = self.call(task_id, tools.next_question, self.class_id, sid, construct, sess)["rows"]
        return (construct, rows[0]) if rows else None

    def _choose(self, task_id, sid, cid, sess, rc_rows, ruled_out, suspects, probed):
        """The next (construct, question), or None when the diagnosis should stop."""
        c = self.class_id
        suspects, tried = list(suspects), set()
        while True:
            base = suspects[-1] if suspects else cid
            below = [r for r in self.call(task_id, tools.learning_path, c, sid, base)["rows"]
                     if r["id"] != base and r["id"] not in ruled_out and r["id"] not in probed and r["id"] not in tried]
            # Closest first: learning_path's depth is the longest path, so depth 1 sits directly under base.
            for r in sorted(below, key=lambda r: (r["depth"], r["id"])):
                if r["id"] in suspects:
                    continue
                tried.add(r["id"])
                if got := self._ask_on(task_id, sid, r["id"], sess):
                    return got
            if base == cid:
                break
            # Nothing left below the deepest suspect: stop if root_cause agrees, else confirm the suspect.
            if confident(rc_rows) and rc_rows[0]["id"] == base:
                return None
            if got := self._ask_on(task_id, sid, base, sess):
                return got
            suspects.pop()  # no questions left on it this session; fall back to the suspect above
        if confident(rc_rows):
            return None
        for r in self.call(task_id, tools.probe_frontier, c, sid, cid)["rows"]:
            if r["id"] not in ruled_out and (got := self._ask_on(task_id, sid, r["id"], sess)):
                return got
        return None
