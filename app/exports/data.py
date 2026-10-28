"""Collects plain data for every export, so PDF / Word / Excel share one source of truth."""
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session as DB, selectinload

from ..models import Event, Group, Meeting, PublishStatus, Session, SessionSpeaker, Speaker, SpeakerStatus
from ..services.sessions import ROLE_ORDER, load_sessions, type_label
from ..services.speakers import sort_name, speaker_sessions
from ..timeutil import fmt_date_long, fmt_duration, fmt_time


@dataclass
class AgendaOpts:
    writeups: bool = True
    subtopics: bool = True
    drafts: bool = False
    notes: bool = False


def event_title(ev: Event) -> str:
    return f"{ev.name} {ev.edition}".strip()


def event_subtitle(ev: Event) -> str:
    return " · ".join(x for x in (ev.theme_line, ", ".join(x for x in (ev.venue_name, ev.venue_city) if x)) if x)


def _hall_label(ev: Event, s: Session) -> str:
    if s.is_merged:
        return f"All halls merged ({ev.venue_name})" if ev.venue_name else "All halls merged"
    return s.hall.name if s.hall else "Hall to be confirmed"


def _person(link: SessionSpeaker) -> dict:
    sp = link.speaker
    return {"name": sp.full_name, "designation": sp.designation, "organisation": sp.organisation,
            "role": link.role.value, "status": sp.status.value}


def agenda_data(db: DB, ev: Event, opts: AgendaOpts) -> list[dict]:
    """[{label, date, sessions:[...]}] in day order. Every day is independent (Section 4.2)."""
    rows = load_sessions(db, ev.id)
    out = []
    for d in ev.days:
        items = []
        for s in rows:
            if s.day_id != d.id or (not opts.drafts and s.status != PublishStatus.published):
                continue
            links = sorted(s.speaker_links, key=lambda l: (ROLE_ORDER.get(l.role.value, 1), l.position, l.id))
            mins = (s.end_time.hour * 60 + s.end_time.minute) - (s.start_time.hour * 60 + s.start_time.minute)
            items.append({
                "id": s.id, "title": s.title, "type": type_label(s), "hall": _hall_label(ev, s), "merged": s.is_merged,
                "start": fmt_time(s.start_time), "end": fmt_time(s.end_time),
                "duration": fmt_duration(mins) if mins > 0 else "",
                "draft": s.status != PublishStatus.published,
                "writeup": s.writeup if opts.writeups else "",
                "subtopics": [t.text for t in s.subtopics] if opts.subtopics else [],
                "notes": s.internal_notes if opts.notes else "",
                "people": [_person(l) for l in links],
            })
        out.append({"label": d.label, "date": fmt_date_long(d.day_date), "sessions": items})
    return out


def load_speakers(db: DB, ev: Event, confirmed_only: bool = False) -> list[Speaker]:
    stmt = select(Speaker).options(
        selectinload(Speaker.session_links).selectinload(SessionSpeaker.session).selectinload(Session.day),
        selectinload(Speaker.session_links).selectinload(SessionSpeaker.session).selectinload(Session.hall),
    ).where(Speaker.event_id == ev.id)
    if confirmed_only:
        stmt = stmt.where(Speaker.status == SpeakerStatus.confirmed)
    return sorted(db.scalars(stmt).all(), key=lambda s: sort_name(s.full_name))


def speaker_dict(sp: Speaker, with_photo: bool = True) -> dict:
    sess = [{"title": r.title, "role": r.role, "day": r.day_label, "start": fmt_time(r.start_time),
             "end": fmt_time(r.end_time), "hall": r.hall, "status": r.status} for r in speaker_sessions(sp)]
    return {"name": sp.full_name, "designation": sp.designation, "organisation": sp.organisation, "bio": sp.bio,
            "status": sp.status.value, "remark": sp.status_remark, "email": sp.email, "phone": sp.phone,
            "linkedin": sp.linkedin_url, "website": sp.website_url, "notes": sp.internal_notes,
            "photo": sp.photo_data if (with_photo and sp.photo_hash) else None, "has_photo": bool(sp.photo_hash),
            "sessions": sess}


def load_group_full(db: DB, ev: Event, gid: int) -> Group | None:
    return db.scalar(select(Group).where(Group.id == gid, Group.event_id == ev.id).options(
        selectinload(Group.members), selectinload(Group.meetings).selectinload(Meeting.attendance)))
