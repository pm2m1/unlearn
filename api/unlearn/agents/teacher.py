"""Teacher agent: look at the class, then write one Proposal for the human teacher.

SPEC steps: cohorts, keystones, bridges -> propose. It can only propose an allowlisted kind; nothing
changes until a human calls decide(approved).
  regroup          the student shares a confident misconception with others (a WCC cohort)
  assign_practice  otherwise: practice on the student's diagnosed root cause
skip_ahead is allowed by the gate but never chosen here: a review task is about a student who is stuck.
"""

from unlearn import tools
from unlearn.agents.base import Agent


class Teacher(Agent):
    name = "Teacher"

    def handle(self, task_id: str) -> None:
        c = self.class_id
        ctx = self.call(task_id, tools.task_context, c, task_id)["rows"][0]
        sid, cid = ctx["student_id"], ctx["construct_id"]

        groups = self.call(task_id, tools.cohorts, c)["rows"]
        keys = self.call(task_id, tools.keystones, c)["rows"]
        bridges = self.call(task_id, tools.bridges)["rows"]
        rc = self.call(task_id, tools.root_cause, c, sid, cid)["rows"]
        root = rc[0] if rc else None

        group = next((g for g in groups if sid in g["ids"]), None)
        pid = f"p-{task_id}"
        if group:
            kind, students = "regroup", sorted(group["ids"])
            aliases = group["students"]
            shared = self.call(task_id, tools.recall, c, sid)["rows"]
            facts = {"kind": kind, "students": aliases, "shared": [r["misconception"] for r in shared[:2]]}
            payload = {"group_id": f"g-{task_id}", "construct_id": root["id"] if root else None}
            turn = [groups, shared]
        else:
            if root is None:
                self.note(task_id, "no cohort and no root cause: nothing to propose")
                self.call(task_id, tools.complete_task, c, task_id)
                return
            kind, students = "assign_practice", [sid]
            facts = {"kind": kind, "students": [sid], "construct_name": root["name"]}
            payload = {"construct_id": root["id"]}
            turn = [rc]
        # Don't stack duplicates: the same kind on the same construct for the same students is already waiting.
        pending = self.call(task_id, tools.proposals, c, "pending")["rows"]
        if any(p["kind"] == kind and sorted(p["students"]) == students
               and p["payload"].get("construct_id") == payload.get("construct_id") for p in pending):
            self.note(task_id, f"an identical {kind} proposal is already pending")
            self.call(task_id, tools.complete_task, c, task_id)
            return
        payload["reason"] = self.say(task_id, "proposal", facts, turn + [keys, bridges])
        self.call(task_id, tools.propose, c, pid, kind, payload, students)
        self.call(task_id, tools.complete_task, c, task_id)
