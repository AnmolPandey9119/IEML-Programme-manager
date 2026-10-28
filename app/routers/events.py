from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session as DB

from ..database import get_db
from ..deps import EventCtx, event_ctx, get_current_user
from ..models import (APP_PENDING, Event, EventDay, EventMember, EventStatus, Group, Role, Session, Speaker,
                      SpeakerApplication, User)
from ..schemas import EventCreate, EventOut, EventSummary, EventUpdate

router = APIRouter(prefix="/api/events", tags=["events"])


def day_label(n: int, d) -> str:
    return f"Day {n} — {d.strftime('%A')}, {d.strftime('%b')} {d.day}"


def event_out(event: Event, role: Role, db: DB | None = None) -> EventOut:
    out = EventOut.model_validate(event)
    out.my_role = role
    if db is not None:
        count = lambda model: db.scalar(select(func.count(model.id)).where(model.event_id == event.id)) or 0
        out.counts = {"sessions": count(Session), "speakers": count(Speaker), "groups": count(Group),
                      "pending_applications": db.scalar(select(func.count(SpeakerApplication.id)).where(
                          SpeakerApplication.event_id == event.id, SpeakerApplication.status == APP_PENDING)) or 0}
    return out


@router.post("", response_model=EventOut, status_code=201)
def create_event(data: EventCreate, user: User = Depends(get_current_user), db: DB = Depends(get_db)):
    """Koi bhi logged-in user event bana sakta hai aur us event ka Admin ban jata hai."""
    if (data.start_date is None) != (data.end_date is None):
        raise HTTPException(400, "Provide both start_date and end_date, or neither")
    if data.start_date and data.end_date:
        if data.end_date < data.start_date:
            raise HTTPException(400, "End date cannot be before start date")
        if (data.end_date - data.start_date).days >= 60:
            raise HTTPException(400, "An event can span at most 60 days")
    event = Event(**data.model_dump(exclude={"start_date", "end_date"}))
    db.add(event)
    db.flush()
    db.add(EventMember(event_id=event.id, user_id=user.id, role=Role.admin))
    if data.start_date and data.end_date:
        for i in range((data.end_date - data.start_date).days + 1):
            d = data.start_date + timedelta(days=i)
            db.add(EventDay(event_id=event.id, day_date=d, label=day_label(i + 1, d)))
    db.commit()
    db.refresh(event)
    return event_out(event, Role.admin, db)


@router.get("", response_model=list[EventSummary])
def list_events(user: User = Depends(get_current_user), db: DB = Depends(get_db)):
    rows = db.execute(
        select(Event, EventMember.role)
        .join(EventMember, EventMember.event_id == Event.id)
        .where(EventMember.user_id == user.id)
        .order_by(Event.created_at.desc(), Event.id.desc())
    ).all()
    spans = {eid: (a, b) for eid, a, b in db.execute(
        select(EventDay.event_id, func.min(EventDay.day_date), func.max(EventDay.day_date)).group_by(EventDay.event_id))}
    return [EventSummary(id=e.id, name=e.name, edition=e.edition, venue_name=e.venue_name, venue_city=e.venue_city,
                         status=e.status, my_role=r, start_date=spans.get(e.id, (None, None))[0],
                         end_date=spans.get(e.id, (None, None))[1]) for e, r in rows]


@router.get("/{event_id}", response_model=EventOut)
def get_event(ctx: EventCtx = Depends(event_ctx(Role.viewer))):
    return event_out(ctx.event, ctx.member.role, ctx.db)


@router.patch("/{event_id}", response_model=EventOut)
def update_event(data: EventUpdate, ctx: EventCtx = Depends(event_ctx(Role.admin))):
    changes = {k: v for k, v in data.model_dump(exclude_unset=True).items() if v is not None}
    # Archived event mein sirf status badal sakte hain (wapas Active/Draft karne ke liye)
    if ctx.event.status == EventStatus.archived and set(changes) - {"status"}:
        raise HTTPException(403, "This event is archived (read-only). Change its status first.")
    for k, v in changes.items():
        setattr(ctx.event, k, v)
    ctx.db.commit()
    ctx.db.refresh(ctx.event)
    return event_out(ctx.event, ctx.member.role, ctx.db)


@router.delete("/{event_id}", status_code=204)
def delete_event(ctx: EventCtx = Depends(event_ctx(Role.admin))):
    ctx.db.delete(ctx.event)
    ctx.db.commit()