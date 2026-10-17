"""Diagnoser: recall, then ask adaptive questions until root_cause is confident, then hand off to the Tutor.

SPEC loop: recall -> (probe_frontier or next_question) -> record_attempt -> root_cause.

Which construct to ask about is a top-down search over the REQUIRES graph, read with learning_path:
  - Start under the target and ask about the closest unasked prerequisite.
  - A correct answer rules that construct out, with everything it depends on (if you can do X you can
    do what X needs).
  - A wrong answer makes it a suspect, and the search continues below it.
  - When nothing is left to ask below the deepest suspect, ask it again to confirm.
Changed from SPEC: the SPEC probes probe_frontier's deepest-first list. On the simulator that spent the
whole 6-question budget on deep constructs the student already knew (REVIEW.md has the numbers).
probe_frontier is still the fallback when there is no suspect and learning_path has nothing left.

Stops when root_cause's top evidence is >= EVIDENCE_MIN and leads the runner-up by >= LEAD_MIN and the
leader is the deepest suspect with nothing unasked below it, or after MAX_QUESTIONS questions.
"""

from unlearn import tools
from unlearn.agents.base import Agent

# root_cause evidence is weighted by SEEN_IN.pct (Phase 3 step 0). Two hits on a prerequisite distractor of
# median weight (pct 66.7) score 1.5 * 0.667 = 1.0, so the SPEC's 1.5 / 0.5 scale by 2/3 to 1.0 / 0.33.
EVIDENCE_MIN = 1.0
LEAD_MIN = 0.33
MAX_QUESTIONS = 6


def confident(rows: list[dict]) -> bool:
    if not rows or rows[0]["evidence"] < EVIDENCE_MIN:
        return False
    runner_up = rows[1]["evidence"] if len(rows) > 1 else 0.0
    return rows[0]["evidence"] - runner_up >= LEAD_MIN


class Diagnoser(Agent):
    name = "Diagnoser"

    def handle(self, task_id: str) -> None:
        c = self.class_id
        ctx = self.call(task_id, tools.task_context, c, task_id)["rows"][0]
        sid, cid, sess = ctx["student_id"], ctx["construct_id"], ctx["session"]

        rec = self.call(task_id, tools.recall, c, sid)
        self.say(task_id, "recall", {"recall": rec["rows"]}, rec["rows"])

        asked, ruled_out, suspects, exhausted = 0, set(), [], set()
        while True:
            rc = self.call(task_id, tools.root_cause, c, sid, cid)
            if asked >= MAX_QUESTIONS:
                break
            picked = self._choose(task_id, sid, cid, rc["rows"], ruled_out, suspects, exhausted)
            if picked is None:
                break
            on, question = picked
            key = self.answerer(sid, question)
            row = self.call(task_id, tools.record_attempt, c, sid, question["id"], key, sess)["rows"][0]
            asked += 1
            if row["correct"]:
                if on in suspects:
                    suspects.remove(on)
                below = self.call(task_id, tools.learning_path, c, sid, on)["rows"]
                ruled_out |= {on} | {r["id"] for r in below}
            elif on not in suspects and on != cid:
                suspects.append(on)
            summary = f"Picked {key} on {question['id']}" + (f": {row['misconception']}" if row["mid"] else " (correct)")
            self.call(task_id, tools.log_event, c, sess, f"{task_id}-a{asked}", "attempt", summary,
                      misconception_id=row["mid"], construct_id=on)

        top = rc["rows"][0] if rc["rows"] else None
        self.say(task_id, "diagnosis", {"root": top}, rc["rows"])
        if top is None:
            self.call(task_id, tools.complete_task, c, task_id)
            return
        self.call(task_id, tools.log_event, c, sess, f"{task_id}-dx", "diagnosis",
                  f"Root cause {top['name']} (evidence {top['evidence']:.2f}) after {asked} questions",
                  construct_id=top["id"])
        self.call(task_id, tools.handoff, c, task_id, sid, "Tutor", "remediate", f"{sess}-remediate")

    def _ask_on(self, task_id: str, sid: str, construct: int):
        rows = self.call(task_id, tools.next_question, self.class_id, sid, construct)["rows"]
        return (construct, rows[0]) if rows else None

    def _choose(self, task_id, sid, cid, rc_rows, ruled_out, suspects, exhausted):
        """The next (construct, question), or None when the diagnosis should stop."""
        c = self.class_id
        while True:
            base = suspects[-1] if suspects else cid
            below = [r for r in self.call(task_id, tools.learning_path, c, sid, base)["rows"]
                     if r["id"] != base and r["id"] not in ruled_out and r["id"] not in exhausted]
            # Closest first: learning_path's depth is the longest path, so depth 1 sits directly under base.
            for r in sorted(below, key=lambda r: (r["depth"], r["id"])):
                if r["id"] in suspects:
                    continue
                got = self._ask_on(task_id, sid, r["id"])
                if got:
                    exhausted.add(r["id"])  # one probe per construct; confirmation happens once it is a suspect
                    return got
                exhausted.add(r["id"])
            if base == cid:
                break
            # Nothing left below the deepest suspect: stop if root_cause agrees, else confirm the suspect.
            if confident(rc_rows) and rc_rows[0]["id"] == base:
                return None
            got = self._ask_on(task_id, sid, base)
            if got:
                return got
            suspects.pop()  # no questions left on it; fall back to the suspect above
        if confident(rc_rows):
            return None
        for r in self.call(task_id, tools.probe_frontier, c, sid, cid)["rows"]:
            if r["id"] not in ruled_out and (got := self._ask_on(task_id, sid, r["id"])):
                return got
        return None
