from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select

from ..config import settings
from ..deps import EventCtx, event_ctx
from ..emailer import render_html, send_email
from ..timeutil import utcnow
from ..models import (EventMember, EventNotificationSetting, Invitation, NotificationType, Role, User)
from ..schemas import (InviteIn, InviteOut, MemberOut, MemberUpdate, NotifSettingIn, NotifSettingOut)

router = APIRouter(prefix="/api/events/{event_id}", tags=["team"])
admin = event_ctx(Role.admin)  # team/settings changes archived event mein bhi admin kar sakta hai


def _member_out(m: EventMember) -> MemberOut:
    return MemberOut(id=m.id, user_id=m.user_id, email=m.user.email, full_name=m.user.full_name,
                     role=m.role, receive_notifications=m.receive_notifications)


def _admin_count(ctx: EventCtx) -> int:
    return ctx.db.scalar(select(func.count(EventMember.id)).where(
        EventMember.event_id == ctx.event.id, EventMember.role == Role.admin))


def _get_member(ctx: EventCtx, member_id: int) -> EventMember:
    m = ctx.db.get(EventMember, member_id)
    if not m or m.event_id != ctx.event.id:
        raise HTTPException(404, "Team member not found")
    return m


@router.get("/members", response_model=list[MemberOut])
def list_members(ctx: EventCtx = Depends(event_ctx(Role.viewer))):
    rows = ctx.db.scalars(select(EventMember).where(EventMember.event_id == ctx.event.id)
                          .order_by(EventMember.id)).all()
    return [_member_out(m) for m in rows]


@router.patch("/members/{member_id}", response_model=MemberOut)
def update_member(member_id: int, data: MemberUpdate, ctx: EventCtx = Depends(admin)):
    m = _get_member(ctx, member_id)
    if data.role is not None and data.role != m.role:
        if m.role == Role.admin and _admin_count(ctx) <= 1:
            raise HTTPException(400, "An event needs at least one admin")
        m.role = data.role
    if data.receive_notifications is not None:
        m.receive_notifications = data.receive_notifications
    ctx.db.commit()
    return _member_out(m)


@router.delete("/members/{member_id}", status_code=204)
def remove_member(member_id: int, ctx: EventCtx = Depends(admin)):
    m = _get_member(ctx, member_id)
    if m.role == Role.admin and _admin_count(ctx) <= 1:
        raise HTTPException(400, "An event needs at least one admin")
    ctx.db.delete(m)
    ctx.db.commit()


# ---------------- invitations
def _invite_out(inv: Invitation, sent: bool = False) -> InviteOut:
    return InviteOut(id=inv.id, email=inv.email, role=inv.role, expires_at=inv.expires_at,
                     link=f"{settings.FRONTEND_URL.rstrip('/')}/#/invite/{inv.token}", email_sent=sent)


@router.post("/invitations", response_model=InviteOut, status_code=201)
def invite(data: InviteIn, ctx: EventCtx = Depends(admin)):
    email = data.email.strip().lower()
    # Admin ka invite hi allow-list hai, isliye domain restriction yahan nahi lagti
    already = ctx.db.scalar(select(EventMember.id).join(User, User.id == EventMember.user_id).where(
        EventMember.event_id == ctx.event.id, User.email == email))
    if already:
        raise HTTPException(409, "This person is already on the team")
    # Same email ka purana pending invite replace ho jata hai (duplicate nahi)
    for old in ctx.db.scalars(select(Invitation).where(
            Invitation.event_id == ctx.event.id, Invitation.email == email,
            Invitation.accepted_at.is_(None))):
        ctx.db.delete(old)
    inv = Invitation(event_id=ctx.event.id, email=email, role=data.role, invited_by_id=ctx.user.id,
                     expires_at=utcnow() + timedelta(days=settings.INVITE_EXPIRE_DAYS))
    ctx.db.add(inv)
    ctx.db.commit()
    link = _invite_out(inv).link
    who = ctx.user.full_name or ctx.user.email
    lines = [f"{who} has invited you to join the team for {ctx.event.name} as {data.role.value.title()}.",
             f"This invitation link expires in {settings.INVITE_EXPIRE_DAYS} days."]
    sent = send_email(email, f"You are invited to {ctx.event.name}", "\n\n".join(lines) + f"\n\nAccept: {link}",
                      render_html("You are invited", lines, ("Accept invitation", link)))
    return _invite_out(inv, sent)


@router.get("/invitations", response_model=list[InviteOut])
def pending_invites(ctx: EventCtx = Depends(admin)):
    rows = ctx.db.scalars(select(Invitation).where(
        Invitation.event_id == ctx.event.id, Invitation.accepted_at.is_(None),
        Invitation.expires_at > utcnow()).order_by(Invitation.id)).all()
    return [_invite_out(i) for i in rows]


@router.delete("/invitations/{invite_id}", status_code=204)
def revoke_invite(invite_id: int, ctx: EventCtx = Depends(admin)):
    inv = ctx.db.get(Invitation, invite_id)
    if not inv or inv.event_id != ctx.event.id:
        raise HTTPException(404, "Invitation not found")
    ctx.db.delete(inv)
    ctx.db.commit()


# ---------------- notification settings (per event, per type)
@router.get("/notification-settings", response_model=list[NotifSettingOut])
def get_notification_settings(ctx: EventCtx = Depends(event_ctx(Role.viewer))):
    saved = {s.type: s.enabled for s in ctx.event.notification_settings}
    return [NotifSettingOut(type=t, enabled=saved.get(t, True)) for t in NotificationType]


@router.put("/notification-settings", response_model=list[NotifSettingOut])
def set_notification_setting(data: NotifSettingIn, ctx: EventCtx = Depends(admin)):
    row = next((s for s in ctx.event.notification_settings if s.type == data.type), None)
    if row:
        row.enabled = data.enabled
    else:
        ctx.db.add(EventNotificationSetting(event_id=ctx.event.id, type=data.type, enabled=data.enabled))
    ctx.db.commit()
    ctx.db.refresh(ctx.event)
    return get_notification_settings(ctx)