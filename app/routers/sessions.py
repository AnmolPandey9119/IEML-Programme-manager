from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session as DB

from ..deps import EventCtx, event_ctx
from ..models import (EventDay, Hall, PublishStatus, Role, Session, SessionRole, SessionSpeaker, SessionSubtopic,
                      SessionType, Speaker)
from ..schemas import AssignIn, SessionIn, SessionOut, Warning_
from ..services.conflicts import check_slot
from ..services.late_change import notify_if_late, snapshot
from ..services.sessions import (event_sessions_out, load_sessions, session_out, slot_from_input, slot_of)

router = APIRouter(prefix="/api/events/{event_id}/sessions", tags=["sessions"])
editor_write = event_ctx(Role.editor, write=True)
admin_write = event_ctx(Role.admin, write=True)


def _validate(ctx: EventCtx, data: SessionIn) -> None:
    db, eid = ctx.db, ctx.event.id
    day = db.get(EventDay, data.day_id)
    if not day or day.event_id != eid:
        raise HTTPException(422, "Choose a day that belongs to this event")
    if data.hall_id is not None and not data.is_merged:
        hall = db.get(Hall, data.hall_id)
        if not hall or hall.event_id != eid:
            raise HTTPException(422, "Choose a hall that belongs to this event")
    if not data.title.strip():
        raise HTTPException(422, "Enter a session title")
    if data.session_type == SessionType.custom and not data.custom_type_label.strip():
        raise HTTPException(422, "Name the custom session type")
    ids = {p.speaker_id for p in data.people}
    if ids:
        found = set(db.scalars(select(Speaker.id).where(Speaker.event_id == eid, Speaker.id.in_(ids))))
        if found != ids:
            raise HTTPException(422, "One of the selected speakers does not belong to this event")


def _apply(ctx: EventCtx, s: Session, data: SessionIn) -> None:
    s.day_id = data.day_id
    s.is_merged = data.is_merged
    s.hall_id = None if data.is_merged else data.hall_id
    s.title = data.title.strip()
    s.session_type = data.session_type
    s.custom_type_label = data.custom_type_label.strip() if data.session_type == SessionType.custom else ""
    s.writeup = data.writeup.strip()
    s.start_time, s.end_time = data.start_time.replace(second=0, microsecond=0), data.end_time.replace(second=0, microsecond=0)
    s.status = data.status
    s.internal_notes = data.internal_notes.strip()
    s.subtopics.clear()
    for i, t in enumerate(x.strip() for x in data.subtopics if x.strip()):
        s.subtopics.append(SessionSubtopic(text=t, position=i))
    s.speaker_links.clear()
    ctx.db.flush()
    seen = set()
    for i, p in enumerate(data.people):
        if (p.speaker_id, p.role) in seen:
            continue
        seen.add((p.speaker_id, p.role))
        s.speaker_links.append(SessionSpeaker(speaker_id=p.speaker_id, role=p.role, position=i))


def _fresh(ctx: EventCtx, session_id: int) -> SessionOut:
    out = next((o for o in event_sessions_out(ctx.db, ctx.event.id) if o.id == session_id), None)
    if not out:
        raise HTTPException(404, "Session not found")
    return out


def _own(ctx: EventCtx, session_id: int) -> Session:
    s = ctx.db.get(Session, session_id)
    if not s or s.event_id != ctx.event.id:
        raise HTTPException(404, "Session not found")
    return s


@router.get("", response_model=list[SessionOut])
def list_sessions(ctx: EventCtx = Depends(event_ctx(Role.viewer))):
    return event_sessions_out(ctx.db, ctx.event.id)


@router.post("/check", response_model=list[Warning_])
def check_session(data: SessionIn, ctx: EventCtx = Depends(event_ctx(Role.viewer))):
    """Dry run used by the editor: nothing is saved. Warnings only, never an error for a schedule problem."""
    cand = slot_from_input(ctx.db, ctx.event, data)
    others = [slot_of(s) for s in load_sessions(ctx.db, ctx.event.id)]
    return [Warning_(**w) for w in check_slot(cand, others)]


@router.post("", response_model=SessionOut, status_code=201)
def create_session(data: SessionIn, bg: BackgroundTasks, ctx: EventCtx = Depends(editor_write)):
    _validate(ctx, data)
    s = Session(event_id=ctx.event.id, day_id=data.day_id, title="", start_time=data.start_time, end_time=data.end_time)
    ctx.db.add(s)
    ctx.db.flush()
    _apply(ctx, s, data)
    ctx.db.commit()
    return _fresh(ctx, s.id)


@router.get("/{session_id}", response_model=SessionOut)
def get_session(session_id: int, ctx: EventCtx = Depends(event_ctx(Role.viewer))):
    _own(ctx, session_id)
    return _fresh(ctx, session_id)


@router.put("/{session_id}", response_model=SessionOut)
def update_session(session_id: int, data: SessionIn, bg: BackgroundTasks, ctx: EventCtx = Depends(editor_write)):
    _own(ctx, session_id)
    _validate(ctx, data)
    s = load_one(ctx, session_id)
    before = snapshot(s)
    _apply(ctx, s, data)
    ctx.db.commit()
    ctx.db.expire_all()  # relationships (hall, speakers) must be re-read after the change
    s = load_one(ctx, session_id)
    notify_if_late(ctx.db, ctx.event, s, before, snapshot(s), ctx.user.full_name or ctx.user.email, bg)
    return _fresh(ctx, session_id)


@router.post("/{session_id}/duplicate", response_model=SessionOut, status_code=201)
def duplicate_session(session_id: int, ctx: EventCtx = Depends(editor_write)):
    src = load_one(ctx, session_id)
    copy = Session(event_id=ctx.event.id, day_id=src.day_id, hall_id=src.hall_id, is_merged=src.is_merged,
                   title=f"{src.title} (copy)"[:500], session_type=src.session_type, custom_type_label=src.custom_type_label,
                   writeup=src.writeup, start_time=src.start_time, end_time=src.end_time,
                   status=PublishStatus.draft, internal_notes=src.internal_notes)
    for t in src.subtopics:
        copy.subtopics.append(SessionSubtopic(text=t.text, position=t.position))
    for l in src.speaker_links:
        copy.speaker_links.append(SessionSpeaker(speaker_id=l.speaker_id, role=l.role, position=l.position))
    ctx.db.add(copy)
    ctx.db.commit()
    return _fresh(ctx, copy.id)


def load_one(ctx: EventCtx, session_id: int) -> Session:
    s = next((x for x in load_sessions(ctx.db, ctx.event.id) if x.id == session_id), None)
    if not s:
        raise HTTPException(404, "Session not found")
    return s


def add_person(ctx: EventCtx, session_id: int, speaker_id: int, role: SessionRole, bg: BackgroundTasks) -> SessionOut:
    """Adds one speaker to a session without touching anything else (used by the speaker-invite review too).
    Schedule problems come back as warnings on the returned session, never as errors."""
    _own(ctx, session_id)
    sp = ctx.db.get(Speaker, speaker_id)
    if not sp or sp.event_id != ctx.event.id:
        raise HTTPException(422, "That speaker does not belong to this event")
    s = load_one(ctx, session_id)
    before = snapshot(s)
    if not any(l.speaker_id == speaker_id and l.role == role for l in s.speaker_links):
        pos = max((l.position for l in s.speaker_links), default=-1) + 1
        ctx.db.add(SessionSpeaker(session_id=session_id, speaker_id=speaker_id, role=role, position=pos))
        ctx.db.commit()
    ctx.db.expire_all()
    s = load_one(ctx, session_id)
    notify_if_late(ctx.db, ctx.event, s, before, snapshot(s), ctx.user.full_name or ctx.user.email, bg)
    return _fresh(ctx, session_id)


@router.post("/{session_id}/people", response_model=SessionOut)
def assign_person(session_id: int, data: AssignIn, bg: BackgroundTasks, ctx: EventCtx = Depends(editor_write)):
    return add_person(ctx, session_id, data.speaker_id, data.role, bg)


@router.delete("/{session_id}/people/{speaker_id}", response_model=SessionOut)
def unassign_person(session_id: int, speaker_id: int, bg: BackgroundTasks, ctx: EventCtx = Depends(editor_write)):
    """Takes the speaker out of this session (every role they hold in it)."""
    _own(ctx, session_id)
    s = load_one(ctx, session_id)
    before = snapshot(s)
    for l in [l for l in s.speaker_links if l.speaker_id == speaker_id]:
        ctx.db.delete(l)
    ctx.db.commit()
    ctx.db.expire_all()
    s = load_one(ctx, session_id)
    notify_if_late(ctx.db, ctx.event, s, before, snapshot(s), ctx.user.full_name or ctx.user.email, bg)
    return _fresh(ctx, session_id)


@router.delete("/{session_id}", status_code=204)
def delete_session(session_id: int, ctx: EventCtx = Depends(admin_write)):
    s = _own(ctx, session_id)
    ctx.db.delete(s)
    ctx.db.commit()