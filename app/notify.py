"""Team notifications (Section 8). Respects the per-event type switch and the per-person switch."""
from sqlalchemy import select
from sqlalchemy.orm import Session as DB

from .emailer import render_html, send_email
from .models import Event, EventMember, EventNotificationSetting, NotificationType


def notification_enabled(db: DB, event_id: int, ntype: NotificationType) -> bool:
    row = db.scalar(select(EventNotificationSetting).where(
        EventNotificationSetting.event_id == event_id, EventNotificationSetting.type == ntype))
    return True if row is None else row.enabled


def team_recipients(db: DB, event_id: int, ntype: NotificationType) -> list[str]:
    if not notification_enabled(db, event_id, ntype):
        return []
    members = db.scalars(select(EventMember).where(
        EventMember.event_id == event_id, EventMember.receive_notifications.is_(True))).all()
    return [m.user.email for m in members if m.user.is_active]


def send_team_email(recipients: list[str], event_name: str, subject: str, title: str, lines: list[str]) -> bool:
    text = "\n\n".join(lines) + f"\n\n(You receive this because you are on the team of {event_name}.)"
    return send_email(recipients, f"[{event_name}] {subject}", text,
                      render_html(title, lines, footer=f"You receive this because you are on the team of {event_name}."))
