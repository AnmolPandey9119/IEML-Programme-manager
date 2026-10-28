import secrets

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session as DB, selectinload

from ..database import get_db
from ..deps import EventCtx, event_ctx
from ..models import (Attendance, Event, EventStatus, Group, GroupMember, Meeting, MeetingAttendance, Role, Speaker)
from ..schemas import (AttendanceIn, GroupDetail, GroupIn, GroupOut, GroupUpdate, MeetingIn, MeetingOut, MemberIn,
                       GroupMemberOut, OrderIn, PersonSuggestion, ShareIn, ShareOut)
from ..services.groups import group_detail, group_out, load_group, meeting_out, writable

router = APIRouter(prefix="/api/events/{event_id}", tags=["lists & meetings"])
public = APIRouter(prefix="/api/public", tags=["public"])
editor_write = event_ctx(Role.editor, write=True)
admin_write = event_ctx(Role.admin, write=True)
viewer = event_ctx(Role.viewer)


def _is_admin(ctx: EventCtx) -> bool:
    return ctx.member.role == Role.admin


def _detail(ctx: EventCtx, gid: int) -> GroupDetail:
    return group_detail(load_group(ctx.db, ctx.event.id, gid), _is_admin(ctx))


# ---------------------------------------------------------------- groups
@router.get("/groups", response_model=list[GroupOut])
def list_groups(archived: bool = False, ctx: EventCtx = Depends(viewer)):
    rows = ctx.db.scalars(select(Group).where(Group.event_id == ctx.event.id, Group.archived.is_(archived)).options(
        selectinload(Group.members), selectinload(Group.meetings)).order_by(Group.id)).all()
    return [group_out(g, _is_admin(ctx)) for g in rows]


@router.post("/groups", response_model=GroupDetail, status_code=201)
def create_group(data: GroupIn, ctx: EventCtx = Depends(editor_write)):
    g = Group(event_id=ctx.event.id, name=data.name.strip(), group_type=data.group_type)
    ctx.db.add(g)
    ctx.db.commit()
    return _detail(ctx, g.id)


@router.get("/groups/{gid}", response_model=GroupDetail)
def get_group(gid: int, ctx: EventCtx = Depends(viewer)):
    return _detail(ctx, gid)


@router.patch("/groups/{gid}", response_model=GroupDetail)
def update_group(gid: int, data: GroupUpdate, ctx: EventCtx = Depends(editor_write)):
    g = load_group(ctx.db, ctx.event.id, gid)
    changes = data.model_dump(exclude_unset=True)
    if g.archived and set(changes) - {"archived"}:
        writable(g)
    if changes.get("name") is not None:
        g.name = changes["name"].strip()
    if changes.get("group_type") is not None:
        g.group_type = changes["group_type"]
    if changes.get("archived") is not None:
        g.archived = changes["archived"]
    ctx.db.commit()
    return _detail(ctx, gid)


@router.delete("/groups/{gid}", status_code=204)
def delete_group(gid: int, ctx: EventCtx = Depends(admin_write)):
    ctx.db.delete(load_group(ctx.db, ctx.event.id, gid))
    ctx.db.commit()


# ---------------------------------------------------------------- sharing (read-only member list)
@router.put("/groups/{gid}/share", response_model=ShareOut)
def set_share(gid: int, data: ShareIn, ctx: EventCtx = Depends(admin_write)):
    g = load_group(ctx.db, ctx.event.id, gid)
    if data.enabled:
        g.share_token = g.share_token or secrets.token_urlsafe(24)
        g.share_include_contacts = data.include_contacts
    else:
        g.share_token = None
        g.share_include_contacts = False
    ctx.db.commit()
    return ShareOut(enabled=bool(g.share_token), token=g.share_token, include_contacts=g.share_include_contacts)


@router.post("/groups/{gid}/share/renew", response_model=ShareOut)
def renew_share(gid: int, ctx: EventCtx = Depends(admin_write)):
    """Issues a new link and invalidates the old one."""
    g = load_group(ctx.db, ctx.event.id, gid)
    g.share_token = secrets.token_urlsafe(24)
    ctx.db.commit()
    return ShareOut(enabled=True, token=g.share_token, include_contacts=g.share_include_contacts)


@public.get("/groups/{token}")
def shared_group(token: str, db: DB = Depends(get_db)):
    g = db.scalar(select(Group).where(Group.share_token == token).options(selectinload(Group.members)))
    if not g or g.archived:
        raise HTTPException(404, "This link is not available")
    event = db.get(Event, g.event_id)
    rows = []
    for m in g.members:
        row = {"name": m.name, "designation": m.designation, "organisation": m.organisation, "role_in_group": m.role_in_group}
        if g.share_include_contacts:
            row.update(email=m.email, phone=m.phone)
        rows.append(row)
    return {"event_name": f"{event.name} {event.edition}".strip(), "group_name": g.name, "group_type": g.group_type.value,
            "include_contacts": g.share_include_contacts, "members": rows}


# ---------------------------------------------------------------- members
def _member(ctx: EventCtx, g: Group, mid: int) -> GroupMember:
    m = next((x for x in g.members if x.id == mid), None)
    if not m:
        raise HTTPException(404, "Member not found")
    return m


@router.post("/groups/{gid}/members", response_model=GroupDetail, status_code=201)
def add_member(gid: int, data: MemberIn, ctx: EventCtx = Depends(editor_write)):
    g = load_group(ctx.db, ctx.event.id, gid)
    writable(g)
    pos = max([m.position for m in g.members], default=-1) + 1
    ctx.db.add(GroupMember(group_id=g.id, position=pos, **{**data.model_dump(), "name": data.name.strip()}))
    ctx.db.commit()
    return _detail(ctx, gid)


@router.put("/groups/{gid}/members/order", response_model=GroupDetail)
def reorder_members(gid: int, data: OrderIn, ctx: EventCtx = Depends(editor_write)):
    g = load_group(ctx.db, ctx.event.id, gid)
    writable(g)
    by_id = {m.id: m for m in g.members}
    if sorted(data.ids) != sorted(by_id):
        raise HTTPException(400, "ids must contain every member of this group exactly once")
    for i, mid in enumerate(data.ids):
        by_id[mid].position = i
    ctx.db.commit()
    return _detail(ctx, gid)


@router.patch("/groups/{gid}/members/{mid}", response_model=GroupDetail)
def update_member(gid: int, mid: int, data: MemberIn, ctx: EventCtx = Depends(editor_write)):
    g = load_group(ctx.db, ctx.event.id, gid)
    writable(g)
    m = _member(ctx, g, mid)
    for k, v in {**data.model_dump(), "name": data.name.strip()}.items():
        setattr(m, k, v)
    ctx.db.commit()
    return _detail(ctx, gid)


@router.delete("/groups/{gid}/members/{mid}", response_model=GroupDetail)
def remove_member(gid: int, mid: int, ctx: EventCtx = Depends(admin_write)):
    g = load_group(ctx.db, ctx.event.id, gid)
    writable(g)
    ctx.db.delete(_member(ctx, g, mid))
    ctx.db.commit()
    return _detail(ctx, gid)


@router.get("/people", response_model=list[PersonSuggestion])
def people(q: str = "", ctx: EventCtx = Depends(viewer)):
    """Existing people in this event (other groups and the speaker directory), so nobody is retyped."""
    needle = q.strip().lower()
    out: dict[str, PersonSuggestion] = {}
    members = ctx.db.scalars(select(GroupMember).join(Group).where(Group.event_id == ctx.event.id)).all()
    for m in members:
        out.setdefault(m.name.lower() + "|" + m.email.lower(), PersonSuggestion(
            name=m.name, designation=m.designation, organisation=m.organisation, email=m.email, phone=m.phone, source="Committees"))
    for s in ctx.db.scalars(select(Speaker).where(Speaker.event_id == ctx.event.id)):
        out.setdefault(s.full_name.lower() + "|" + s.email.lower(), PersonSuggestion(
            name=s.full_name, designation=s.designation, organisation=s.organisation, email=s.email, phone=s.phone, source="Speakers"))
    rows = [p for p in out.values() if not needle or needle in f"{p.name} {p.organisation}".lower()]
    return sorted(rows, key=lambda p: p.name.lower())[:8]


# ---------------------------------------------------------------- meetings
def _meeting(g: Group, mtg_id: int) -> Meeting:
    m = next((x for x in g.meetings if x.id == mtg_id), None)
    if not m:
        raise HTTPException(404, "Meeting not found")
    return m


@router.post("/groups/{gid}/meetings", response_model=GroupDetail, status_code=201)
def add_meeting(gid: int, data: MeetingIn, ctx: EventCtx = Depends(editor_write)):
    g = load_group(ctx.db, ctx.event.id, gid)
    writable(g)
    ctx.db.add(Meeting(group_id=g.id, **data.model_dump()))
    ctx.db.commit()
    return _detail(ctx, gid)


@router.patch("/groups/{gid}/meetings/{mid}", response_model=GroupDetail)
def update_meeting(gid: int, mid: int, data: MeetingIn, ctx: EventCtx = Depends(editor_write)):
    g = load_group(ctx.db, ctx.event.id, gid)
    writable(g)
    m = _meeting(g, mid)
    for k, v in data.model_dump().items():
        setattr(m, k, v)
    ctx.db.commit()
    return _detail(ctx, gid)


@router.put("/groups/{gid}/meetings/{mid}/attendance", response_model=GroupDetail)
def mark_attendance(gid: int, mid: int, data: AttendanceIn, ctx: EventCtx = Depends(editor_write)):
    g = load_group(ctx.db, ctx.event.id, gid)
    writable(g)
    m = _meeting(g, mid)
    member_ids = {x.id for x in g.members}
    existing = {a.member_id: a for a in m.attendance}
    for member_id, status in data.marks.items():
        if member_id not in member_ids:
            raise HTTPException(422, "Attendance can only be marked for members of this group")
        if member_id in existing:
            existing[member_id].status = status
        else:
            ctx.db.add(MeetingAttendance(meeting_id=m.id, member_id=member_id, status=status))
    ctx.db.commit()
    return _detail(ctx, gid)


@router.delete("/groups/{gid}/meetings/{mid}", response_model=GroupDetail)
def delete_meeting(gid: int, mid: int, ctx: EventCtx = Depends(admin_write)):
    g = load_group(ctx.db, ctx.event.id, gid)
    writable(g)
    ctx.db.delete(_meeting(g, mid))
    ctx.db.commit()
    return _detail(ctx, gid)
