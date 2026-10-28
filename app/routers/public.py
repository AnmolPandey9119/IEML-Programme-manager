"""Public, read-only programme API (Section 7). No login. Only Published sessions and Confirmed speakers."""
import hashlib
import json

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session as DB

from ..config import settings
from ..database import get_db
from ..models import Event, EventStatus, PublishStatus, SpeakerStatus
from ..security import photo_url
from ..services.sessions import load_sessions, type_label
from ..timeutil import fmt_time, utcnow

router = APIRouter(prefix="/api/public", tags=["public website"])


def public_base(request: Request) -> str:
    f = settings.FRONTEND_URL.rstrip("/")
    return f if f and "localhost" not in f and "127.0.0.1" not in f else str(request.base_url).rstrip("/")


def _live_event(db: DB, key: str) -> Event:
    ev = db.scalar(select(Event).where(Event.public_key == key))
    # Draft events are team-only. Active is live. Archived stays readable so the website keeps its programme.
    if not ev or ev.status == EventStatus.draft:
        raise HTTPException(404, "This programme is not available")
    return ev


def build_agenda(db: DB, ev: Event, base: str, day: int | None = None, hall: int | None = None) -> dict:
    sessions = [s for s in load_sessions(db, ev.id) if s.status == PublishStatus.published]
    venue = ev.venue_name or "All halls"
    days = []
    for d in ev.days:
        if day and d.id != day:
            continue
        rows = []
        for s in sessions:
            if s.day_id != d.id or (hall and not s.is_merged and s.hall_id != hall):
                continue
            people = []
            for l in sorted(s.speaker_links, key=lambda l: ({"moderator": 0}.get(l.role.value, 1), l.position, l.id)):
                sp = l.speaker
                if sp.status != SpeakerStatus.confirmed:
                    continue  # speakers appear on the website only when confirmed
                people.append({"id": sp.id, "name": sp.full_name, "designation": sp.designation, "organisation": sp.organisation,
                               "bio": sp.bio, "role": l.role.value, "linkedin_url": sp.linkedin_url, "website_url": sp.website_url,
                               "photo_url": (base + photo_url(sp.id, sp.photo_hash)) if sp.photo_hash else ""})
            rows.append({
                "id": s.id, "title": s.title, "type": type_label(s), "writeup": s.writeup,
                "subtopics": [t.text for t in s.subtopics],
                "start_time": s.start_time.strftime("%H:%M"), "end_time": s.end_time.strftime("%H:%M"),
                "start_label": fmt_time(s.start_time), "end_label": fmt_time(s.end_time),
                "hall": venue if s.is_merged else (s.hall.name if s.hall else ""), "is_merged": s.is_merged,
                "speakers": people,
            })
        days.append({"id": d.id, "label": d.label, "date": d.day_date.isoformat(), "sessions": rows})
    return {
        "event": {"name": ev.name, "edition": ev.edition, "venue_name": ev.venue_name, "venue_city": ev.venue_city,
                  "theme_line": ev.theme_line, "website_url": ev.website_url},
        "halls": [{"id": h.id, "name": h.name} for h in ev.halls],
        "days": days,
    }


@router.get("/events/{key}/agenda")
def agenda(key: str, request: Request, response: Response, day: int | None = None, hall: int | None = None,
           db: DB = Depends(get_db)):
    ev = _live_event(db, key)
    data = build_agenda(db, ev, public_base(request), day, hall)
    body = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
    etag = '"' + hashlib.sha1(body.encode()).hexdigest()[:20] + '"'
    headers = {"ETag": etag, "Cache-Control": "public, max-age=5, must-revalidate"}  # +15 s polling => well inside 30 s
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=headers)
    return Response(body, media_type="application/json", headers=headers)
