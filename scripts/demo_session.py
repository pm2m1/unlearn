"""Run one full Diagnoser -> Tutor -> Teacher session for a simulated student and print every step.

    python scripts/demo_session.py --class demo --student s01             # session 1 (resets the student)
    python scripts/demo_session.py --class demo --student s01 --session 2 # session 2 opens with recall

Each step prints the tool, the named queries it ran (from queries.py) and the node path in its receipt.
The student is the seeded rule-based simulator; its planted state is printed first as ground truth, and
the agents never see it.
"""

import argparse
import sys

from eval.simulator import Simulator
from unlearn import tools as T
from unlearn.agents.runner import run_session_sync

PLUMBING = {"task_context", "log_event", "complete_task", "showed_on", "name_vocabulary"}


def node_path(node_ids: list[dict], limit: int = 8) -> str:
    parts = [f"{n['label']}:{n['id']}" for n in node_ids[:limit]]
    return " → ".join(parts) + (" …" if len(node_ids) > limit else "")


def detail(step) -> str:
    rows, tool = step.rows, step.tool
    if tool == "recall":
        return "; ".join(f"{r['misconception']} ×{r['times']}" for r in rows) or "nothing remembered yet"
    if tool == "next_question" and rows:
        return f"{rows[0]['id']}: {rows[0]['text']}"
    if tool == "record_attempt":
        r = rows[0]
        return f"picked {step.args_key} → " + ("correct" if r["correct"] else f"wrong: {r['misconception']}") + \
            (f" (mastered {r['mastered']})" if r.get("mastered") else "")
    if tool == "root_cause":
        if not rows:
            return "no evidence yet"
        return "; ".join(f"{r['id']} {r['name']} ev={r['evidence']:.2f} depth={r['depth']}" for r in rows)
    if tool in ("probe_frontier", "learning_path"):
        return ", ".join(f"{r['id']}(d{r['depth']})" for r in rows) or "none"
    if tool == "pick_skill":
        return rows[0]["skill"] if rows else "no skill"
    if tool == "update_skill":
        return f"{rows[0]['skill']} rate={rows[0]['rate']:.2f} uses={rows[0]['uses']}"
    if tool == "cohorts":
        return "; ".join(f"[{', '.join(r['students'])}]" for r in rows) or "no cohorts"
    if tool == "keystones":
        return ", ".join(str(r["id"]) for r in rows[:5])
    if tool == "bridges":
        return f"{len(rows)} bridge constructs on curriculum"
    if tool in ("handoff", "propose"):
        return rows[0]["id"] if rows else ""
    return ""


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--class", dest="class_id", default="demo")
    ap.add_argument("--student", default="s01")
    ap.add_argument("--session", type=int, default=1, help="1 resets the student first; 2+ continues")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--verbose", action="store_true", help="also print plumbing steps")
    a = ap.parse_args(argv)

    sim = Simulator(seed=a.seed)
    student = sim.student(a.student)
    if a.session == 1:
        T.reset_student(a.class_id, a.student)
    elif not T.sessions(a.class_id, a.student)["rows"]:
        print(f"{a.student} has no earlier session: run --session 1 first", file=sys.stderr)
        return 2

    print(f"== class_{a.class_id} · student {a.student} · session {a.session} · seed {a.seed}")
    print(f"   simulator ground truth (hidden from agents): root cause {student.root_cause}, "
          f"misconceptions {student.misconceptions}, target construct {student.target}\n")

    last_key = {}

    def answer(sid, question):
        key = student.answer(question)
        last_key["key"] = key
        return key

    def show(step):
        if step.tool in PLUMBING and not a.verbose:
            return
        if step.tool.startswith("llm:"):
            print(f"  [{step.agent}] says ({step.source}):")
            for line in step.text.splitlines():
                print(f"      {line}")
            return
        if step.tool == "note":
            print(f"  [{step.agent}] note: {step.text}")
            return
        step.args_key = last_key.get("key")
        print(f"  [{step.agent}] {step.tool}  {', '.join(step.queries)}")
        print(f"      path: {node_path(step.node_ids)}")
        if d := detail(step):
            print(f"      {d}")

    res = run_session_sync(a.class_id, a.student, student.target, answer, on_step=show,
                           session_id=f"{a.student}-s{a.session}-{T.now_ms()}")
    print(f"\n== task chain (session n={res.session_n}):")
    for t in res.chain:
        print(f"   {t['step']}. {t['agent']:<9} {t['kind']:<9} {t['state']}  {t['id']}")
    pending = [p for p in T.proposals(a.class_id)["rows"] if a.student in p["students"]]
    for p in pending:
        print(f"   pending proposal {p['id']}: {p['kind']} for {', '.join(p['students'])} (needs teacher approval)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
