"""The teacher's chat: an LLM tool loop over the Teacher tools, with the receipt check and a template fallback.

The model may only call the tools below (no decide, no Cypher). Every tool row it receives in the turn goes
into the receipt check for its final reply. If no provider is configured, or a provider fails, or the reply
fails the check twice, a template answers from the same tools, chosen by keywords in the message.
"""

import json
import re

from unlearn import llm, tools
from unlearn.agents.base import Agent

MAX_ROUNDS = 4
ROWS_FOR_MODEL = 12  # rows per tool result sent back to the model; the receipt keeps all of them

SPECS = [
    {"name": "cohorts", "description": "Groups of students who share confident misconceptions (WCC).",
     "parameters": {"type": "object", "properties": {}}},
    {"name": "keystones", "description": "The 10 constructs most of the topic depends on (PageRank over REQUIRES).",
     "parameters": {"type": "object", "properties": {}}},
    {"name": "bridges", "description": "Constructs where misconceptions cross topics (betweenness, curriculum graph).",
     "parameters": {"type": "object", "properties": {}}},
    {"name": "recall", "description": "What the tutor remembers about one student.",
     "parameters": {"type": "object", "properties": {"student_id": {"type": "string"}}, "required": ["student_id"]}},
    {"name": "root_cause", "description": "Deepest unmastered prerequisite with misconception evidence for a student on a target construct.",
     "parameters": {"type": "object", "properties": {"student_id": {"type": "string"}, "construct_id": {"type": "integer"}},
                    "required": ["student_id", "construct_id"]}},
    {"name": "pending_proposals", "description": "Proposals waiting for the teacher's approval.",
     "parameters": {"type": "object", "properties": {}}},
    {"name": "propose", "description": "Create a PENDING proposal (regroup needs 2+ students; skip_ahead and assign_practice need construct_id). The teacher approves it in the UI.",
     "parameters": {"type": "object", "properties": {
         "kind": {"type": "string", "enum": sorted(tools.PROPOSAL_KINDS)},
         "student_ids": {"type": "array", "items": {"type": "string"}},
         "construct_id": {"type": "integer"}}, "required": ["kind", "student_ids"]}},
]
TOOL_SPECS = [{"type": "function", "function": s} for s in SPECS]

SYSTEM = (
    "You are the assistant on a maths teacher's dashboard. Answer only from tool results; call tools to get "
    "facts. Copy every construct or misconception name exactly from the tool results and wrap it in double "
    "square brackets, like [[Find the lowest common multiple]]. You can create proposals but never approve "
    "them. At most 120 words."
)


class TeacherChat(Agent):
    name = "Teacher"

    def __init__(self, class_id: str, on_step=None, writer=llm.write):
        super().__init__(class_id, on_step=on_step, writer=writer)
        self.turn_rows: list = []

    # --- tools the model can call ---

    def run_tool(self, task_id: str, name: str, args: dict) -> list:
        c = self.class_id
        if name == "cohorts":
            out = self.call(task_id, tools.cohorts, c)
        elif name == "keystones":
            out = self.call(task_id, tools.keystones, c)
        elif name == "bridges":
            out = self.call(task_id, tools.bridges)
        elif name == "recall":
            out = self.call(task_id, tools.recall, c, str(args["student_id"]))
        elif name == "root_cause":
            out = self.call(task_id, tools.root_cause, c, str(args["student_id"]), int(args["construct_id"]))
        elif name == "pending_proposals":
            out = self.call(task_id, tools.proposals, c, "pending")
        elif name == "propose":
            payload = {"construct_id": int(args["construct_id"])} if args.get("construct_id") is not None else {}
            out = self.call(task_id, tools.propose, c, f"p-chat-{tools.now_ms()}", args["kind"], payload,
                            [str(s) for s in args["student_ids"]])
        else:
            raise ValueError(f"unknown tool {name!r}")
        self.turn_rows.append(out["rows"])
        return out["rows"]

    # --- the turn ---

    def reply(self, message: str) -> dict:
        task_id = f"chat-{tools.now_ms()}"
        attempts = []
        for provider in llm.available():
            try:
                text, problems = self._llm_turn(task_id, provider, message, attempts)
            except Exception as e:  # network, auth, bad tool args: next provider
                llm.note_failure(provider, e)
                attempts.append({"provider": provider.name, "ok": False, "error": f"{type(e).__name__}: {str(e)[:200]}"})
                continue
            if text is not None:
                self._log_llm(task_id, text, provider.name, attempts)
                return {"text": text, "source": provider.name, "attempts": attempts}
            break  # failed the receipt check twice: template
        text = self._template(task_id, message)
        attempts.append({"provider": "template", "ok": True, "problems": []})
        self._log_llm(task_id, text, "template", attempts)
        return {"text": text, "source": "template", "attempts": attempts}

    def _log_llm(self, task_id, text, source, attempts):
        from unlearn.agents.base import Step
        self.on_step(Step(self.name, task_id, "llm:chat", text=text, source=source, rows=attempts))

    def _llm_turn(self, task_id, provider, message, attempts):
        messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": message}]
        checks = 0
        for _ in range(MAX_ROUNDS + 2):
            out = llm.chat_tools(provider, messages, TOOL_SPECS)
            if out["tool_calls"]:
                messages.append({"role": "assistant", "content": out["content"] or None, "tool_calls": [
                    t.get("raw") or {"id": t["id"], "type": "function",
                                     "function": {"name": t["name"], "arguments": json.dumps(t["arguments"])}}
                    for t in out["tool_calls"]]})
                for t in out["tool_calls"]:
                    rows = self.run_tool(task_id, t["name"], t["arguments"])
                    messages.append({"role": "tool", "tool_call_id": t["id"],
                                     "content": json.dumps(rows[:ROWS_FOR_MODEL], default=str)})
                continue
            problems = llm.check_reply(out["content"], self.turn_rows, self.vocabulary()) + llm.malformed(out["content"])
            attempts.append({"provider": provider.name, "model": provider.model, "ok": not problems, "problems": problems})
            if not problems:
                return llm.unmark(out["content"]), []
            checks += 1
            if checks == 2:
                return None, problems
            messages += [{"role": "assistant", "content": out["content"]},
                         {"role": "user", "content": "These names are not in the tool results: " + "; ".join(problems)
                          + ". Rewrite using only names from the tool results, in [[double brackets]]."}]
        return None, ["too many tool rounds"]

    def _template(self, task_id: str, message: str) -> str:
        """No LLM: pick tools by keyword and answer from their rows."""
        m = message.lower()
        students = {r["id"]: r["alias"] for r in tools.class_students(self.class_id)["rows"]}
        named = [sid for sid, alias in students.items()
                 if re.search(rf"\b{re.escape(sid)}\b", m) or (alias and re.search(rf"\b{re.escape(alias.lower())}\b", m))]
        parts = []
        if named:
            for sid in named[:2]:
                rec = self.run_tool(task_id, "recall", {"student_id": sid})
                who = f"{students[sid]} ({sid})"
                parts.append(f"{who} shows: " + "; ".join(f"{r['misconception']} ×{r['times']}" for r in rec[:3])
                             if rec else f"{who} has no confident misconceptions yet.")
        if "cohort" in m or "group" in m or not (named or any(k in m for k in ("keystone", "bridge", "proposal", "pending"))):
            groups = self.run_tool(task_id, "cohorts", {})
            parts.append(f"{len(groups)} cohort{'' if len(groups) == 1 else 's'}: " + "; ".join(", ".join(g["students"]) for g in groups[:4]) + "."
                         if groups else "No cohorts: no two students share a confident misconception yet.")
        if "keystone" in m or "foundation" in m or "important" in m:
            ks = self.run_tool(task_id, "keystones", {})
            parts.append("Keystones: " + "; ".join(k["name"] for k in ks[:3]) + ".")
        if "bridge" in m or "across" in m:
            br = self.run_tool(task_id, "bridges", {})
            parts.append("Bridges across topics: " + "; ".join(b["name"] for b in br[:3]) + ".")
        if "proposal" in m or "pending" in m or "approve" in m:
            ps = self.run_tool(task_id, "pending_proposals", {})
            parts.append(f"{len(ps)} pending proposal(s), first {min(len(ps), 4)}: "
                         + "; ".join(f"{p['kind']} for {', '.join(p['students'])}" for p in ps[:4]) + "."
                         if ps else "No pending proposals.")
        return " ".join(parts)


def chat(class_id: str, message: str, on_step=None) -> dict:
    return TeacherChat(class_id, on_step=on_step).reply(message)
