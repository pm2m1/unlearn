"""Record the Teacher chat's example answers for the live demo (deploy/recorded_chat.json).

    OLLAMA_BASE_URL=http://localhost:11434/v1 GEMINI_API_KEY= python deploy/record_chat.py

Run it against a FalkorDB holding the Render image's baked graphs (the dump.rdb deploy/Dockerfile.render
builds), so class_demo is in the state a fresh live instance starts in. Each example question goes through the
real chat with the local model only; a reply is kept only if the model wrote it and it passed the receipt check.
The file stores the tool calls and a fingerprint of their rows: the live app serves a recorded answer only while
re-running those calls gives the same rows (api/unlearn/agents/teacher_chat.py), so it can't go stale.
"""

import json
import time
from pathlib import Path

from unlearn import llm
from unlearn.agents.teacher_chat import TeacherChat, fingerprint

OUT = Path(__file__).resolve().parent / "recorded_chat.json"
CLASS_ID = "demo"
QUESTIONS = ["Which cohorts do I have?", "What do you remember about Rosa?", "Which skill should I teach first?",
             "Why is Ben struggling?"]


class Recorder(TeacherChat):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.calls, self.rows = [], []

    def run_tool(self, task_id, name, args):
        rows = super().run_tool(task_id, name, args)
        self.calls.append([name, args])
        self.rows.append(rows)
        return rows


def main() -> int:
    providers = llm.available()
    assert [p.name for p in providers] == ["ollama"], f"run with the local model only, got {[p.name for p in providers]}"
    answers = []
    for q in QUESTIONS:
        chat = Recorder(CLASS_ID)
        out = chat.reply(q)
        if out["source"] != "ollama":
            print(f"SKIPPED {q!r}: answered by {out['source']} ({out['attempts']})")
            continue
        answers.append({"class_id": CLASS_ID, "question": q, "tools": chat.calls,
                        "fingerprint": fingerprint(chat.calls, chat.rows), "text": out["text"]})
        print(f"{q} -> {[c[0] for c in chat.calls]}\n  {out['text'][:200]}")
    OUT.write_text(json.dumps({"model": f"{providers[0].model} (local, Ollama)", "recorded_on": time.strftime("%Y-%m-%d"),
                               "answers": answers}, indent=2) + "\n")
    print(f"wrote {len(answers)} answers to {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
