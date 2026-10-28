from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select

from ..deps import EventCtx, event_ctx
from ..models import EventDay, Hall, Role, Session
from ..schemas import DayIn, DayOut, DayUpdate, HallIn, HallOrder, HallOut
from .events import day_label

router = APIRouter(prefix="/api/events/{event_id}", tags=["event setup"])
admin_write = event_ctx(Role.admin, write=True)


def _own(ctx: EventCtx, model, obj_id: int):
    obj = ctx.db.get(model, obj_id)
    if not obj or obj.event_id != ctx.event.id:
        raise HTTPException(404, f"{model.__name__} not found")
    return obj


# ---------------- days
def _date_taken(ctx: EventCtx, d, ignore_id=None) -> bool:
    q = select(EventDay.id).where(EventDay.event_id == ctx.event.id, EventDay.day_date == d)
    found = ctx.db.scalar(q)
    return found is not None and found != ignore_id


@router.post("/days", response_model=DayOut, status_code=201)
def add_day(data: DayIn, ctx: EventCtx = Depends(admin_write)):
    if _date_taken(ctx, data.day_date):
        raise HTTPException(409, "A day with this date already exists")
    n = ctx.db.scalar(select(func.count(EventDay.id)).where(EventDay.event_id == ctx.event.id)) + 1
    day = EventDay(event_id=ctx.event.id, day_date=data.day_date,
                   label=(data.label or "").strip() or day_label(n, data.day_date))
    ctx.db.add(day)
    ctx.db.commit()
    return day


@router.patch("/days/{day_id}", response_model=DayOut)
def update_day(day_id: int, data: DayUpdate, ctx: EventCtx = Depends(admin_write)):
    day = _own(ctx, EventDay, day_id)
    if data.day_date is not None:
        if _date_taken(ctx, data.day_date, ignore_id=day.id):
            raise HTTPException(409, "A day with this date already exists")
        day.day_date = data.day_date  # sessions day_id se jude hain, isliye wahin rehte hain
    if data.label is not None:
        day.label = data.label.strip()
    ctx.db.commit()
    return day


@router.delete("/days/{day_id}", status_code=204)
def delete_day(day_id: int, ctx: EventCtx = Depends(admin_write)):
    day = _own(ctx, EventDay, day_id)
    if ctx.db.scalar(select(func.count(Session.id)).where(Session.day_id == day.id)):
        raise HTTPException(409, "This day still has sessions. Move or delete them first.")
    ctx.db.delete(day)
    ctx.db.commit()


# ---------------- halls
@router.post("/halls", response_model=HallOut, status_code=201)
def add_hall(data: HallIn, ctx: EventCtx = Depends(admin_write)):
    name = data.name.strip()
    dup = ctx.db.scalar(select(Hall.id).where(
        Hall.event_id == ctx.event.id, func.lower(Hall.name) == name.lower()))
    if dup:
        raise HTTPException(409, "A hall with this name already exists")
    pos = (ctx.db.scalar(select(func.max(Hall.position)).where(Hall.event_id == ctx.event.id)) or 0) + 1
    hall = Hall(event_id=ctx.event.id, name=name, position=pos)
    ctx.db.add(hall)
    ctx.db.commit()
    return hall


@router.put("/halls/order", response_model=list[HallOut])
def reorder_halls(data: HallOrder, ctx: EventCtx = Depends(admin_write)):
    halls = {h.id: h for h in ctx.event.halls}
    if sorted(data.ids) != sorted(halls):
        raise HTTPException(400, "ids must contain every hall of this event exactly once")
    for i, hid in enumerate(data.ids):
        halls[hid].position = i
    ctx.db.commit()
    return [halls[i] for i in data.ids]


@router.patch("/halls/{hall_id}", response_model=HallOut)
def rename_hall(hall_id: int, data: HallIn, ctx: EventCtx = Depends(admin_write)):
    hall = _own(ctx, Hall, hall_id)
    name = data.name.strip()
    dup = ctx.db.scalar(select(Hall.id).where(
        Hall.event_id == ctx.event.id, func.lower(Hall.name) == name.lower(), Hall.id != hall.id))
    if dup:
        raise HTTPException(409, "A hall with this name already exists")
    hall.name = name
    ctx.db.commit()
    return hall


@router.delete("/halls/{hall_id}", status_code=204)
def delete_hall(hall_id: int, ctx: EventCtx = Depends(admin_write)):
    hall = _own(ctx, Hall, hall_id)
    if ctx.db.scalar(select(func.count(Session.id)).where(Session.hall_id == hall.id)):
        raise HTTPException(409, "Sessions are assigned to this hall. Reassign them first.")
    ctx.db.delete(hall)
    ctx.db.commit()
