"""Late change alert (Section 8): a session's time, hall or speakers change within 48 hours of the event day."""
from dataclasses import dataclass, field

from ..models import NotificationType, PublishStatus, Session
from ..notify import send_team_email, team_recipients
from ..timeutil import day_is_over, fmt_time, hours_until_day_start

WINDOW_HOURS = 48


@dataclass
class Snap:
    day_id: int
    day_label: str
    day_date: object
    start: object
    end: object
    hall: str
    people: dict[tuple[int, str], str] = field(default_factory=dict)  # (speaker_id, role) -> name
    published: bool = False


def snapshot(s: Session) -> Snap:
    return Snap(day_id=s.day_id, day_label=s.day.label, day_date=s.day.day_date, start=s.start_time, end=s.end_time,
                hall="All halls" if s.is_merged else (s.hall.name if s.hall else "Hall to be confirmed"),
                people={(l.speaker_id, l.role.value): l.speaker.full_name for l in s.speaker_links},
                published=s.status == PublishStatus.published)


def in_window(d) -> bool:
    return hours_until_day_start(d) <= WINDOW_HOURS and not day_is_over(d)


def describe(a: Snap, b: Snap) -> list[str]:
    lines = []
    if a.day_id != b.day_id:
        lines.append(f"Day: {a.day_label} to {b.day_label}")
    if (a.start, a.end) != (b.start, b.end):
        lines.append(f"Time: {fmt_time(a.start)} to {fmt_time(a.end)} changed to {fmt_time(b.start)} to {fmt_time(b.end)}")
    if a.hall != b.hall:
        lines.append(f"Hall: {a.hall} changed to {b.hall}")
    added = [n for k, n in b.people.items() if k not in a.people]
    removed = [n for k, n in a.people.items() if k not in b.people]
    if added:
        lines.append("Speakers added: " + ", ".join(added))
    if removed:
        lines.append("Speakers removed: " + ", ".join(removed))
    return lines


def notify_if_late(db, event, session: Session, before: Snap, after: Snap, actor: str, bg) -> int:
    """Queues the alert email. Returns the number of recipients (0 when nothing needs to be sent)."""
    if not (before.published or after.published):
        return 0
    if not (in_window(before.day_date) or in_window(after.day_date)):
        return 0
    changes = describe(before, after)
    if not changes:
        return 0
    recipients = team_recipients(db, event.id, NotificationType.late_change)
    if not recipients:
        return 0
    lines = [f"\"{session.title}\" on {after.day_label} was changed close to the event day.", *changes,
             f"Changed by {actor}. The public website already shows the updated programme."]
    bg.add_task(send_team_email, recipients, event.name, f"Late change: {session.title}", "Late schedule change", lines)
    return len(recipients)
