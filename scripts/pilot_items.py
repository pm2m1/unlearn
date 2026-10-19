"""Write the pilot's question set (data/pilot/items.json) and its review file (docs/pilot/ITEM_REVIEW.md).

    PYTHONPATH=api .venv/bin/python scripts/pilot_items.py

Items are copies of data/curated/questions.json with the pilot edits below applied (the demo's questions are
not changed). Every item is re-verified with the curation checks (maths and SEEN_IN) and the script refuses to
write if any fail. Decisions already in ITEM_REVIEW.md are kept while an item's fingerprint is unchanged; a
changed item goes back to PENDING. The pilot uses only APPROVED items (unlearn/pilot/items.py).
"""

import copy
import json
import re
import sys
from pathlib import Path

import networkx as nx
import pandas as pd

from unlearn.curation import CURATED, is_simplest, load_requires, parse_value, verify_question
from unlearn.pilot import items as P
from unlearn.pilot import wording

ROOT = Path(__file__).resolve().parents[1]

# Check constructs, in the order the check asks them. Each has a session-1 item and a parallel session-2 item.
CHECK = [(425, "q-425-2", "q-425-3"), (427, "q-427-1", "q-427-3"), (433, "q-433-1", "q-433-2"),
         (435, "q-435-1", "q-435-3"), (410, "q-410-1", "q-410-2")]
# Diagnostic pool: the prerequisites of the check constructs, all three items each.
POOL_CONSTRUCTS = [409, 345, 342, 424, 432, 338, 331, 3342, 3378, 164]

# Pilot-only edits. "options" maps an option key to the fields that replace the source option's.
EDITS = {
    "q-164-1": {"text": "96 ÷ 8 = ?"},
    "q-164-2": {"text": "84 ÷ 4 = ?"},
    "q-164-3": {"text": "240 ÷ 40 = ?"},
    "q-3378-1": {"text": "7 × 8 = ?"},
    "q-3378-2": {"text": "? × 6 = 42. What is the missing number?"},
    "q-3378-3": {"text": "48 ÷ 6 = ?"},
    "q-432-1": {"options": {"A": {"text": "1/4"}}},
    "q-432-3": {"options": {"D": {"text": "1/2"}}},
    "q-435-1": {"options": {"D": {"text": "13/15", "misconception_id": 26054,
                                  "why": "Adds instead of subtracting: 2/3 + 1/5 = 13/15."}}},
    "q-3342-3": {"text": "Which of these is equal to 7/3?"},
    "q-409-2": {"text": "Which pair of fractions is equivalent?"},
}

WHY_EDITED = {
    "q-164-1": "÷ for division (Indian textbooks use ÷; \"/\" reads as a fraction).",
    "q-164-2": "÷ for division.",
    "q-164-3": "÷ for division.",
    "q-3378-1": "× for multiplication.",
    "q-3378-2": "× for multiplication.",
    "q-3378-3": "÷ for division.",
    "q-432-1": "Correct option in simplest form (was 2/8), to match \"Give answers in simplest form, unless the question "
               "asks for an equivalent fraction\".",
    "q-432-3": "Correct option in simplest form (was 5/10), same rule.",
    "q-435-1": "Negative distractor -1/2 (24501) replaced by 13/15 (26054, adds instead of subtracting; SEEN_IN 435).",
    "q-3342-3": "Stem said \"Which mixed number\", but two options aren't mixed numbers.",
    "q-409-2": "Grammar: \"Which pair ... is\".",
}

# Equivalence questions whose answer is deliberately not in simplest form.
NOT_SIMPLEST_OK = {"q-409-1"}

FLAGS = {
    "q-409-1": "The answer 8/12 is not in simplest form by design: the question asks for an equivalent fraction, "
               "which the instruction \"Give answers in simplest form, unless the question asks for an equivalent "
               "fraction\" exempts.",
    "q-433-2": "Key is 1/2 (3/6 simplified). Fine with the instruction \"Give answers in simplest form, unless the "
               "question asks for an equivalent fraction\".",
    "q-410-3": "Simplifying a mixed number; option D repeats the question. Fine for Class 7, less sure for Class 6.",
    "q-427-2": "D \"9/15\" tagged 19088: the working (multiplies both numerators by 3) is plausible but unusual.",
    "q-342-3": "\"First multiple of 6\" = 6 matches NCERT; low risk.",
    "q-3378-1": "Only 3 options; 15 and 1 are weak distractors.",
}

SUGGEST = {
    "q-164-1": "APPROVE (your default: ÷ rendering)", "q-164-2": "APPROVE (your default: ÷ rendering)",
    "q-164-3": "APPROVE (your default: ÷ rendering)",
    "q-3378-1": "DROP (your default)", "q-3378-2": "DROP (your default)", "q-3378-3": "DROP (your default)",
    "q-432-1": "APPROVE (your default: simplest form)", "q-432-3": "APPROVE (same rule as q-432-1)",
    "q-435-1": "APPROVE the replacement distractor, or DROP (your default)",
    "q-3342-3": "APPROVE the fixed stem, or DROP (your default)",
    "q-427-2": "Your call (tag on D)",
}


def seen_in_from_csv() -> dict[int, set[int]]:
    m = pd.read_csv(ROOT / "data" / "raw" / "misconception-map.csv")
    return m.groupby("ConstructId").MisconceptionId.apply(set).to_dict()


def construct_names() -> dict[int, str]:
    m = pd.read_csv(ROOT / "data" / "raw" / "construct-map.csv")
    return {int(r.ConstructId): re.sub(r"\s{2,}", " ", r.ConstructName).strip() for r in m.itertuples()}


def misconception_names() -> dict[int, str]:
    m = pd.read_csv(ROOT / "data" / "raw" / "misconception-map.csv")
    return {int(r.MisconceptionId): re.sub(r"\s{2,}", " ", r.MisconceptionName).strip() for r in m.itertuples()}


def apply_edits(q: dict) -> dict:
    q = copy.deepcopy(q)
    edit = EDITS.get(q["id"], {})
    if "text" in edit:
        q["text"] = edit["text"]
    for key, fields in edit.get("options", {}).items():
        opt = next(o for o in q["options"] if o["key"] == key)
        opt.update(fields)
    return q


def build() -> tuple[list[dict], dict[int, str]]:
    source = {q["id"]: q for q in json.loads((CURATED / "questions.json").read_text())}
    plan = [(qid, "S1") for _, qid, _ in CHECK] + [(qid, "S2") for _, _, qid in CHECK]
    check_ids = {qid for qid, _ in plan}
    plan += [(qid, "POOL") for cid, _, _ in CHECK for qid in sorted(source) if source[qid]["construct_id"] == cid
             and qid not in check_ids]
    plan += [(qid, "POOL") for cid in POOL_CONSTRUCTS for qid in sorted(source) if source[qid]["construct_id"] == cid]
    items = []
    for qid, role in plan:
        q = apply_edits(source[qid])
        items.append({"id": qid, "role": role, "construct_id": q["construct_id"], "text": q["text"],
                      "check": q["check"],
                      "options": [{k: v for k, v in o.items() if k in ("key", "text", "correct", "misconception_id",
                                                                         "why", "claim")} for o in q["options"]]})
    # Constructs a student may see by name: the prerequisites a diagnosis can land on.
    g = nx.DiGraph((r["construct_id"], r["prereq_id"]) for r in load_requires())
    roots = set().union(*(nx.descendants(g, cid) for cid, _, _ in CHECK))
    names = construct_names()
    return items, {cid: names[cid] for cid in sorted(roots)}


def check(items: list[dict]) -> list[str]:
    seen_in = seen_in_from_csv()
    errs = []
    for it in items:
        errs += [f"{it['id']}: {e}" for e in verify_question(it, seen_in)]
        right = next(o for o in it["options"] if o.get("correct"))
        if (it["id"] not in NOT_SIMPLEST_OK and parse_value(right["text"]) is not None and "/" in right["text"]
                and not is_simplest(right["text"])):
            errs.append(f"{it['id']}: correct option {right['text']!r} is not in simplest form")
        if len(it["options"]) < 3:
            errs.append(f"{it['id']}: fewer than 3 options")
    return errs


def render(items: list[dict], constructs: dict[int, str], old: dict) -> str:
    mnames, cnames = misconception_names(), construct_names()
    source = {q["id"]: q for q in json.loads((CURATED / "questions.json").read_text())}

    def decision(block_id: str, fp: str) -> str:
        """The block's decision line: kept whole (with any note) while the fingerprint is unchanged."""
        was = old.get(block_id)
        if was and was[0] == fp:
            return was[1]
        return "**Decision:** PENDING"

    out = [
        "# Pilot item review",
        "",
        "Every question and every fixed sentence a pilot student can see is listed here. **The pilot uses an item "
        "only while its decision line reads `APPROVED`**; anything else (`PENDING`, `DROPPED`, `EDIT`) keeps it out. "
        "The pilot also refuses to create a class until the wording block is `APPROVED` and at least one session-1 "
        "and one session-2 check item are.",
        "",
        "- **How to decide:** change `PENDING` after `**Decision:**` to `APPROVED` or `DROPPED`. For a change, write "
        "`EDIT` and a note on the same line; Claude Code applies the edit in `scripts/pilot_items.py` and the item "
        "comes back as `PENDING`. Anything after the decision word on that line is kept when the file is regenerated.",
        "- **Fingerprints:** each block has a fingerprint of exactly what students see (stem, options, key, "
        "misconception tags). If the item changes, the fingerprint changes and an earlier decision no longer counts.",
        "- **Regenerate:** `PYTHONPATH=api .venv/bin/python scripts/pilot_items.py` rewrites this file and keeps "
        "decisions whose fingerprint is unchanged.",
        "- **Source:** copies of `data/curated/questions.json` with pilot-only edits; the demo's questions are not "
        "changed. Every item is re-checked by `verify_question` (maths and SEEN_IN) and the script refuses to write if "
        "one fails. Answer keys were also recomputed by hand in Phase 0.",
        "- **Roles:** **S1** session-1 check, **S2** session-2 check (a different item on the same construct), "
        "**POOL** questions the Diagnoser and Tutor may ask in session 1. Check items are never asked by the "
        "Diagnoser or Tutor.",
        "",
        "## Wording",
        "",
    ]
    wfp = P.wording_fingerprint({str(k): v for k, v in constructs.items()})
    out += [f"### {P.WORDING_ID} · fixed sentences and construct names", "", f"`fingerprint: {wfp}`", "",
            "From `api/unlearn/pilot/wording.py`. **The Hindi is a draft and needs a native speaker's check.**", "",
            "**Assent screen (English, then Hindi):**", ""]
    for lang in ("en", "hi"):
        a = wording.ASSENT[lang]
        out += [f"- **{lang}** {a['title']}"] + [f"  - {line}" for line in a["body"]]
        out += [f"  - Button: {a['yes']}", f"  - Button: {a['no']}", f"  - After \"no\": {a['declined']}"]
    out += ["", "**Other sentences (English only):**", ""]
    out += [f"- `{k}`: {v}" for k, v in wording.TEXT.items()]
    out += ["", "**Construct names a student may see** (after \"Let's practise:\" and in session 2's recall):", ""]
    out += [f"- {cid} {name}" for cid, name in constructs.items()]
    out += ["", "The Tutor's remediation skills are not shown to students: their steps are written as teacher "
            "instructions, so they appear only in the teacher view.", "",
            decision(P.WORDING_ID, wfp), ""]

    def block(it: dict, label: str) -> list[str]:
        fp = P.item_fingerprint(it)
        lines = [f"### {it['id']} · {label} · construct {it['construct_id']} {cnames[it['construct_id']]}", "",
                 f"`fingerprint: {fp}`", "", f"> {it['text']}", ""]
        for o in it["options"]:
            tag = "**correct**" if o.get("correct") else f"{o['misconception_id']} {mnames[o['misconception_id']]}"
            lines.append(f"- {o['key']}. `{o['text']}`: {tag}")
        if it["id"] in EDITS:
            src = source[it["id"]]
            changes = []
            if src["text"] != it["text"]:
                changes.append(f"stem was \"{src['text']}\"")
            for o, so in zip(it["options"], src["options"]):
                if o["text"] != so["text"] or o.get("misconception_id") != so.get("misconception_id"):
                    changes.append(f"{o['key']} was `{so['text']}`" + (
                        f" ({so['misconception_id']})" if so.get("misconception_id") else " (correct)"))
            lines += ["", f"**Pilot edit:** {WHY_EDITED[it['id']]} ({'; '.join(changes)})"]
        if it["id"] in FLAGS:
            lines += ["", f"**Flag:** {FLAGS[it['id']]}"]
        if it["id"] in SUGGEST:
            lines += ["", f"**Suggested:** {SUGGEST[it['id']]}"]
        lines += ["", decision(it["id"], fp), ""]
        return lines

    out += ["## Check items", "", "Session 1 asks the S1 items in this order; session 2 asks the S2 items. "
            "Each pair is on the same construct and shares at least one misconception tag.", ""]
    by_id = {it["id"]: it for it in items}
    for n, (cid, s1, s2) in enumerate(CHECK, 1):
        out += block(by_id[s1], f"S1 #{n}") + block(by_id[s2], f"S2 #{n}")
    out += ["## Diagnostic pool", ""]
    for it in items:
        if it["role"] == "POOL":
            out += block(it, "POOL")
    return "\n".join(out).rstrip() + "\n"


def main() -> int:
    items, constructs = build()
    errs = check(items)
    if errs:
        print("\n".join(errs))
        sys.exit(f"{len(errs)} problems; nothing written")
    P.ITEMS.parent.mkdir(parents=True, exist_ok=True)
    P.ITEMS.write_text(json.dumps({"constructs": {str(k): v for k, v in constructs.items()}, "items": items},
                                  indent=1, ensure_ascii=False) + "\n")
    old = P.decision_lines(P.REVIEW.read_text()) if P.REVIEW.exists() else {}
    P.REVIEW.parent.mkdir(parents=True, exist_ok=True)
    P.REVIEW.write_text(render(items, constructs, old))
    marks = P.decisions(P.REVIEW.read_text())
    approved = sum(1 for k, (_, d) in marks.items() if d == P.APPROVED)
    print(f"wrote {len(items)} items and the review file ({approved} of {len(marks)} blocks APPROVED)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
