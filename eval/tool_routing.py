"""Tool routing for the Teacher chat: does the model pick the right tools for a teacher's question?

    OLLAMA_BASE_URL=http://localhost:11434/v1 GEMINI_API_KEY= python eval/tool_routing.py   # tool_routing.json

eval/tool_routing_questions.json has 30 dev and 10 held-out questions, each with the exact set of chat tools
that should answer it. Each question goes through the real chat (agents/teacher_chat.py) with the local model
only, on a scratch copy of class_demo (propose writes). Only the tools the model chose count: if its reply fails
the receipt check and the template answers, the template's keyword-picked tools are not counted.
  exact      the set of tools called equals the expected set
  covers     every expected tool was called (extra calls allowed)
Nothing was tuned on the dev set, so both sets are plain test sets.
"""

import json
import time
from pathlib import Path

from unlearn import llm
from unlearn.agents.teacher_chat import TeacherChat
from unlearn.db import delete_graph, recreate_graph

HERE = Path(__file__).resolve().parent
OUT = HERE / "results" / "tool_routing.json"
CLASS_ID = "tool_routing"


class Routed(TeacherChat):
    """Records the tools the model calls; stops recording once the template takes over."""
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.called, self.by_model = [], True

    def run_tool(self, task_id, name, args):
        if self.by_model:
            self.called.append(name)
        return super().run_tool(task_id, name, args)

    def _template(self, task_id, message):
        self.by_model = False
        return super()._template(task_id, message)


def run_set(items: list[dict]) -> dict:
    rows = []
    for it in items:
        chat, t0 = Routed(CLASS_ID), time.time()
        try:
            out = chat.reply(it["q"])
            source, error = out["source"], None
        except Exception as e:  # count a crash as a miss, and say so
            source, error = "error", f"{type(e).__name__}: {str(e)[:160]}"
        called = sorted(set(chat.called))
        rows.append({"q": it["q"], "expected": sorted(it["tools"]), "called": called, "source": source,
                     "exact": called == sorted(it["tools"]), "covers": set(it["tools"]) <= set(called),
                     "seconds": round(time.time() - t0, 1), **({"error": error} if error else {})})
        print(f"{'OK  ' if rows[-1]['exact'] else 'MISS'} {it['q']}  expected {rows[-1]['expected']}, called {called} ({source})")
    n = len(rows)
    return {"n": n, "exact": sum(r["exact"] for r in rows), "covers": sum(r["covers"] for r in rows),
            "exact_rate": round(sum(r["exact"] for r in rows) / n, 3), "covers_rate": round(sum(r["covers"] for r in rows) / n, 3),
            "rows": rows}


def main() -> int:
    providers = llm.available()
    assert [p.name for p in providers] == ["ollama"], f"run with the local model only, got {[p.name for p in providers]}"
    qs = json.loads((HERE / "tool_routing_questions.json").read_text())
    recreate_graph("class_demo", f"class_{CLASS_ID}")
    try:
        result = {"model": f"{providers[0].model} (local, Ollama)", "method": __doc__.split("\n\n")[1].strip(),
                  "dev": run_set(qs["dev"]), "held_out": run_set(qs["held_out"])}
    finally:
        delete_graph(f"class_{CLASS_ID}")
    OUT.write_text(json.dumps(result, indent=2) + "\n")
    for k in ("dev", "held_out"):
        r = result[k]
        print(f"{k}: exact {r['exact']}/{r['n']} ({r['exact_rate']:.0%}), covers {r['covers']}/{r['n']} ({r['covers_rate']:.0%})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
