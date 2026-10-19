"""Pilot classes: one graph per class, rebuilt from the event log; the student flow as a state machine over events.

The event log (store.py) is the source of truth. Every change goes log first, graph second:
  1. the request is checked against the student's state (consent given, the question it waits on)
  2. the event is written to the log, with retries; if that fails nothing is acknowledged
  3. the same apply() that replays the log on startup updates the graph and the in-memory state
Each class has one lock held across 2 and 3, so the log's order is the order the graph saw. Replaying the log
into a fresh copy of class_template (graph class_pilot_<code>) gives back the same graph, which is how a
restart, a deletion or a failed step is recovered.

Session 1: assent -> check (fixed S1 items) -> Diagnoser (if a check answer was wrong) -> Tutor's check question.
Session 2 (once the teacher opens it): assent -> check (fixed S2 items) -> recall of session 1's practice.
All words come from wording.py: the agents run with template writing and their text is never shown.
"""

import csv
import functools
import hashlib
import hmac
import io
import logging
import secrets
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone

from unlearn import llm, tools
from unlearn import queries as Q
from unlearn.agents import runner
from unlearn.db import delete_graph, list_graphs, recreate_graph, run, run_batched
from unlearn.pilot import items as I
from unlearn.pilot.store import Duplicate, Event, SaveFailed, Store

log = logging.getLogger("unlearn.pilot")

TEMPLATE = "class_template"
PREFIX = "pilot_"
WRITER = functools.partial(llm.write, providers=[])  # template words only: never a model call
SESSIONS = 2
ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"        # no 0/O, 1/I/L
CLASS_CODE_LEN, STUDENT_CODE_LEN = 4, 5
MAX_STUDENTS = 60
MAX_MS = 3_600_000
FAIL_LIMIT, FAIL_WINDOW_S = 30, 60                   # wrong codes or keys, across everyone


class PilotError(Exception):
    status = 400


class NotFound(PilotError):
    status = 404


class Forbidden(PilotError):
    status = 403


class Conflict(PilotError):
    status = 409


class TooMany(PilotError):
    status = 429


class NotReady(PilotError):
    status = 503


def class_id(class_code: str) -> str:
    return PREFIX + class_code.lower()


def is_pilot_class(cid: str) -> bool:
    return cid.startswith(PREFIX)


def session_id(code: str, n: int) -> str:
    return f"{code}-s{n}"


def check_session(code: str, n: int) -> str:
    """Check answers are ATTEMPTED under their own tag, so the Diagnoser's per-session state starts empty."""
    return f"{session_id(code, n)}:check"


def hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def new_code(n: int) -> str:
    return "".join(secrets.choice(ALPHABET) for _ in range(n))


def normalise(code: str) -> str:
    c = "".join(code.split()).upper()
    if "-" not in c and len(c) == CLASS_CODE_LEN + STUDENT_CODE_LEN:
        c = c[:CLASS_CODE_LEN] + "-" + c[CLASS_CODE_LEN:]
    return c


def now_ms() -> int:
    return time.time_ns() // 1_000_000


@dataclass
class Learner:
    code: str
    done: int = 0                       # sessions finished
    session: int | None = None          # the open session (after assent)
    phase: str | None = None            # 'check', 'diagnose' or 'tutor'
    check_i: int = 0
    check_wrong: list[int] = field(default_factory=list)  # constructs of wrong check answers, in order
    pending: str | None = None          # the question it waits on
    practise: int | None = None         # construct the Tutor practised (session 1)
    all_right: bool = False
    declined: bool = False              # the latest assent was "no"
    answered: set = field(default_factory=set)            # (session, question id)


@dataclass
class PilotClass:
    code: str
    key_hash: str
    item_set: str
    session2_open: bool
    learners: dict[str, Learner] = field(default_factory=dict)
    events: list[Event] = field(default_factory=list)
    lock: threading.RLock = field(default_factory=threading.RLock)
    ready: bool = False
    building: bool = False
    error: str | None = None

    @property
    def cid(self) -> str:
        return class_id(self.code)


class Pilot:
    def __init__(self, store: Store, item_set: I.ItemSet, admin_key: str | None):
        self.store, self.items, self.admin_key = store, item_set, admin_key or None
        self.classes: dict[str, PilotClass] = {}
        self.codes: dict[str, str] = {}          # student code -> class code
        self.loaded = False
        self.load_error: str | None = None
        self._lock = threading.Lock()
        self._fails: deque = deque()
        self.realigned = 0                       # replay steps where the Diagnoser's pick had to be realigned

    # --- startup -----------------------------------------------------------------------------------------

    def load_all(self) -> None:
        """Rebuild every class from the log. Called once at startup (in the background)."""
        self.store.init()
        for row in self.store.classes():
            pc = PilotClass(row["class_code"], row["teacher_key_hash"], row["item_set"], row["session2_open"])
            codes = self.store.codes(pc.code)
            with self._lock:
                self.classes[pc.code] = pc
                self.codes.update({c: pc.code for c in codes})
            if pc.item_set != self.items.digest():
                pc.error = "the approved item set changed after this class was created"
                log.error("pilot class %s: %s; not rebuilt", pc.code, pc.error)
                continue
            self._rebuild(pc, codes)
        self.loaded = True

    def _rebuild(self, pc: PilotClass, codes: list[str] | None = None) -> None:
        with pc.lock:
            pc.ready, pc.building = False, True
            try:
                codes = codes if codes is not None else self.store.codes(pc.code)
                build_graph(pc.cid, self.items, codes)
                pc.learners = {c: Learner(c) for c in codes}
                pc.events = []
                for ev in self.store.events(pc.code):
                    self._apply(pc, ev, replay=True)
                pc.ready = True
            finally:
                pc.building = False

    # --- the state machine ----------------------------------------------------------------------------------

    def _apply(self, pc: PilotClass, ev: Event, replay: bool = False) -> None:
        """Apply one logged event to the graph and the learner's state. The same code runs live and on replay."""
        L = pc.learners.get(ev.code)
        if L is None:
            return
        pc.events.append(ev)
        if ev.kind == "assent":
            L.declined = not ev.assent
            if ev.assent and L.session is None and ev.session == L.done + 1 <= SESSIONS:
                L.session, L.phase, L.check_i, L.check_wrong = ev.session, "check", 0, []
                tools.start_session(pc.cid, L.code, session_id(L.code, ev.session), ts=ev.ts)
                L.pending = self.items.check[ev.session][0]
            return
        if L.session != ev.session:
            log.error("pilot: answer %s for %s outside an open session; skipped", ev.id, ev.code)
            return
        L.answered.add((ev.session, ev.question_id))
        sess = session_id(L.code, ev.session)
        if L.phase == "check":
            tools.record_attempt(pc.cid, L.code, ev.question_id, ev.option, check_session(L.code, ev.session),
                                 ts=ev.ts)
            if not ev.correct:
                L.check_wrong.append(self.items.items[ev.question_id]["construct_id"])
            L.check_i += 1
            ids = self.items.check[ev.session]
            if L.check_i < len(ids):
                L.pending = ids[L.check_i]
                return
            L.pending = None
            if ev.session == 1 and L.check_wrong:
                out = runner.start(pc.cid, L.code, self._target(pc, L.check_wrong), session_id=sess, writer=WRITER,
                                   new_session=False)
                self._after_agent(pc, L, sess, out)
            else:
                L.all_right = ev.session == 1
                self._finish(L)
            return
        if replay:
            self._realign(pc, sess, ev.question_id)
        out = runner.answer(pc.cid, sess, ev.question_id, ev.option, writer=WRITER)
        self._after_agent(pc, L, sess, out)

    def _after_agent(self, pc: PilotClass, L: Learner, sess: str, out: dict) -> None:
        if out["kind"] == "question":
            L.phase, L.pending = "diagnose", out["question"]["id"]
            return
        if out["kind"] == "diagnosis" and out.get("next_task"):
            tut = runner.remediate(pc.cid, sess, writer=WRITER)
            L.practise = (tut.get("root") or {}).get("id")
            if tut["kind"] == "check":
                L.phase, L.pending = "tutor", tut["question"]["id"]
                return
        self._finish(L)

    def _finish(self, L: Learner) -> None:
        L.done, L.session, L.phase, L.pending = L.session, None, None, None

    def _target(self, pc: PilotClass, wrong: list[int]) -> int:
        """Diagnose under the wrong check construct with the most prerequisites (ties: the earliest asked)."""
        rows, _ = run(tools.graph_name(pc.cid), Q.PILOT_PREREQ_COUNTS, {"ids": sorted(set(wrong))})
        n = {r["id"]: r["n"] for r in rows}
        return min(wrong, key=lambda c: (-n.get(c, 0), wrong.index(c)))

    def _realign(self, pc: PilotClass, sess: str, qid: str) -> None:
        """On replay, make the waiting task expect the logged question even if a tie was broken differently."""
        t = runner.awaiting(pc.cid, sess)
        if t["pending_qid"] != qid:
            self.realigned += 1
            log.warning("pilot replay: %s waited on %s, log has %s", t["id"], t["pending_qid"], qid)
            tools.set_pending(pc.cid, t["id"], qid, self.items.items[qid]["construct_id"])

    # --- student requests -------------------------------------------------------------------------------------

    def _fail(self) -> None:
        now = time.monotonic()
        with self._lock:
            while self._fails and now - self._fails[0] > FAIL_WINDOW_S:
                self._fails.popleft()
            self._fails.append(now)

    def _limited(self) -> None:
        now = time.monotonic()
        with self._lock:
            while self._fails and now - self._fails[0] > FAIL_WINDOW_S:
                self._fails.popleft()
            if len(self._fails) >= FAIL_LIMIT:
                raise TooMany("too many wrong codes; wait a minute")

    def _learner(self, code: str) -> tuple[PilotClass, Learner]:
        self._limited()
        if not self.loaded:
            raise NotReady("warming")
        code = normalise(code)
        cc = self.codes.get(code)
        if cc is None:
            self._fail()
            raise NotFound("bad_code")
        pc = self.classes[cc]
        if pc.error:
            raise NotReady("not_open")
        if not pc.ready and self.loaded and not pc.building:
            try:  # an earlier rebuild failed (the log was unreachable, say): try again now
                self._rebuild(pc)
            except Exception:
                log.exception("pilot: rebuilding class %s failed", pc.code)
        if not pc.ready:
            raise NotReady("warming")
        return pc, pc.learners[code]

    def state(self, code: str) -> dict:
        pc, L = self._learner(code)
        with pc.lock:
            return self._screen(pc, L)

    def assent(self, code: str, session: int, agree: bool) -> dict:
        pc, L = self._learner(code)
        with pc.lock:
            expected = L.done + 1
            if (L.session is not None or expected > SESSIONS or session != expected
                    or (expected == 2 and not pc.session2_open)):
                return self._screen(pc, L)
            self._log_and_apply(pc, Event(L.code, session, "assent", now_ms(), assent=bool(agree)))
            return {"screen": "declined"} if not agree else self._screen(pc, L)

    def answer(self, code: str, session: int, qid: str, key: str, ms: int | None) -> dict:
        pc, L = self._learner(code)
        with pc.lock:
            if (session, qid) in L.answered:              # a resent answer: already logged
                return self._screen(pc, L, just_done=session)
            if L.session is None or L.session != session:
                raise Conflict("no open session: assent comes first")
            if L.pending != qid:
                return self._screen(pc, L)               # the page was behind; show where the student is
            opt = self.items.option(qid, key)
            if opt is None:
                raise PilotError(f"no option {key!r} on {qid}")
            ms = None if ms is None else max(0, min(int(ms), MAX_MS))
            ev = Event(L.code, session, "answer", now_ms(), phase=L.phase, question_id=qid, option=key,
                       correct=bool(opt.get("correct")), misconception_id=opt.get("misconception_id"), ms=ms)
            self._log_and_apply(pc, ev)
            return self._screen(pc, L, just_done=session)

    def _log_and_apply(self, pc: PilotClass, ev: Event) -> None:
        try:
            self.store.append(ev)                         # SaveFailed propagates: nothing acknowledged
        except Duplicate:
            log.warning("pilot: %s already logged; rebuilding class %s from the log", ev.question_id, pc.code)
            self._rebuild(pc)
            return
        try:
            self._apply(pc, ev)
        except Exception:
            log.exception("pilot: applying event %s failed; rebuilding class %s from the log", ev.id, pc.code)
            self._rebuild(pc)

    def _question(self, qid: str) -> dict:
        it = self.items.items[qid]
        return {"id": qid, "text": it["text"], "options": [{"key": o["key"], "text": o["text"]} for o in it["options"]]}

    def _screen(self, pc: PilotClass, L: Learner, just_done: int | None = None) -> dict:
        if L.session is not None:
            out = {"screen": "question", "session": L.session, "phase": L.phase, "question": self._question(L.pending)}
            if L.phase == "check":
                out["progress"] = {"i": L.check_i + 1, "n": len(self.items.check[L.session])}
            elif L.phase == "tutor":
                out["practise"] = self.items.constructs.get(L.practise)
            return out
        if just_done is not None and L.done == just_done:
            return self._done_screen(pc, L, just_done)
        if L.done >= SESSIONS:
            return {"screen": "finished"}
        if L.done == 1 and not pc.session2_open:
            return {"screen": "wait"}
        return {"screen": "assent", "session": L.done + 1}

    def _done_screen(self, pc: PilotClass, L: Learner, n: int) -> dict:
        if n == 1:
            return {"screen": "done", "session": 1, "all_right": L.all_right}
        # Recall comes after session 2's check, so it can't prime the answers.
        rows, _ = run(tools.graph_name(pc.cid), Q.PILOT_DIAGNOSES, {"sid": L.code})
        first = [r for r in rows if r["session"] == 1]
        name = self.items.constructs.get(first[-1]["id"]) if first else None
        return {"screen": "done", "session": 2, "recall": name}

    # --- teacher requests ------------------------------------------------------------------------------------

    def _check_admin(self, admin_key: str) -> None:
        self._limited()
        if not self.admin_key or not hmac.compare_digest(admin_key or "", self.admin_key):
            self._fail()
            raise Forbidden("wrong admin key")

    def teacher(self, class_code: str, key: str) -> PilotClass:
        self._limited()
        pc = self.classes.get(normalise(class_code or ""))
        if pc is None or not hmac.compare_digest(hash_key(key or ""), pc.key_hash):
            self._fail()
            raise Forbidden("wrong class code or teacher key")
        return pc

    def create_class(self, admin_key: str, n: int) -> dict:
        self._check_admin(admin_key)
        if not self.loaded:
            raise NotReady("warming")
        why = self.items.usable()
        if why:
            raise Conflict(why)
        if not 1 <= n <= MAX_STUDENTS:
            raise PilotError(f"between 1 and {MAX_STUDENTS} students")
        for _ in range(10):
            cc = new_code(CLASS_CODE_LEN)
            codes = set()
            while len(codes) < n:
                codes.add(f"{cc}-{new_code(STUDENT_CODE_LEN)}")
            codes = sorted(codes)
            key = secrets.token_urlsafe(12)
            if cc in self.classes:
                continue
            try:
                self.store.create_class(cc, hash_key(key), self.items.digest(), codes, now_ms())
            except Duplicate:
                continue
            pc = PilotClass(cc, hash_key(key), self.items.digest(), False)
            with self._lock:
                self.classes[cc] = pc
                self.codes.update({c: cc for c in codes})
            self._rebuild(pc, codes)
            return {"class_code": cc, "teacher_key": key, "codes": codes}
        raise Conflict("could not pick a free class code")

    def set_session2(self, pc: PilotClass, is_open: bool) -> None:
        with pc.lock:
            self.store.set_session2_open(pc.code, is_open)
            pc.session2_open = is_open

    def set_rating(self, pc: PilotClass, code: str, rating: int | None) -> None:
        if normalise(code) not in pc.learners:
            raise NotFound("no such code in this class")
        if rating is not None and not 1 <= rating <= 5:
            raise PilotError("rating is 1 to 5")
        self.store.set_rating(normalise(code), rating, now_ms())

    def set_followup(self, pc: PilotClass, code: str, followed_up: bool) -> None:
        """The teacher went through the practice topic with this student (or not). Not controlled by the pilot:
        this toggle is the only record of follow-up between sessions."""
        if normalise(code) not in pc.learners:
            raise NotFound("no such code in this class")
        self.store.set_followup(normalise(code), bool(followed_up))

    def overview(self, pc: PilotClass) -> dict:
        """Per code: progress, check scores, the diagnosed root, misconceptions shown, the Tutor's skill."""
        if pc.error:
            return {"class_code": pc.code, "error": pc.error, "students": []}
        g = tools.graph_name(pc.cid)
        ratings, followups = self.store.ratings(pc.code), self.store.followups(pc.code)
        with pc.lock:  # snapshot, then read the graph without holding up the students
            learners = sorted((code, _status(L)) for code, L in pc.learners.items())
            events = list(pc.events)
        students = []
        for code, status in learners:
            evs = [e for e in events if e.code == code]
            checks = {n: [e for e in evs if e.kind == "answer" and e.phase == "check" and e.session == n]
                      for n in (1, 2)}
            dx, _ = run(g, Q.PILOT_DIAGNOSES, {"sid": code})
            plans, _ = run(g, Q.PILOT_TUTOR_PLANS, {"sid": code})
            showed, _ = run(g, Q.STUDENT_SHOWED, {"sid": code})
            skill = next((p["skill"] for p in plans if p["skill"]), None)
            steps = [r["text"] for r in run(g, Q.SKILL_STEPS, {"name": skill})[0]] if skill else []
            students.append({
                "code": code, "status": status,
                "check": {n: {"right": sum(e.correct for e in c), "of": len(self.items.check[n]), "answered": len(c)}
                          for n, c in checks.items()},
                "questions_after_check": sum(1 for e in evs if e.kind == "answer" and e.phase != "check"),
                "root": dx[-1]["name"] if dx else None,
                "misconceptions": [{"name": r["name"], "count": r["count"]} for r in showed[:5]],
                "skill": skill, "skill_steps": steps, "rating": ratings.get(code),
                "followed_up": followups.get(code, False)})
        return {"class_code": pc.code, "session2_open": pc.session2_open, "items": self.items.counts(),
                "students": students}

    def answers_csv(self, pc: PilotClass) -> str:
        buf = io.StringIO()
        w = csv.writer(buf, lineterminator="\n")
        w.writerow(["code", "session", "phase", "question_id", "option", "correct", "misconception_id",
                    "answered_at_utc", "time_to_answer_ms"])
        with pc.lock:
            for e in pc.events:
                if e.kind == "answer":
                    w.writerow([e.code, e.session, e.phase, e.question_id, e.option, int(e.correct),
                                e.misconception_id if e.misconception_id is not None else "",
                                datetime.fromtimestamp(e.ts / 1000, timezone.utc).isoformat(timespec="seconds"),
                                e.ms if e.ms is not None else ""])
        return buf.getvalue()

    def summary_csv(self, pc: PilotClass) -> str:
        buf = io.StringIO()
        w = csv.writer(buf, lineterminator="\n")
        w.writerow(["code", "status", "session1_check_right", "session2_check_right", "questions_after_check",
                    "diagnosed_root", "misconceptions_shown", "tutor_skill", "teacher_rating",
                    "teacher_went_through_practice"])
        for s in self.overview(pc)["students"]:
            c1, c2 = s["check"][1], s["check"][2]
            w.writerow([s["code"], s["status"], f"{c1['right']}/{c1['answered']}" if c1["answered"] else "",
                        f"{c2['right']}/{c2['answered']}" if c2["answered"] else "", s["questions_after_check"],
                        s["root"] or "", "; ".join(f"{m['name']} (x{m['count']})" for m in s["misconceptions"]),
                        s["skill"] or "", s["rating"] or "", "yes" if s["followed_up"] else "no"])
        return buf.getvalue()

    # --- deletion --------------------------------------------------------------------------------------------

    def delete_code(self, pc: PilotClass, code: str) -> None:
        """Delete one student's rows from the log, then rebuild the class graph without them."""
        code = normalise(code)
        if code not in pc.learners:
            raise NotFound("no such code in this class")
        with pc.lock:
            self.store.delete_code(code)
            with self._lock:
                self.codes.pop(code, None)
            self._rebuild(pc)

    def delete_class(self, pc: PilotClass) -> None:
        with pc.lock:
            self.store.delete_class(pc.code)
            delete_graph(tools.graph_name(pc.cid))
            with self._lock:
                self.classes.pop(pc.code, None)
                for c in [c for c, cc in self.codes.items() if cc == pc.code]:
                    del self.codes[c]
            pc.ready, pc.error = False, "deleted"

    def wipe(self, admin_key: str) -> int:
        self._check_admin(admin_key)
        return wipe_all(self.store, self)

    def status(self) -> dict:
        return {"configured": True, "loaded": self.loaded, "load_error": self.load_error,
                "ready": self.loaded and all(pc.ready or pc.error for pc in self.classes.values()),
                "wording_approved": self.items.wording_approved, "items": self.items.counts(),
                "classes": len(self.classes)}


def _status(L: Learner) -> str:
    if L.session is not None:
        return f"session {L.session} in progress"
    if L.done >= SESSIONS:
        return "both sessions done"
    if L.done == 1:
        return "session 1 done"
    if L.declined:
        return "declined"
    return "not started"


def build_graph(cid: str, item_set: I.ItemSet, codes: list[str]) -> None:
    """class_pilot_<code>: class_template with only the approved questions, in the pilot's wording, plus the
    class's codes as students. Fails if the graph doesn't end up matching items.json exactly."""
    g = tools.graph_name(cid)
    recreate_graph(TEMPLATE, g)
    keep = sorted(item_set.items)
    run(g, Q.PILOT_DROP_UNKEPT_OPTIONS, {"keep": keep})
    run(g, Q.PILOT_DROP_UNKEPT_QUESTIONS, {"keep": keep})
    for qid, it in item_set.items.items():
        if not run(g, Q.PILOT_SET_QUESTION, {"id": qid, "text": it["text"],
                                             "check_only": True if it["role"] != "POOL" else None})[0]:
            raise RuntimeError(f"{qid} is not in {TEMPLATE}")
        run(g, Q.PILOT_CLEAR_OPTIONS, {"qid": qid})
        run_batched(g, Q.LOAD_OPTIONS, [{"qid": qid, "key": o["key"], "text": o["text"],
                                         "correct": bool(o.get("correct")), "mid": o.get("misconception_id")}
                                        for o in it["options"]])
    run_batched(g, Q.LOAD_STUDENTS, [{"id": c, "alias": c} for c in codes])
    got, _ = run(g, Q.PILOT_OPTION_TAGS)
    want = sorted((qid, o["key"], o["text"], bool(o.get("correct")), o.get("misconception_id"))
                  for qid, it in item_set.items.items() for o in it["options"])
    have = sorted((r["qid"], r["key"], r["option"], bool(r["correct"]), r["mid"]) for r in got)
    if have != want:
        raise RuntimeError(f"pilot graph {g} does not match the approved items")


def wipe_all(store: Store, pilot: Pilot | None = None) -> int:
    """Delete every pilot row and every pilot graph. Returns the number of graphs dropped."""
    store.wipe()
    dropped = 0
    for g in list_graphs():
        if g.startswith("class_" + PREFIX):
            delete_graph(g)
            dropped += 1
    if pilot is not None:
        with pilot._lock:
            for pc in pilot.classes.values():
                pc.ready, pc.error = False, "deleted"
            pilot.classes.clear()
            pilot.codes.clear()
    return dropped
