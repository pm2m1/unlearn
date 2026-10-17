"""A bounded in-process store of receipts, keyed by receipt id, for GET /receipts/{rid}.

A receipt is one agent Step: the tool, the named queries, the Cypher, the params, the rows and the node ids.
The store keeps the newest MAX_RECEIPTS and drops the oldest, so memory stays flat on a long-running demo.
Receipts are a view for the UI; nothing reads them back to make a decision.
"""

import itertools
import threading
import time
from collections import OrderedDict
from dataclasses import asdict

MAX_RECEIPTS = 5000

_lock = threading.Lock()
_store: "OrderedDict[str, dict]" = OrderedDict()
_ids = itertools.count(1)
_prefix = f"{int(time.time()) % 100000:05d}"


def add(step) -> str:
    rid = f"r{_prefix}-{next(_ids)}"
    item = {"id": rid, **asdict(step)}
    with _lock:
        _store[rid] = item
        while len(_store) > MAX_RECEIPTS:
            _store.popitem(last=False)
    return rid


def get(rid: str) -> dict | None:
    with _lock:
        return _store.get(rid)


def summary(rid: str) -> dict:
    """What a step response lists: enough to label the drawer, the rest is one GET away."""
    r = get(rid)
    return {"id": rid, "agent": r["agent"], "tool": r["tool"], "queries": r["queries"], "node_ids": r["node_ids"],
            "text": r["text"], "source": r["source"]}


class Collector:
    """on_step callback for one request: stores each step and remembers the ids in order."""

    def __init__(self):
        self.ids: list[str] = []

    def __call__(self, step) -> None:
        self.ids.append(add(step))

    def summaries(self) -> list[dict]:
        return [summary(i) for i in self.ids]


def size() -> int:
    with _lock:
        return len(_store)
