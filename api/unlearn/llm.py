"""LLM provider chain, cache and receipt check.

The LLM writes words, never facts. Every reply is checked against the rows the tools returned in the same
turn: any construct or misconception name it mentions must appear in those rows. A reply that fails is
retried once, then replaced by a template built only from the rows, so the demo never fails.
"""

import re
from dataclasses import dataclass, field

MARK = re.compile(r"\[\[(.+?)\]\]")
MIN_NAME_LEN = 15  # shorter vocabulary names are too likely to match ordinary words


@dataclass
class Reply:
    text: str
    source: str                      # provider name, or "template"
    attempts: list[dict] = field(default_factory=list)  # [{provider, ok, problems}] for the receipt


# --- Receipt check ------------------------------------------------------------

def _strings(value) -> set[str]:
    if isinstance(value, str):
        return {value.strip().lower()}
    if isinstance(value, dict):
        return set().union(*map(_strings, value.values())) if value else set()
    if isinstance(value, (list, tuple, set)):
        return set().union(*map(_strings, value)) if value else set()
    return set()


def check_reply(text: str, turn_rows: list, vocabulary: list[str]) -> list[str]:
    """Names in `text` that the turn's tool rows don't back up. Empty means the reply passes.

    Two checks: every [[marked]] name must be a value in the rows, and any known construct or
    misconception name that appears unmarked must also be in the rows.
    """
    allowed = _strings(turn_rows)
    problems = [m.strip() for m in MARK.findall(text) if m.strip().lower() not in allowed]
    plain = MARK.sub(" ", text).lower()
    for name in vocabulary:
        n = name.strip().lower()
        # A short name can sit inside a longer one from the rows ("... in size" in "... in size when ...").
        if len(n) >= MIN_NAME_LEN and n in plain and not any(n in a for a in allowed):
            problems.append(name)
    return problems


def unmark(text: str) -> str:
    return MARK.sub(lambda m: m.group(1), text)


# --- Templates (built only from tool rows) ------------------------------------

def _join(xs: list[str]) -> str:
    xs = [x for x in xs if x]
    return xs[0] if len(xs) == 1 else ", ".join(xs[:-1]) + " and " + xs[-1] if xs else ""


def template(kind: str, facts: dict) -> str:
    if kind == "recall":
        items = facts.get("recall") or []
        if not items:
            return "Welcome! This is our first session, so I'll start with a few questions."
        parts = [f"{r['misconception']} ({r['times']} times)" for r in items[:2]]
        return f"Welcome back. Last time you showed: {_join(parts)}. Let's check whether that has changed."
    if kind == "diagnosis":
        root = facts.get("root")
        if not root:
            return "I didn't find a broken prerequisite in these answers."
        chain = " → ".join(root.get("chain") or [])
        return (f"Your answers point back to a prerequisite: {root['name']}, {root['depth']} step(s) below the topic "
                f"(evidence {root['evidence']:.2f}). Path: {chain}.")
    if kind == "explain":
        steps = facts.get("steps") or []
        lines = [f"The gap is in {facts['root_name']}. Your answers showed: {facts['misconception']}."]
        if facts.get("skill"):
            lines.append(f"Let's try the {facts['skill']} approach:")
            lines += [f"  {i}. {s}" for i, s in enumerate(steps, 1)]
        return "\n".join(lines)
    if kind == "proposal":
        who = _join(facts.get("students") or [])
        if facts["kind"] == "regroup":
            return (f"Proposal: group {who} together; WCC puts them in one cohort linked by shared confident "
                    f"misconceptions. This student's include: {_join(facts.get('shared') or [])}.")
        if facts["kind"] == "assign_practice":
            return f"Proposal: assign {who} practice on {facts['construct_name']}, the diagnosed root cause."
        return f"Proposal: let {who} skip ahead past {facts['construct_name']}."
    raise ValueError(f"no template for {kind!r}")


# --- Entry point --------------------------------------------------------------

def write(kind: str, facts: dict, turn_rows: list, vocabulary: list[str]) -> Reply:
    """Words for one agent turn. Template only for now; the provider chain is added in llm step 3."""
    text = template(kind, facts)
    problems = check_reply(text, turn_rows, vocabulary)
    if problems:  # a template is built from the rows, so this means a bug in the template or the facts
        raise AssertionError(f"template for {kind!r} named facts not in the rows: {problems}")
    return Reply(text, "template", [{"provider": "template", "ok": True, "problems": []}])
