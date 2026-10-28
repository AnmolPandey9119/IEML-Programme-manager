from sqlalchemy import select
from sqlalchemy.orm import Session as DB, selectinload

from ..models import Event, Session, SessionSpeaker, SessionType
from ..schemas import SessionIn, SessionOut, SessionPersonOut, Warning_
from ..security import photo_url
from .conflicts import Slot, all_conflicts, check_slot

ROLE_ORDER = {"moderator": 0, "speaker": 1, "panelist": 1}


def load_sessions(db: DB, event_id: int) -> list[Session]:
    stmt = (select(Session).where(Session.event_id == event_id)
            .options(selectinload(Session.day), selectinload(Session.hall), selectinload(Session.subtopics),
                     selectinload(Session.speaker_links).selectinload(SessionSpeaker.speaker)))
    rows = db.scalars(stmt).all()
    return sorted(rows, key=lambda s: (s.day.day_date, s.start_time, s.end_time, s.id))


def type_label(s: Session) -> str:
    return (s.custom_type_label.strip() or "Custom") if s.session_type == SessionType.custom else s.session_type.value


def slot_of(s: Session) -> Slot:
    return Slot(id=s.id, day_id=s.day_id, hall_id=s.hall_id, hall_name=s.hall.name if s.hall else "",
                is_merged=s.is_merged, title=s.title, session_type=s.session_type.value,
                start=s.start_time, end=s.end_time,
                speakers={l.speaker_id: l.speaker.full_name for l in s.speaker_links})


def duration(s: Session) -> int | None:
    a = s.start_time.hour * 60 + s.start_time.minute
    b = s.end_time.hour * 60 + s.end_time.minute
    return b - a if b > a else None


def session_out(s: Session, warnings: list[dict]) -> SessionOut:
    links = sorted(s.speaker_links, key=lambda l: (ROLE_ORDER.get(l.role.value, 1), l.position, l.id))
    return SessionOut(
        id=s.id, day_id=s.day_id, day_label=s.day.label, day_date=s.day.day_date, hall_id=s.hall_id,
        hall_name="All halls" if s.is_merged else (s.hall.name if s.hall else ""), is_merged=s.is_merged,
        title=s.title, session_type=s.session_type, custom_type_label=s.custom_type_label, type_label=type_label(s),
        writeup=s.writeup, subtopics=[t.text for t in s.subtopics], start_time=s.start_time, end_time=s.end_time,
        duration_minutes=duration(s), status=s.status, internal_notes=s.internal_notes,
        people=[SessionPersonOut(speaker_id=l.speaker_id, full_name=l.speaker.full_name,
                                 designation=l.speaker.designation, organisation=l.speaker.organisation,
                                 status=l.speaker.status, role=l.role, photo_url=photo_url(l.speaker.id, l.speaker.photo_hash))
                for l in links],
        warnings=[Warning_(**w) for w in warnings], updated_at=s.updated_at)


def event_sessions_out(db: DB, event_id: int) -> list[SessionOut]:
    rows = load_sessions(db, event_id)
    conflicts = all_conflicts([slot_of(s) for s in rows])
    return [session_out(s, conflicts.get(s.id, [])) for s in rows]


def slot_from_input(db: DB, event: Event, data: SessionIn) -> Slot:
    """Builds the slot for a draft that is not saved yet (dry-run check)."""
    from ..models import Hall, Speaker
    hall = db.get(Hall, data.hall_id) if data.hall_id and not data.is_merged else None
    names = {}
    for p in data.people:
        sp = db.get(Speaker, p.speaker_id)
        if sp and sp.event_id == event.id:
            names[sp.id] = sp.full_name
    return Slot(id=data.id, day_id=data.day_id, hall_id=hall.id if hall else None, hall_name=hall.name if hall else "",
                is_merged=data.is_merged, title=data.title.strip() or "This session", session_type=data.session_type.value,
                start=data.start_time, end=data.end_time, speakers=names)
