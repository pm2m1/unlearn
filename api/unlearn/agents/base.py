"""What every agent shares: calling tools with a trace, and writing words through the LLM chain.

Agents never write Cypher. They call the fixed tools in unlearn.tools, decide the next step from the rows
those tools return, and record each call as a Step so a CLI or UI can print the receipts.
"""

from dataclasses import dataclass, field
from typing import Callable

from unlearn import llm, tools

# answerer(student_id, question) -> option key. The question dict has id, text and options [{key, text}].
Answerer = Callable[[str, dict], str]
# Interactive agents (Diagnoser, Tutor) run one step per call: begin(task_id), then answer(task_id, ...) until
# the returned dict's "kind" is no longer a question. Nothing is held in memory between steps.


@dataclass
class Step:
    agent: str
    task_id: str
    tool: str                       # tool name, "llm:<kind>" for a reply, or "note"
    queries: list[str] = field(default_factory=list)
    cypher: list[str] = field(default_factory=list)
    params: list[dict] = field(default_factory=list)
    node_ids: list[dict] = field(default_factory=list)
    rows: list = field(default_factory=list)
    text: str = ""
    source: str = ""                # for llm steps: which provider wrote the text


class Agent:
    name = ""

    def __init__(self, class_id: str, answerer: Answerer | None = None,
                 on_step: Callable[[Step], None] | None = None, writer=llm.write):
        self.class_id = class_id
        self.answerer = answerer
        self.on_step = on_step or (lambda step: None)
        self.writer = writer
        self._vocabulary = None

    # --- tools ---

    def call(self, task_id: str, fn, *args, **kwargs) -> dict:
        out = fn(*args, **kwargs)
        self.on_step(Step(self.name, task_id, fn.__name__, tools.query_names(out), out["cypher"], out["params"],
                          out["node_ids"], out["rows"]))
        return out

    def note(self, task_id: str, text: str) -> None:
        self.on_step(Step(self.name, task_id, "note", text=text))

    # --- words ---

    def vocabulary(self) -> list[str]:
        if self._vocabulary is None:
            self._vocabulary = [r["name"] for r in tools.name_vocabulary(self.class_id)["rows"] if r["name"]]
        return self._vocabulary

    def say(self, task_id: str, kind: str, facts: dict, turn_rows: list) -> str:
        reply = self.writer(kind, facts, turn_rows, self.vocabulary())
        self.on_step(Step(self.name, task_id, f"llm:{kind}", text=reply.text, source=reply.source,
                          rows=reply.attempts))
        return reply.text

    # --- tasks ---

    def context(self, task_id: str) -> dict:
        return self.call(task_id, tools.task_context, self.class_id, task_id)["rows"][0]

    def handle(self, task_id: str) -> None:
        raise NotImplementedError


class StepError(ValueError):
    """The request doesn't fit the task's state (wrong question, nothing pending, task not open)."""
