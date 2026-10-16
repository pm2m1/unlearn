"""Validation for the hand-curated files in data/curated/. Every loader and test goes through here."""

import csv
import json
import re
from fractions import Fraction
from math import gcd, lcm
from pathlib import Path

import networkx as nx

ROOT = Path(__file__).resolve().parents[2]
CURATED = ROOT / "data" / "curated"

# The class topic slice: four Fractions subtopics plus hand-picked prerequisites.
TOPIC = "Fractions"
SUBTOPICS = [
    "Equivalent Fractions",
    "Adding and Subtracting Fractions",
    "Simplifying Fractions",
    "Ordering Fractions",
]
PREREQ_CONSTRUCTS = {
    3378: "Know times tables up to 12 x 12",
    342: "Identify multiples of a number",
    345: "Identify the Lowest Common Multiple of two numbers",
    331: "Identify factors of a number",
    338: "Identify the Highest Common Factor of two numbers",
    164: "Carry out mental divisions when the answer is an integer",
    3193: "Express a division as a fraction",
}


class CurationError(ValueError):
    pass


# --- REQUIRES -----------------------------------------------------------------

def load_requires(path: Path = CURATED / "requires.csv") -> list[dict]:
    with open(path, newline="") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["construct_id"] = int(r["construct_id"])
        r["prereq_id"] = int(r["prereq_id"])
        if r["confidence"] not in {"high", "medium", "low"}:
            raise CurationError(f"bad confidence {r['confidence']!r} on {r['construct_id']}->{r['prereq_id']}")
    check_dag(rows)
    return rows


def requires_graph(rows: list[dict]) -> nx.DiGraph:
    g = nx.DiGraph()
    g.add_edges_from((r["construct_id"], r["prereq_id"]) for r in rows)
    return g


def check_dag(rows: list[dict]) -> None:
    g = requires_graph(rows)
    if not nx.is_directed_acyclic_graph(g):
        raise CurationError(f"REQUIRES has a cycle: {nx.find_cycle(g)}")
    if any(r["construct_id"] == r["prereq_id"] for r in rows):
        raise CurationError("REQUIRES has a self-loop")


# --- Questions ----------------------------------------------------------------
# Each question carries a `check` spec so its maths can be recomputed independently
# of which option is marked correct. Kinds:
#   value      options are numbers; the correct one equals expr, no distractor does
#   simplest   like value, but "correct" also means lowest terms (for simplifying)
#   predicate  options are numbers; only the correct one satisfies pred(x)
#   order      options are comma lists of items; only the correct one is sorted by dir
#   symbol     options are <, >, = (or an operation); only the true relation a ? b is correct
#   statement  options are "X op Y"; only the correct one is true
#   claim      options carry a claim about a vs b in {<, =, >, ?}; only the true one is correct
#   pair       options are "X and Y"; only the correct pair is equal
#   between    options are "a and b" (consecutive integers); only the correct one brackets expr

_NUM = r"-?\d+(?:\.\d+)?"
_FRAC_RE = re.compile(rf"^({_NUM})/(\d+(?:\.\d+)?)$")
_MIXED_RE = re.compile(r"^(-?)(\d+) (\d+)/(\d+)$")
_NUM_RE = re.compile(rf"^{_NUM}$")
_RELATIONS = {"<": lambda a, b: a < b, ">": lambda a, b: a > b, "=": lambda a, b: a == b}


def _ndiv(n: int) -> int:
    return sum(1 for d in range(1, n + 1) if n % d == 0)


_ENV = {"__builtins__": {}, "F": Fraction, "lcm": lcm, "gcd": gcd, "ndiv": _ndiv, "max": max, "min": min}


def evaluate(expr: str) -> Fraction:
    return Fraction(eval(expr, dict(_ENV)))  # expressions are authored in-repo, never user input


def parse_value(text: str) -> Fraction | None:
    t = text.strip()
    if m := _MIXED_RE.match(t):
        sign, whole, num, den = m.groups()
        v = int(whole) + Fraction(int(num), int(den))
        return -v if sign else v
    if m := _FRAC_RE.match(t):
        return Fraction(m.group(1)) / Fraction(m.group(2))
    if _NUM_RE.match(t):
        return Fraction(t)
    return None


def is_simplest(text: str) -> bool:
    t = text.strip()
    if re.fullmatch(r"-?\d+", t):
        return True
    if m := _MIXED_RE.match(t):
        _, _, num, den = m.groups()
        return 0 < int(num) < int(den) and gcd(int(num), int(den)) == 1
    if m := re.fullmatch(r"(-?\d+)/(\d+)", t):
        num, den = int(m.group(1)), int(m.group(2))
        return den > 1 and gcd(abs(num), den) == 1
    return False


def _relation(a: Fraction, b: Fraction) -> str:
    return "<" if a < b else ">" if a > b else "="


def _statement_true(text: str) -> bool:
    m = re.fullmatch(r"\s*(.+?)\s*([<>=])\s*(.+?)\s*", text)
    if not m:
        raise CurationError(f"unparseable statement {text!r}")
    left, op, right = parse_value(m.group(1)), m.group(2), parse_value(m.group(3))
    if left is None or right is None:
        raise CurationError(f"unparseable statement {text!r}")
    return _RELATIONS[op](left, right)


def _pair(text: str) -> tuple[Fraction, Fraction]:
    parts = text.split(" and ")
    vals = [parse_value(p) for p in parts]
    if len(vals) != 2 or None in vals:
        raise CurationError(f"unparseable pair {text!r}")
    return vals[0], vals[1]


def _is_correct(q: dict, opt: dict) -> bool:
    """Recompute from the check spec whether this option is a right answer."""
    c, text = q["check"], opt["text"]
    kind = c["kind"]
    if kind in ("value", "simplest", "predicate"):
        v = parse_value(text)
        if v is None:
            raise CurationError(f"{q['id']}: option {text!r} is not a number")
        if kind == "predicate":
            return bool(eval(c["pred"], dict(_ENV), {"x": v}))
        ok = v == evaluate(c["expr"])
        return ok and (kind == "value" or is_simplest(text))
    if kind == "order":
        items = [s.strip() for s in text.split(",")]
        if sorted(items) != sorted(c["items"]):
            raise CurationError(f"{q['id']}: option {text!r} is not a permutation of {c['items']}")
        target = sorted(c["items"], key=parse_value, reverse=c["dir"] == "desc")
        return items == target
    if kind == "symbol":
        return text.strip() == _relation(evaluate(c["a"]), evaluate(c["b"]))
    if kind == "statement":
        return _statement_true(text)
    if kind == "claim":
        return opt["claim"] == _relation(evaluate(c["a"]), evaluate(c["b"]))
    if kind == "pair":
        a, b = _pair(text)
        return a == b
    if kind == "between":
        lo, hi = _pair(text)
        v = evaluate(c["expr"])
        return lo < v < hi and hi == lo + 1
    raise CurationError(f"{q['id']}: unknown check kind {kind!r}")


def _numbers_in(s: str) -> set[str]:
    return set(re.findall(r"\d+", s))


def verify_question(q: dict, seen_in: dict[int, set[int]] | None = None) -> list[str]:
    """Return a list of problems with one question (empty means it passes)."""
    errs = []
    opts = q.get("options", [])
    keys = [o["key"] for o in opts]
    if len(opts) < 2 or len(set(keys)) != len(keys):
        errs.append("needs 2+ options with unique keys")
    if sum(1 for o in opts if o.get("correct")) != 1:
        errs.append("needs exactly one option marked correct")
    if len({o["text"] for o in opts}) != len(opts):
        errs.append("duplicate option text")
    for o in opts:
        if not o.get("correct") and "misconception_id" not in o:
            errs.append(f"wrong option {o['key']} has no misconception_id")
        if seen_in is not None and not o.get("correct"):
            if o.get("misconception_id") not in seen_in.get(q["construct_id"], set()):
                errs.append(f"option {o['key']}: misconception {o.get('misconception_id')} has no SEEN_IN to {q['construct_id']}")
        try:
            right = _is_correct(q, o)
        except CurationError as e:
            errs.append(str(e))
            continue
        except Exception as e:  # bad expression in the check spec
            errs.append(f"option {o['key']}: check failed: {e}")
            continue
        if o.get("correct") and not right:
            errs.append(f"option {o['key']} {o['text']!r} is marked correct but is wrong")
        if not o.get("correct") and right:
            errs.append(f"distractor {o['key']} {o['text']!r} is actually correct")
    # The check spec must be about the numbers in the question text.
    c = q.get("check", {})
    if not c.get("words"):
        text_nums = _numbers_in(q["text"])
        exprs = [c[k] for k in ("expr", "a", "b") if k in c] + c.get("items", [])
        missing = set().union(*[_numbers_in(e) for e in exprs]) - text_nums if exprs else set()
        if missing:
            errs.append(f"check uses numbers not in the text: {sorted(missing)}")
    return errs


def load_questions(path: Path = CURATED / "questions.json", seen_in: dict[int, set[int]] | None = None) -> list[dict]:
    questions = json.loads(path.read_text())
    ids = [q["id"] for q in questions]
    if len(set(ids)) != len(ids):
        raise CurationError("duplicate question ids")
    problems = {q["id"]: e for q in questions if (e := verify_question(q, seen_in))}
    if problems:
        raise CurationError("questions failed verification:\n" + "\n".join(f"  {k}: {v}" for k, v in problems.items()))
    return questions
