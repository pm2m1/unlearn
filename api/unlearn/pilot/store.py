"""The pilot's event log: the only durable copy of pilot data. Postgres (Neon) in production, SQLite in tests.

    PILOT_DATABASE_URL=postgresql://...?sslmode=require   (Neon)
    PILOT_DATABASE_URL=sqlite:///path/to/pilot.db         (tests, local runs)

Events are only ever added during a pilot; the one exception is deletion, which removes rows for real. The
tables hold exactly the columns in SCHEMA and nothing else: codes are random, and no names, contact details,
IP addresses, device details or free text are stored (tests/test_pilot.py checks the live schema).

Every write retries with backoff (Neon's compute sleeps when idle and takes a moment to wake). If it still
fails, SaveFailed is raised and the caller must not acknowledge the answer.
"""

import sqlite3
import threading
import time
from dataclasses import dataclass, fields

# The only columns pilot data may have. Changing this is a decision for the pilot owner, not a refactor.
SCHEMA = {
    "pilot_classes": ["class_code", "teacher_key_hash", "item_set", "session2_open", "created_at"],
    "pilot_codes": ["code", "class_code"],
    "pilot_events": ["id", "code", "session", "kind", "phase", "question_id", "option", "correct",
                     "misconception_id", "ts", "ms", "assent"],
    "pilot_ratings": ["code", "rating", "ts"],
    "pilot_followups": ["code", "followed_up"],   # the teacher went through the practice topic with this code
}

_DDL = {
    "pilot_classes": "CREATE TABLE IF NOT EXISTS pilot_classes (class_code TEXT PRIMARY KEY, "
                     "teacher_key_hash TEXT NOT NULL, item_set TEXT NOT NULL, "
                     "session2_open BOOLEAN NOT NULL DEFAULT FALSE, created_at BIGINT NOT NULL)",
    "pilot_codes": "CREATE TABLE IF NOT EXISTS pilot_codes (code TEXT PRIMARY KEY, class_code TEXT NOT NULL)",
    "pilot_events": "CREATE TABLE IF NOT EXISTS pilot_events (id {serial}, code TEXT NOT NULL, "
                    "session INTEGER NOT NULL, kind TEXT NOT NULL, phase TEXT, question_id TEXT, option TEXT, "
                    "correct BOOLEAN, misconception_id INTEGER, ts BIGINT NOT NULL, ms INTEGER, assent BOOLEAN)",
    "pilot_ratings": "CREATE TABLE IF NOT EXISTS pilot_ratings (code TEXT PRIMARY KEY, rating INTEGER NOT NULL, "
                     "ts BIGINT NOT NULL)",
    "pilot_followups": "CREATE TABLE IF NOT EXISTS pilot_followups (code TEXT PRIMARY KEY, "
                       "followed_up BOOLEAN NOT NULL)",
}
# One answer per question per session: a resent answer is recognised, never stored twice.
_ONE_ANSWER = ("CREATE UNIQUE INDEX IF NOT EXISTS pilot_events_one_answer ON pilot_events (code, session, question_id) "
               "WHERE kind = 'answer'")

RETRY_SLEEPS = (0.5, 1.0, 2.0)  # three retries after the first try


class SaveFailed(RuntimeError):
    """The log could not be written after retrying. Nothing was acknowledged."""


class Duplicate(Exception):
    """This answer is already in the log."""


@dataclass
class Event:
    code: str
    session: int
    kind: str                      # 'assent' or 'answer'
    ts: int                        # server time, ms since the epoch
    phase: str | None = None       # answers: 'check', 'diagnose' or 'tutor'
    question_id: str | None = None
    option: str | None = None      # A-D
    correct: bool | None = None
    misconception_id: int | None = None
    ms: int | None = None          # time to answer, measured on the student's device
    assent: bool | None = None
    id: int | None = None

    @classmethod
    def from_row(cls, row: dict) -> "Event":
        d = {f.name: row[f.name] for f in fields(cls)}
        for k in ("correct", "assent"):
            if d[k] is not None:
                d[k] = bool(d[k])
        return cls(**d)


EVENT_COLUMNS = [c for c in SCHEMA["pilot_events"] if c != "id"]
assert sorted(f.name for f in fields(Event)) == sorted(SCHEMA["pilot_events"])


class Store:
    def __init__(self, url: str):
        self.url = url
        self.kind = "sqlite" if url.startswith("sqlite:") else "postgres"
        self._conn = None
        self._lock = threading.RLock()

    # --- connection ---

    def _connect(self):
        if self.kind == "sqlite":
            conn = sqlite3.connect(self.url.removeprefix("sqlite:///"), check_same_thread=False, isolation_level=None)
            conn.row_factory = sqlite3.Row
            return conn
        import psycopg
        from psycopg.rows import dict_row
        return psycopg.connect(self.url, autocommit=True, row_factory=dict_row, connect_timeout=10)

    def _sql(self, q: str) -> str:
        return q if self.kind == "sqlite" else q.replace("?", "%s")

    def _exec(self, q: str, params: tuple = (), fetch: bool = False):
        with self._lock:
            if self._conn is None:
                self._conn = self._connect()
            cur = self._conn.execute(self._sql(q), params)
            return [dict(r) for r in cur.fetchall()] if fetch else cur

    def _retry(self, fn):
        """Run fn, reconnecting and retrying on connection errors. Integrity errors are not retried."""
        last = None
        for sleep in (*RETRY_SLEEPS, None):
            try:
                return fn()
            except Duplicate:
                raise
            except Exception as e:
                if _is_integrity(e):
                    raise Duplicate() from e
                last = e
                with self._lock:
                    try:
                        if self._conn is not None:
                            self._conn.close()
                    except Exception:
                        pass
                    self._conn = None
                if sleep is None:
                    break
                time.sleep(sleep)
        raise SaveFailed(f"pilot log unavailable: {type(last).__name__}") from last

    # --- schema ---

    def init(self) -> None:
        serial = "INTEGER PRIMARY KEY AUTOINCREMENT" if self.kind == "sqlite" else "BIGSERIAL PRIMARY KEY"

        def go():
            for table, ddl in _DDL.items():
                self._exec(ddl.format(serial=serial))
            self._exec(_ONE_ANSWER)
        self._retry(go)

    def columns(self) -> dict[str, list[str]]:
        """The live tables' columns, read from the database itself."""
        out = {}
        for table in SCHEMA:
            if self.kind == "sqlite":
                rows = self._exec(f"PRAGMA table_info({table})", fetch=True)
                out[table] = [r["name"] for r in rows]
            else:
                rows = self._exec("SELECT column_name AS name FROM information_schema.columns WHERE table_name = ? "
                                  "ORDER BY ordinal_position", (table,), fetch=True)
                out[table] = [r["name"] for r in rows]
        return out

    # --- writes ---

    def create_class(self, class_code: str, teacher_key_hash: str, item_set: str, codes: list[str], ts: int) -> None:
        def go():
            with self._lock:
                self._exec("BEGIN")
                try:
                    self._exec("INSERT INTO pilot_classes (class_code, teacher_key_hash, item_set, session2_open, "
                               "created_at) VALUES (?, ?, ?, ?, ?)", (class_code, teacher_key_hash, item_set, False, ts))
                    for c in codes:
                        self._exec("INSERT INTO pilot_codes (code, class_code) VALUES (?, ?)", (c, class_code))
                    self._exec("COMMIT")
                except Exception:
                    self._exec("ROLLBACK")
                    raise
        self._retry(go)

    def append(self, ev: Event) -> int:
        """Add one event; returns its id. Raises Duplicate for a resent answer, SaveFailed if the log is down."""
        cols = ", ".join(EVENT_COLUMNS)
        marks = ", ".join("?" for _ in EVENT_COLUMNS)
        values = tuple(getattr(ev, c) for c in EVENT_COLUMNS)

        def go():
            rows = self._exec(f"INSERT INTO pilot_events ({cols}) VALUES ({marks}) RETURNING id", values, fetch=True)
            return rows[0]["id"]
        ev.id = self._retry(go)
        return ev.id

    def set_session2_open(self, class_code: str, is_open: bool) -> None:
        self._retry(lambda: self._exec("UPDATE pilot_classes SET session2_open = ? WHERE class_code = ?",
                                       (is_open, class_code)))

    def set_rating(self, code: str, rating: int | None, ts: int) -> None:
        def go():
            with self._lock:
                self._exec("DELETE FROM pilot_ratings WHERE code = ?", (code,))
                if rating is not None:
                    self._exec("INSERT INTO pilot_ratings (code, rating, ts) VALUES (?, ?, ?)", (code, rating, ts))
        self._retry(go)

    def set_followup(self, code: str, followed_up: bool) -> None:
        def go():
            with self._lock:
                self._exec("DELETE FROM pilot_followups WHERE code = ?", (code,))
                self._exec("INSERT INTO pilot_followups (code, followed_up) VALUES (?, ?)", (code, followed_up))
        self._retry(go)

    def delete_code(self, code: str) -> None:
        def go():
            with self._lock:
                self._exec("DELETE FROM pilot_events WHERE code = ?", (code,))
                self._exec("DELETE FROM pilot_ratings WHERE code = ?", (code,))
                self._exec("DELETE FROM pilot_followups WHERE code = ?", (code,))
                self._exec("DELETE FROM pilot_codes WHERE code = ?", (code,))
        self._retry(go)

    def delete_class(self, class_code: str) -> None:
        def go():
            with self._lock:
                sub = "SELECT code FROM pilot_codes WHERE class_code = ?"
                self._exec(f"DELETE FROM pilot_events WHERE code IN ({sub})", (class_code,))
                self._exec(f"DELETE FROM pilot_ratings WHERE code IN ({sub})", (class_code,))
                self._exec(f"DELETE FROM pilot_followups WHERE code IN ({sub})", (class_code,))
                self._exec("DELETE FROM pilot_codes WHERE class_code = ?", (class_code,))
                self._exec("DELETE FROM pilot_classes WHERE class_code = ?", (class_code,))
        self._retry(go)

    def wipe(self) -> None:
        """Delete every pilot row (scripts/pilot_wipe.py)."""
        def go():
            with self._lock:
                for table in ("pilot_events", "pilot_ratings", "pilot_followups", "pilot_codes", "pilot_classes"):
                    self._exec(f"DELETE FROM {table}")
        self._retry(go)

    # --- reads ---

    def classes(self) -> list[dict]:
        rows = self._retry(lambda: self._exec("SELECT * FROM pilot_classes ORDER BY created_at", fetch=True))
        for r in rows:
            r["session2_open"] = bool(r["session2_open"])
        return rows

    def codes(self, class_code: str) -> list[str]:
        rows = self._retry(lambda: self._exec("SELECT code FROM pilot_codes WHERE class_code = ? ORDER BY code",
                                              (class_code,), fetch=True))
        return [r["code"] for r in rows]

    def events(self, class_code: str) -> list[Event]:
        """The class's events in the order they were written."""
        rows = self._retry(lambda: self._exec(
            "SELECT e.* FROM pilot_events e JOIN pilot_codes c ON c.code = e.code WHERE c.class_code = ? "
            "ORDER BY e.id", (class_code,), fetch=True))
        return [Event.from_row(r) for r in rows]

    def ratings(self, class_code: str) -> dict[str, int]:
        rows = self._retry(lambda: self._exec(
            "SELECT r.code, r.rating FROM pilot_ratings r JOIN pilot_codes c ON c.code = r.code "
            "WHERE c.class_code = ?", (class_code,), fetch=True))
        return {r["code"]: r["rating"] for r in rows}

    def followups(self, class_code: str) -> dict[str, bool]:
        rows = self._retry(lambda: self._exec(
            "SELECT f.code, f.followed_up FROM pilot_followups f JOIN pilot_codes c ON c.code = f.code "
            "WHERE c.class_code = ?", (class_code,), fetch=True))
        return {r["code"]: bool(r["followed_up"]) for r in rows}

    def count(self, table: str) -> int:
        assert table in SCHEMA
        return self._retry(lambda: self._exec(f"SELECT COUNT(*) AS n FROM {table}", fetch=True))[0]["n"]


def _is_integrity(e: Exception) -> bool:
    if isinstance(e, sqlite3.IntegrityError):
        return True
    try:
        import psycopg
        return isinstance(e, psycopg.errors.IntegrityError)
    except ImportError:
        return False
