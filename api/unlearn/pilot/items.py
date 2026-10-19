"""The pilot's question set: data/pilot/items.json, used only where docs/pilot/ITEM_REVIEW.md says APPROVED.

Every reviewable block in the review file carries a fingerprint of exactly what students would see. A decision
counts only while its fingerprint still matches items.json (or the wording), so editing an item after it was
approved takes it out of the pilot until it is reviewed again. scripts/pilot_items.py writes both files.
"""

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from unlearn.pilot import wording

ROOT = Path(__file__).resolve().parents[3]
ITEMS = ROOT / "data" / "pilot" / "items.json"
REVIEW = ROOT / "docs" / "pilot" / "ITEM_REVIEW.md"
ROLES = ("S1", "S2", "POOL")
APPROVED = "APPROVED"
WORDING_ID = "wording"

_BLOCK = re.compile(r"^### (\S+)[^\n]*\n(.*?)(?=^### |\Z)", re.M | re.S)
_FP = re.compile(r"`fingerprint: ([0-9a-f]+)`")
_DECISION = re.compile(r"^\*\*Decision:\*\*\s*([A-Za-z]+)", re.M)


def fingerprint(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:10]


def student_view(item: dict) -> dict:
    """What a student sees of an item, plus what the log records about each option."""
    return {"id": item["id"], "role": item["role"], "text": item["text"],
            "options": [{"key": o["key"], "text": o["text"], "correct": bool(o.get("correct")),
                         "misconception_id": o.get("misconception_id")} for o in item["options"]]}


def item_fingerprint(item: dict) -> str:
    return fingerprint(student_view(item))


def wording_fingerprint(constructs: dict) -> str:
    return fingerprint({"wording": wording.bundle(), "constructs": constructs})


def decisions(text: str) -> dict[str, tuple[str | None, str]]:
    """{block id: (fingerprint, decision word)} from the review file."""
    out = {}
    for m in _BLOCK.finditer(text):
        fp, dec = _FP.search(m.group(2)), _DECISION.search(m.group(2))
        out[m.group(1)] = (fp.group(1) if fp else None, dec.group(1).upper() if dec else "PENDING")
    return out


@dataclass
class ItemSet:
    items: dict[str, dict] = field(default_factory=dict)       # approved items by id
    check: dict[int, list[str]] = field(default_factory=dict)  # session -> approved check item ids, in order
    pool: list[str] = field(default_factory=list)
    constructs: dict[int, str] = field(default_factory=dict)   # construct names a student may see
    wording_approved: bool = False

    def digest(self) -> str:
        """Identifies the approved set: a pilot class is tied to the set it was created with."""
        return fingerprint({"items": sorted((i, item_fingerprint(x)) for i, x in self.items.items()),
                            "wording": self.wording_approved})

    def counts(self) -> dict:
        return {"S1": len(self.check.get(1, [])), "S2": len(self.check.get(2, [])), "POOL": len(self.pool)}

    def usable(self) -> str | None:
        """Why a pilot class can't run on this set, or None."""
        if not self.wording_approved:
            return "the pilot wording is not approved in ITEM_REVIEW.md"
        if not self.check.get(1) or not self.check.get(2):
            return "no approved check items for session 1 and session 2 in ITEM_REVIEW.md"
        return None

    def option(self, qid: str, key: str) -> dict | None:
        return next((o for o in self.items[qid]["options"] if o["key"] == key), None) if qid in self.items else None


def load(items_path: Path = ITEMS, review_path: Path = REVIEW) -> ItemSet:
    data = json.loads(items_path.read_text())
    marks = decisions(review_path.read_text()) if review_path.exists() else {}
    constructs = {int(k): v for k, v in data["constructs"].items()}
    out = ItemSet(constructs=constructs, check={1: [], 2: []})
    fp, dec = marks.get(WORDING_ID, (None, "PENDING"))
    out.wording_approved = dec == APPROVED and fp == wording_fingerprint(data["constructs"])
    for item in data["items"]:
        fp, dec = marks.get(item["id"], (None, "PENDING"))
        if dec != APPROVED or fp != item_fingerprint(item):
            continue
        out.items[item["id"]] = item
        if item["role"] == "POOL":
            out.pool.append(item["id"])
        else:
            out.check[1 if item["role"] == "S1" else 2].append(item["id"])
    return out
