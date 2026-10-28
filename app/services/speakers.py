import re

from sqlalchemy.orm import Session as DB

from ..models import Event, Speaker
from ..schemas import SpeakerOut, SpeakerSessionRef
from ..security import photo_url


def speaker_sessions(sp: Speaker, venue_name: str = "") -> list[SpeakerSessionRef]:
    refs = []
    for link in sp.session_links:
        s = link.session
        refs.append(SpeakerSessionRef(
            session_id=s.id, title=s.title, session_type=s.custom_type_label or s.session_type.value,
            day_id=s.day_id, day_label=s.day.label, day_date=s.day.day_date,
            start_time=s.start_time, end_time=s.end_time,
            hall="All halls" if s.is_merged else (s.hall.name if s.hall else "Hall to be confirmed"),
            role=link.role.value, status=s.status.value))
    refs.sort(key=lambda r: (r.day_date, r.start_time))
    return refs


def speaker_out(sp: Speaker, team_notified: int | None = None) -> SpeakerOut:
    return SpeakerOut(
        id=sp.id, full_name=sp.full_name, designation=sp.designation, organisation=sp.organisation,
        bio=sp.bio, email=sp.email, phone=sp.phone, linkedin_url=sp.linkedin_url,
        website_url=sp.website_url, status=sp.status, status_remark=sp.status_remark,
        internal_notes=sp.internal_notes, photo_url=photo_url(sp.id, sp.photo_hash),
        sessions=speaker_sessions(sp), team_notified=team_notified)


_TITLES = re.compile(r"^(?:(?:dr|prof|mr|mrs|ms|shri|smt|sri|er|ca|hon|h\.e\.)\.?\s+)+", re.I)


def sort_name(full_name: str) -> str:
    """Alphabetical order that ignores honorifics, so 'Dr. Ananya Rao' sorts under A."""
    return _TITLES.sub("", full_name.strip()).lower()
