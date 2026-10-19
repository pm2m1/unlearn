"""HTTP API for pilot mode, mounted under /pilot by main.py. Off unless PILOT_DATABASE_URL is set.

Student routes take the anonymous code in the JSON body (never in the URL, so it stays out of request logs).
Teacher routes take the class code and teacher key in headers; creating a class or wiping needs PILOT_ADMIN_KEY.
"""

import logging
import os
import threading
import time
from pathlib import Path

from fastapi import APIRouter, Header
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel, Field

from unlearn.pilot import items as I
from unlearn.pilot import wording
from unlearn.pilot.engine import Pilot, PilotError
from unlearn.pilot.store import SaveFailed, Store

log = logging.getLogger("unlearn.pilot")
STATIC = Path(__file__).resolve().parents[2] / "static"
LOAD_RETRY_S = 30
NO_STORE = {"Cache-Control": "no-store"}

router = APIRouter(prefix="/pilot")
_state: dict = {"pilot": None}


def configure(url: str | None = None, admin_key: str | None = None, item_set: I.ItemSet | None = None) -> Pilot | None:
    """Set up the pilot from the environment (or the arguments). Returns None when it's off."""
    url = url or os.getenv("PILOT_DATABASE_URL")
    if not url:
        _state["pilot"] = None
        return None
    p = Pilot(Store(url), item_set or I.load(), admin_key if admin_key is not None else os.getenv("PILOT_ADMIN_KEY"))
    _state["pilot"] = p
    return p


def start_loading(p: Pilot) -> threading.Thread:
    """Rebuild every pilot class from the log in the background, retrying while the log is unreachable."""
    def go():
        while True:
            try:
                p.load_all()
                p.load_error = None
                log.info("pilot: %d classes loaded", len(p.classes))
                return
            except Exception as e:
                p.load_error = type(e).__name__
                log.exception("pilot: loading from the log failed; retrying in %d s", LOAD_RETRY_S)
                time.sleep(LOAD_RETRY_S)
    t = threading.Thread(target=go, name="pilot-load", daemon=True)
    t.start()
    return t


def pilot() -> Pilot | None:
    return _state["pilot"]


def _call(fn, *args, csv_name: str | None = None):
    p = pilot()
    if p is None:
        return JSONResponse({"detail": "off"}, status_code=503, headers=NO_STORE)
    try:
        out = fn(p, *args)
    except SaveFailed:
        return JSONResponse({"detail": "save_failed"}, status_code=503, headers=NO_STORE)
    except PilotError as e:
        return JSONResponse({"detail": str(e)}, status_code=e.status, headers=NO_STORE)
    if csv_name:
        return Response(out, media_type="text/csv", headers={
            **NO_STORE, "Content-Disposition": f'attachment; filename="{csv_name}"'})
    return JSONResponse(out if out is not None else {"ok": True}, headers=NO_STORE)


# --- pages -----------------------------------------------------------------------------------------------

@router.get("", include_in_schema=False)
def student_page():
    return FileResponse(STATIC / "pilot.html", headers=NO_STORE)


@router.get("/teacher", include_in_schema=False)
def teacher_page():
    return FileResponse(STATIC / "pilot-teacher.html", headers=NO_STORE)


@router.get("/api/status")
def status():
    p = pilot()
    return JSONResponse(p.status() if p else {"configured": False}, headers=NO_STORE)


@router.get("/api/wording")
def get_wording():
    return JSONResponse(wording.bundle())


# --- students --------------------------------------------------------------------------------------------

class CodeBody(BaseModel):
    code: str = Field(..., min_length=1, max_length=20)


class AssentBody(CodeBody):
    session: int = Field(..., ge=1, le=2)
    agree: bool


class AnswerBody(CodeBody):
    session: int = Field(..., ge=1, le=2)
    qid: str = Field(..., min_length=1, max_length=20)
    key: str = Field(..., pattern="^[A-D]$")
    ms: int | None = Field(None, ge=0, le=86_400_000)


@router.post("/api/state")
def state(body: CodeBody):
    return _call(lambda p: p.state(body.code))


@router.post("/api/assent")
def assent(body: AssentBody):
    return _call(lambda p: p.assent(body.code, body.session, body.agree))


@router.post("/api/answer")
def answer(body: AnswerBody):
    return _call(lambda p: p.answer(body.code, body.session, body.qid, body.key, body.ms))


# --- teacher ---------------------------------------------------------------------------------------------

class CreateBody(BaseModel):
    students: int = Field(..., ge=1, le=60)


class OpenBody(BaseModel):
    open: bool


class RatingBody(CodeBody):
    rating: int | None = Field(None, ge=1, le=5)


class ConfirmBody(BaseModel):
    confirm: str = Field(..., max_length=20)


def _teacher(p: Pilot, cls: str | None, key: str | None):
    return p.teacher(cls or "", key or "")


@router.post("/api/teacher/create")
def create(body: CreateBody, x_pilot_admin: str | None = Header(None)):
    return _call(lambda p: p.create_class(x_pilot_admin or "", body.students))


@router.post("/api/teacher/overview")
def overview(x_pilot_class: str | None = Header(None), x_pilot_key: str | None = Header(None)):
    return _call(lambda p: p.overview(_teacher(p, x_pilot_class, x_pilot_key)))


@router.post("/api/teacher/session2")
def session2(body: OpenBody, x_pilot_class: str | None = Header(None), x_pilot_key: str | None = Header(None)):
    return _call(lambda p: p.set_session2(_teacher(p, x_pilot_class, x_pilot_key), body.open))


@router.post("/api/teacher/rating")
def rating(body: RatingBody, x_pilot_class: str | None = Header(None), x_pilot_key: str | None = Header(None)):
    return _call(lambda p: p.set_rating(_teacher(p, x_pilot_class, x_pilot_key), body.code, body.rating))


@router.post("/api/teacher/export/answers")
def export_answers(x_pilot_class: str | None = Header(None), x_pilot_key: str | None = Header(None)):
    return _call(lambda p: p.answers_csv(_teacher(p, x_pilot_class, x_pilot_key)), csv_name="pilot-answers.csv")


@router.post("/api/teacher/export/summary")
def export_summary(x_pilot_class: str | None = Header(None), x_pilot_key: str | None = Header(None)):
    return _call(lambda p: p.summary_csv(_teacher(p, x_pilot_class, x_pilot_key)), csv_name="pilot-summary.csv")


@router.post("/api/teacher/delete-code")
def delete_code(body: CodeBody, x_pilot_class: str | None = Header(None), x_pilot_key: str | None = Header(None)):
    return _call(lambda p: p.delete_code(_teacher(p, x_pilot_class, x_pilot_key), body.code))


@router.post("/api/teacher/delete-class")
def delete_class(body: ConfirmBody, x_pilot_class: str | None = Header(None), x_pilot_key: str | None = Header(None)):
    def go(p):
        pc = _teacher(p, x_pilot_class, x_pilot_key)
        if body.confirm.strip().upper() != pc.code:
            raise PilotError("type the class code to confirm")
        p.delete_class(pc)
    return _call(go)


@router.post("/api/admin/wipe")
def wipe(body: ConfirmBody, x_pilot_admin: str | None = Header(None)):
    def go(p):
        if body.confirm != "WIPE":
            raise PilotError('type WIPE to confirm')
        return {"graphs_dropped": p.wipe(x_pilot_admin or "")}
    return _call(go)
