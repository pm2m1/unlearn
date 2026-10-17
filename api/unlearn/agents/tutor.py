"""Tutor: explain the root cause with the best skill, ask one check question, update the skill.

Steppable: begin(task_id) explains and returns the check question; answer(task_id, ...) records the check,
updates the skill and hands off or ends the chain. What was taught (skill, misconception, root) is stored on
the Task between the two steps.

SPEC steps: recall -> root_cause -> learning_path -> pick_skill -> explain -> 1 check question -> update_skill.
Hands off to the Teacher agent (review) when the check is answered wrong and the misconception's
confidence is still above 0.6; otherwise the chain ends here.
"""

from unlearn import tools
from unlearn.agents.base import Agent, StepError

ESCALATE_CONFIDENCE = 0.6


class Tutor(Agent):
    name = "Tutor"

    def begin(self, task_id: str) -> dict:
        c = self.class_id
        ctx = self.context(task_id)
        sid, cid, sess = ctx["student_id"], ctx["construct_id"], ctx["session"]

        rec = self.call(task_id, tools.recall, c, sid)["rows"]
        rc = self.call(task_id, tools.root_cause, c, sid, cid)["rows"]
        if not rc:
            self.note(task_id, "no root cause left to remediate")
            self.call(task_id, tools.complete_task, c, task_id)
            return {"kind": "done", "task_id": task_id, "recall": rec, "explanation": None}
        root = rc[0]
        path = self.call(task_id, tools.learning_path, c, sid, cid, to_id=root["id"])["rows"]
        mis = self.call(task_id, tools.showed_on, c, sid, root["id"])["rows"][0]
        skills = self.call(task_id, tools.pick_skill, c, mis["mid"])["rows"]
        skill = skills[0] if skills else None

        facts = {"root_name": root["name"], "misconception": mis["name"],
                 "skill": skill["skill"] if skill else None, "steps": skill["steps"] if skill else []}
        explanation = self.say(task_id, "explain", facts, [rc, path, [mis], skills])
        out = {"task_id": task_id, "recall": rec, "root": root, "path": path, "misconception": mis,
               "skill": skill, "explanation": explanation}

        # One check question: on the root cause if one is left this session, else the closest construct above
        # it on the root_cause chain (target -> ... -> root), which depends on the root.
        for construct in [root["id"]] + list(reversed(root["chain_ids"][:-1])):
            rows = self.call(task_id, tools.next_question, c, sid, construct, sess)["rows"]
            if rows:
                self.call(task_id, tools.set_tutor_plan, c, task_id, facts["skill"], mis["mid"], root["id"])
                self.call(task_id, tools.set_pending, c, task_id, rows[0]["id"], construct)
                return {**out, "kind": "check", "question": rows[0], "construct_id": construct}
        self.note(task_id, "no check question left")
        self.call(task_id, tools.complete_task, c, task_id)
        return {**out, "kind": "done"}

    def answer(self, task_id: str, question_id: str, key: str, explanation: str | None = None) -> dict:
        c = self.class_id
        ctx = self.context(task_id)
        if ctx["state"] != "working" or ctx["pending_qid"] is None:
            raise StepError(f"task {task_id} is not waiting for an answer")
        if question_id != ctx["pending_qid"]:
            raise StepError(f"task {task_id} is waiting for {ctx['pending_qid']}, not {question_id}")
        sid, sess, on = ctx["student_id"], ctx["session"], ctx["pending_cid"]
        row = self.call(task_id, tools.record_attempt, c, sid, question_id, key, sess)["rows"][0]
        ok = bool(row["correct"])
        self.call(task_id, tools.set_pending, c, task_id, None, None)
        if ctx["skill"]:
            self.call(task_id, tools.update_skill, c, ctx["skill"], ok)
        self.call(task_id, tools.log_event, c, sess, f"{task_id}-check", "remediation",
                  f"Check {question_id} after {ctx['skill'] or 'explanation'}: {'correct' if ok else 'wrong'}",
                  misconception_id=ctx["mid"], construct_id=on)

        after = self.call(task_id, tools.showed_on, c, sid, ctx["root_id"])["rows"]
        confidence = max((r["confidence"] for r in after), default=0.0)
        escalated = not ok and confidence > ESCALATE_CONFIDENCE
        if escalated:
            nxt = self.call(task_id, tools.handoff, c, task_id, sid, "Teacher", "review", f"{sess}-review")
            next_task = nxt["rows"][0]["id"]
        else:
            self.call(task_id, tools.complete_task, c, task_id)
            next_task = None
        return {"kind": "done", "task_id": task_id, "answer": {
            "question_id": question_id, "key": key, "correct": ok, "misconception": row["misconception"]},
            "confidence": confidence, "escalated": escalated, "next_task": next_task}
