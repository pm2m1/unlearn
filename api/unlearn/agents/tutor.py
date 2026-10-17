"""Tutor: explain the root cause with the best skill, ask one check question, update the skill.

SPEC steps: root_cause -> learning_path -> pick_skill -> explain -> 1 check question -> update_skill.
Hands off to the Teacher agent (review) when the check is answered wrong and the misconception's
confidence is still above 0.6; otherwise the chain ends here.
"""

from unlearn import tools
from unlearn.agents.base import Agent

ESCALATE_CONFIDENCE = 0.6


class Tutor(Agent):
    name = "Tutor"

    def handle(self, task_id: str) -> None:
        c = self.class_id
        ctx = self.call(task_id, tools.task_context, c, task_id)["rows"][0]
        sid, cid, sess = ctx["student_id"], ctx["construct_id"], ctx["session"]

        rc = self.call(task_id, tools.root_cause, c, sid, cid)["rows"]
        if not rc:
            self.note(task_id, "no root cause left to remediate")
            self.call(task_id, tools.complete_task, c, task_id)
            return
        root = rc[0]
        path = self.call(task_id, tools.learning_path, c, sid, cid, to_id=root["id"])["rows"]
        mis = self.call(task_id, tools.showed_on, c, sid, root["id"])["rows"][0]
        skills = self.call(task_id, tools.pick_skill, c, mis["mid"])["rows"]
        skill = skills[0] if skills else None

        facts = {"root_name": root["name"], "misconception": mis["name"],
                 "skill": skill["skill"] if skill else None, "steps": skill["steps"] if skill else []}
        self.say(task_id, "explain", facts, [rc, path, [mis], skills])

        # One check question: on the root cause if any is left, else the closest construct above it on the
        # root_cause chain (target -> ... -> root), which depends on the root.
        check = None
        for construct in [root["id"]] + list(reversed(root["chain_ids"][:-1])):
            rows = self.call(task_id, tools.next_question, c, sid, construct)["rows"]
            if rows:
                check = (construct, rows[0])
                break
        if check is None:
            self.note(task_id, "no check question left")
            self.call(task_id, tools.complete_task, c, task_id)
            return

        on, question = check
        key = self.answerer(sid, question)
        row = self.call(task_id, tools.record_attempt, c, sid, question["id"], key, sess)["rows"][0]
        ok = bool(row["correct"])
        if skill:
            self.call(task_id, tools.update_skill, c, skill["skill"], ok)
        self.call(task_id, tools.log_event, c, sess, f"{task_id}-check", "remediation",
                  f"Check {question['id']} after {facts['skill'] or 'explanation'}: {'correct' if ok else 'wrong'}",
                  misconception_id=mis["mid"], construct_id=on)

        after = self.call(task_id, tools.showed_on, c, sid, root["id"])["rows"]
        confidence = max((r["confidence"] for r in after), default=0.0)
        if not ok and confidence > ESCALATE_CONFIDENCE:
            self.call(task_id, tools.handoff, c, task_id, sid, "Teacher", "review", f"{sess}-review")
        else:
            self.call(task_id, tools.complete_task, c, task_id)
