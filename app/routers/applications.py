"""Speaker invitations, the public speaker form, and the team's review of what comes back.

Flow: admin invites speakers (personal link by email) -> speaker fills the public form (no login)
-> application lands in the Speaker Invites tab as Pending -> admin approves (creates / links a Speaker)
or rejects -> admin assigns the speaker to a session. Nothing here touches the public website:
speakers appear there only once their status is Confirmed, exactly as before.
"""
import logging
import secrets
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session as DB

from ..config import settings
from ..database import SessionLocal, get_db
from ..deps import EventCtx, event_ctx
from ..emailer import render_html, send_email
from ..models import (APP_APPROVED, APP_PENDING, APP_REJECTED, Event, EventMember, EventStatus, Role, Speaker,
                      SpeakerApplication, SpeakerInvite, SpeakerStatus)
from ..schemas import (FORMAT_CHOICES, ApplicationOut, ApproveIn, InvitesCreate, SpeakerInviteOut, InvitesResult,
                       PublicFormIn, PublicFormOut, RejectIn, SpeakerLinkIn, SpeakerLinkOut)
from ..services.speakers import speaker_sessions
from .sessions import add_person
from .speakers import _confirmation_email, _get as _speaker_row

log = logging.getLogger("applications")

router = APIRouter(prefix="/api/events/{event_id}", tags=["speaker invites"])
public = APIRouter(prefix="/api/public/speaker-form", tags=["speaker form"])
viewer = event_ctx(Role.viewer)
admin_write = event_ctx(Role.admin, write=True)

_FIELDS = ("full_name", "designation", "organisation", "email", "phone", "city_country", "bio", "linkedin_url",
           "website_url", "expertise", "topics", "proposed_title", "abstract", "key_takeaways", "past_speaking",
           "requirements", "extra_notes")


def _base(request: Request | None = None) -> str:
    f = settings.FRONTEND_URL.rstrip("/")
    if f and "localhost" not in f and "127.0.0.1" not in f:
        return f
    return str(request.base_url).rstrip("/") if request else f


def _link(token: str, request: Request | None = None) -> str:
    return f"{_base(request)}/#/speaker-form/{token}"


def _split(s: str) -> list[str]:
    return [x.strip() for x in (s or "").split("||") if x.strip()]


def _join(items: list[str], limit: int = 500) -> str:
    return "||".join(dict.fromkeys(x.strip() for x in items if x.strip()))[:limit]


# ---------------------------------------------------------------- invitations (team side)
def _spk_invite_out(inv: SpeakerInvite, app: SpeakerApplication | None, request: Request | None = None) -> SpeakerInviteOut:
    return SpeakerInviteOut(id=inv.id, name=inv.name, email=inv.email, token=inv.token, link=_link(inv.token, request),
                     created_at=inv.created_at, last_sent_at=inv.last_sent_at, email_sent=inv.email_sent,
                     submitted=app is not None, application_id=app.id if app else None,
                     application_status=app.status if app else None)


def _apps_by_invite(db: DB, event_id: int) -> dict[int, SpeakerApplication]:
    rows = db.scalars(select(SpeakerApplication).where(
        SpeakerApplication.event_id == event_id, SpeakerApplication.invite_id.is_not(None))).all()
    return {a.invite_id: a for a in rows}


def _deliver_invites(invite_ids: list[int], event_name: str, event_link_name: str, sender: str, base: str) -> None:
    """Runs after the response is sent, with its own DB session (the request session is closed by then)."""
    with SessionLocal() as db:
        for iid in invite_ids:
            inv = db.get(SpeakerInvite, iid)
            if not inv or not inv.email:
                continue
            link = f"{base}/#/speaker-form/{inv.token}"
            hello = f"Dear {inv.name}," if inv.name else "Hello,"
            lines = [hello, f"We would be glad to have you as a speaker at {event_link_name}.",
                     "Please take five minutes to tell us about yourself, your expertise and what you would like to speak on."]
            if inv.message:
                lines.append(inv.message)
            lines.append("No account or password is needed. The link below is personal to you.")
            text = "\n\n".join(lines) + f"\n\nOpen the speaker form: {link}"
            ok = send_email(inv.email, f"Speaker invitation: {event_name}", text,
                            render_html(f"Speaker invitation: {event_name}", lines, ("Open the speaker form", link),
                                        footer=f"Sent by {sender} on behalf of the {event_name} team."))
            inv.email_sent = ok
            inv.last_sent_at = datetime.utcnow() if ok else inv.last_sent_at
        db.commit()


@router.get("/speaker-invites", response_model=list[SpeakerInviteOut])
def list_invites(request: Request, ctx: EventCtx = Depends(viewer)):
    apps = _apps_by_invite(ctx.db, ctx.event.id)
    rows = ctx.db.scalars(select(SpeakerInvite).where(SpeakerInvite.event_id == ctx.event.id)
                          .order_by(SpeakerInvite.id.desc())).all()
    return [_spk_invite_out(i, apps.get(i.id), request) for i in rows]


@router.post("/speaker-invites", response_model=InvitesResult, status_code=201)
def create_invites(data: InvitesCreate, request: Request, bg: BackgroundTasks, ctx: EventCtx = Depends(admin_write)):
    db, ev = ctx.db, ctx.event
    existing = {i.email.lower(): i for i in db.scalars(select(SpeakerInvite).where(SpeakerInvite.event_id == ev.id))}
    made, skipped = [], []
    for p in data.invitees:
        email = p.email.strip().lower()
        if not email:
            skipped.append(p.name or "(no email)")
            continue
        inv = existing.get(email)
        if inv:  # same person invited twice: keep their link, refresh the note
            inv.name = p.name.strip() or inv.name
            inv.message = data.message.strip() or inv.message
        else:
            inv = SpeakerInvite(event_id=ev.id, name=p.name.strip(), email=email, message=data.message.strip(),
                                invited_by_id=ctx.user.id)
            db.add(inv)
            existing[email] = inv
        made.append(inv)
    db.commit()
    for i in made:
        db.refresh(i)  # server-side created_at is only filled in after a refresh
    ids = [i.id for i in made]
    queued = 0
    if data.send_email and ids:  # without SMTP the email is only logged (development), and `emailed` stays 0
        bg.add_task(_deliver_invites, ids, ev.name, f"{ev.name} {ev.edition}".strip(),
                    ctx.user.full_name or ctx.user.email, _base(request))
        queued = len(ids) if settings.SMTP_HOST else 0
    apps = _apps_by_invite(db, ev.id)
    return InvitesResult(invites=[_spk_invite_out(i, apps.get(i.id), request) for i in made], emailed=queued, skipped=skipped)


@router.post("/speaker-invites/{invite_id}/resend", response_model=SpeakerInviteOut)
def resend_invite(invite_id: int, request: Request, bg: BackgroundTasks, ctx: EventCtx = Depends(admin_write)):
    inv = ctx.db.get(SpeakerInvite, invite_id)
    if not inv or inv.event_id != ctx.event.id:
        raise HTTPException(404, "Invitation not found")
    bg.add_task(_deliver_invites, [inv.id], ctx.event.name, f"{ctx.event.name} {ctx.event.edition}".strip(),
                ctx.user.full_name or ctx.user.email, _base(request))
    return _spk_invite_out(inv, _apps_by_invite(ctx.db, ctx.event.id).get(inv.id), request)


@router.delete("/speaker-invites/{invite_id}", status_code=204)
def delete_invite(invite_id: int, ctx: EventCtx = Depends(admin_write)):
    """Deleting an invitation switches its link off. A response already received is kept."""
    inv = ctx.db.get(SpeakerInvite, invite_id)
    if not inv or inv.event_id != ctx.event.id:
        raise HTTPException(404, "Invitation not found")
    ctx.db.delete(inv)
    ctx.db.commit()


# ---------------------------------------------------------------- shared "invite by link" (team side)
def _open_link(token: str, request: Request | None = None) -> str:
    return f"{_base(request)}/#/speaker-form/open/{token}"


def _link_out(ev: Event, request: Request | None = None) -> SpeakerLinkOut:
    t = ev.speaker_form_token
    return SpeakerLinkOut(enabled=bool(t), token=t, link=_open_link(t, request) if t else None)


@router.get("/speaker-form-link", response_model=SpeakerLinkOut)
def get_form_link(request: Request, ctx: EventCtx = Depends(event_ctx(Role.admin))):
    return _link_out(ctx.event, request)


@router.put("/speaker-form-link", response_model=SpeakerLinkOut)
def set_form_link(data: SpeakerLinkIn, request: Request, ctx: EventCtx = Depends(admin_write)):
    """Switch the shared link on (keeps the same address if it already exists) or off."""
    ev = ctx.event
    ev.speaker_form_token = (ev.speaker_form_token or secrets.token_urlsafe(24)) if data.enabled else None
    ctx.db.commit()
    return _link_out(ev, request)


@router.post("/speaker-form-link/renew", response_model=SpeakerLinkOut)
def renew_form_link(request: Request, ctx: EventCtx = Depends(admin_write)):
    """A new address. The old one stops working, for example if the link was shared too widely."""
    ctx.event.speaker_form_token = secrets.token_urlsafe(24)
    ctx.db.commit()
    return _link_out(ctx.event, request)


# ---------------------------------------------------------------- applications (team side)
def _app_out(ctx_db: DB, a: SpeakerApplication, sessions=None, speaker_status=None) -> ApplicationOut:
    return ApplicationOut(
        id=a.id, status=a.status, full_name=a.full_name, designation=a.designation, organisation=a.organisation,
        email=a.email, phone=a.phone, city_country=a.city_country, bio=a.bio, linkedin_url=a.linkedin_url,
        website_url=a.website_url, expertise=a.expertise, topics=a.topics, proposed_title=a.proposed_title,
        abstract=a.abstract, key_takeaways=a.key_takeaways, formats=_split(a.formats), past_speaking=a.past_speaking,
        availability=_split(a.availability), requirements=a.requirements, extra_notes=a.extra_notes,
        review_note=a.review_note, submitted_at=a.submitted_at, reviewed_at=a.reviewed_at, speaker_id=a.speaker_id,
        invited=a.invite_id is not None, sessions=sessions or [], speaker_status=speaker_status)


def _app_full(ctx: EventCtx, a: SpeakerApplication) -> ApplicationOut:
    if a.speaker_id:
        try:
            sp = _speaker_row(ctx, a.speaker_id)
            return _app_out(ctx.db, a, speaker_sessions(sp), sp.status.value)
        except HTTPException:  # speaker was deleted from the Speakers tab meanwhile
            a.speaker_id = None
            ctx.db.commit()
    return _app_out(ctx.db, a)


def _own_app(ctx: EventCtx, app_id: int) -> SpeakerApplication:
    a = ctx.db.get(SpeakerApplication, app_id)
    if not a or a.event_id != ctx.event.id:
        raise HTTPException(404, "Response not found")
    return a


@router.get("/speaker-applications", response_model=list[ApplicationOut])
def list_applications(status: str = "", ctx: EventCtx = Depends(viewer)):
    stmt = select(SpeakerApplication).where(SpeakerApplication.event_id == ctx.event.id)
    if status:
        stmt = stmt.where(SpeakerApplication.status == status)
    rows = ctx.db.scalars(stmt.order_by(SpeakerApplication.submitted_at.desc(), SpeakerApplication.id.desc())).all()
    return [_app_out(ctx.db, a) for a in rows]


@router.get("/speaker-applications/{app_id}", response_model=ApplicationOut)
def get_application(app_id: int, ctx: EventCtx = Depends(viewer)):
    return _app_full(ctx, _own_app(ctx, app_id))


def _internal_summary(a: SpeakerApplication) -> str:
    parts = []
    for label, v in (("Expertise", a.expertise), ("Wants to speak on", a.topics), ("Proposed title", a.proposed_title),
                     ("Requirements", a.requirements)):
        if v.strip():
            parts.append(f"{label}: {v.strip()}")
    return ("From the speaker form.\n" + "\n".join(parts))[:5000]


@router.post("/speaker-applications/{app_id}/approve", response_model=ApplicationOut)
def approve(app_id: int, data: ApproveIn, bg: BackgroundTasks, ctx: EventCtx = Depends(admin_write)):
    """Adds the person to the Speakers directory (or links an existing speaker with the same email)."""
    db, ev = ctx.db, ctx.event
    a = _own_app(ctx, app_id)
    if a.status == APP_APPROVED and a.speaker_id:
        raise HTTPException(409, "This response is already approved")
    sp = None
    if a.email:
        sp = db.scalar(select(Speaker).where(Speaker.event_id == ev.id, Speaker.email == a.email))
    created = sp is None
    before = sp.status if sp else None
    if created:
        sp = Speaker(event_id=ev.id, full_name=a.full_name, designation=a.designation, organisation=a.organisation,
                     bio=a.bio, email=a.email, phone=a.phone, linkedin_url=a.linkedin_url, website_url=a.website_url,
                     status=data.speaker_status, status_remark=data.note.strip() or "Applied through the speaker form",
                     internal_notes=_internal_summary(a))
        db.add(sp)
        db.flush()
    else:  # already in the directory: keep their record, only move the status if the admin chose a different one
        sp.status = data.speaker_status
        if data.note.strip():
            sp.status_remark = data.note.strip()
    a.speaker_id = sp.id
    a.status = APP_APPROVED
    a.review_note = data.note.strip()
    a.reviewed_by_id, a.reviewed_at = ctx.user.id, datetime.utcnow()
    db.commit()
    sp = _speaker_row(ctx, sp.id)
    if sp.status == SpeakerStatus.confirmed and (created or before != SpeakerStatus.confirmed):
        _confirmation_email(ctx, sp, bg)
    if data.session_id:
        add_person(ctx, data.session_id, sp.id, data.role, bg)
    return _app_full(ctx, a)


@router.post("/speaker-applications/{app_id}/reject", response_model=ApplicationOut)
def reject(app_id: int, data: RejectIn, ctx: EventCtx = Depends(admin_write)):
    a = _own_app(ctx, app_id)
    if a.status == APP_APPROVED:
        raise HTTPException(409, "This speaker is already added. To remove them, delete the speaker in the Speakers tab.")
    a.status = APP_REJECTED
    a.review_note = data.note.strip()
    a.reviewed_by_id, a.reviewed_at = ctx.user.id, datetime.utcnow()
    ctx.db.commit()
    return _app_out(ctx.db, a)


@router.post("/speaker-applications/{app_id}/restore", response_model=ApplicationOut)
def restore(app_id: int, ctx: EventCtx = Depends(admin_write)):
    a = _own_app(ctx, app_id)
    if a.status != APP_REJECTED:
        raise HTTPException(409, "Only a rejected response can be moved back to pending")
    a.status, a.reviewed_at, a.reviewed_by_id = APP_PENDING, None, None
    ctx.db.commit()
    return _app_out(ctx.db, a)


@router.delete("/speaker-applications/{app_id}", status_code=204)
def delete_application(app_id: int, ctx: EventCtx = Depends(admin_write)):
    ctx.db.delete(_own_app(ctx, app_id))
    ctx.db.commit()


# ---------------------------------------------------------------- the public form (speaker side, no login)
def _invite_by_token(db: DB, token: str) -> tuple[SpeakerInvite, Event]:
    inv = db.scalar(select(SpeakerInvite).where(SpeakerInvite.token == token))
    ev = db.get(Event, inv.event_id) if inv else None
    if not inv or not ev:
        raise HTTPException(404, "This invitation link is not available")
    return inv, ev


def _values(a: SpeakerApplication) -> dict:
    v = {k: getattr(a, k) for k in _FIELDS}
    v["formats"], v["availability"] = _split(a.formats), _split(a.availability)
    return v


def _form_out(ev: Event, status: str, inv: SpeakerInvite | None = None, app: SpeakerApplication | None = None) -> PublicFormOut:
    return PublicFormOut(
        event_name=ev.name, edition=ev.edition, venue=", ".join(x for x in (ev.venue_name, ev.venue_city) if x),
        theme_line=ev.theme_line, days=[d.label for d in ev.days], formats=FORMAT_CHOICES,
        invitee_name=inv.name if inv else "", invitee_email=inv.email if inv else "", message=inv.message if inv else "",
        status=status, values=_values(app) if app else None)


@public.get("/open/{token}", response_model=PublicFormOut)
def open_form_info(token: str, db: DB = Depends(get_db)):
    ev = _event_by_open_token(db, token)
    return _form_out(ev, "closed" if ev.status == EventStatus.archived else "open")


@public.get("/{token}", response_model=PublicFormOut)
def form_info(token: str, db: DB = Depends(get_db)):
    inv, ev = _invite_by_token(db, token)
    app = db.scalar(select(SpeakerApplication).where(SpeakerApplication.invite_id == inv.id))
    status = "closed" if ev.status == EventStatus.archived and not app else (app.status if app else "open")
    return _form_out(ev, status, inv, app)


def _event_by_open_token(db: DB, token: str) -> Event:
    ev = db.scalar(select(Event).where(Event.speaker_form_token == token))
    if not ev:
        raise HTTPException(404, "This link is not available")
    return ev


def _notify_team(event_id: int, app_id: int, base: str, updated: bool) -> None:
    with SessionLocal() as db:
        ev, a = db.get(Event, event_id), db.get(SpeakerApplication, app_id)
        if not ev or not a:
            return
        members = db.scalars(select(EventMember).where(EventMember.event_id == event_id,
                                                       EventMember.receive_notifications.is_(True))).all()
        to = [m.user.email for m in members if m.user.is_active and m.role in (Role.admin, Role.editor)]
        if not to:
            return
        who = a.full_name + (f", {a.designation}" if a.designation else "") + (f" ({a.organisation})" if a.organisation else "")
        lines = [f"{who} has {'updated' if updated else 'submitted'} the speaker form.",
                 f"Wants to speak on: {a.topics[:300]}" if a.topics else "No topic was given.",
                 "Open the Speaker Invites tab to review, add them to the speakers and assign a session."]
        link = f"{base}/#/event/{event_id}/invites"
        send_email(to, f"[{ev.name}] Speaker form received: {a.full_name}", "\n\n".join(lines) + f"\n\n{link}",
                   render_html("Speaker form received", lines, ("Review the response", link)))


def _save(db: DB, ev: Event, data: PublicFormIn, app: SpeakerApplication | None, invite_id: int | None,
          default_email: str, base: str, bg: BackgroundTasks) -> dict:
    fields = {k: (getattr(data, k) or "").strip() for k in _FIELDS}
    if not fields["full_name"]:
        raise HTTPException(422, "Please enter your full name")
    if not fields["email"]:
        fields["email"] = default_email
    if not fields["email"]:
        raise HTTPException(422, "Please enter your email address")
    fmts = [f for f in data.formats if f in FORMAT_CHOICES]
    days = [d for d in data.availability if d in {x.label for x in ev.days}]
    updated = app is not None
    if app:
        for k, v in fields.items():
            setattr(app, k, v)
        app.formats, app.availability = _join(fmts), _join(days)
    else:
        app = SpeakerApplication(event_id=ev.id, invite_id=invite_id, formats=_join(fmts), availability=_join(days), **fields)
        db.add(app)
    db.commit()
    bg.add_task(_notify_team, ev.id, app.id, base, updated)
    return {"ok": True, "updated": updated}


def _check_submit(data: PublicFormIn) -> bool:
    """False = a bot filled the hidden field (pretend it worked, store nothing)."""
    if data.hp:
        return False
    if not data.consent:
        raise HTTPException(422, "Please tick the box to confirm your details can be used for the event programme")
    return True


@public.post("/open/{token}", status_code=201)
def submit_open_form(token: str, data: PublicFormIn, request: Request, bg: BackgroundTasks, db: DB = Depends(get_db)):
    ev = _event_by_open_token(db, token)
    if not _check_submit(data):
        return {"ok": True}
    if ev.status == EventStatus.archived:
        raise HTTPException(409, "This event is closed")
    email = (data.email or "").strip().lower()
    app = None
    if email:  # the same person sending twice through the shared link updates their response while it is pending
        app = db.scalar(select(SpeakerApplication).where(
            SpeakerApplication.event_id == ev.id, SpeakerApplication.invite_id.is_(None),
            SpeakerApplication.email == email))
        if app and app.status != APP_PENDING:
            raise HTTPException(409, "We already have a response from this email address. Please contact the team for changes.")
    return _save(db, ev, data, app, None, "", _base(request), bg)


@public.post("/{token}", status_code=201)
def submit_form(token: str, data: PublicFormIn, request: Request, bg: BackgroundTasks, db: DB = Depends(get_db)):
    inv, ev = _invite_by_token(db, token)
    if not _check_submit(data):
        return {"ok": True}
    app = db.scalar(select(SpeakerApplication).where(SpeakerApplication.invite_id == inv.id))
    if app and app.status != APP_PENDING:
        raise HTTPException(409, "Your response has already been reviewed by the team. Please contact them for changes.")
    if not app and ev.status == EventStatus.archived:
        raise HTTPException(409, "This event is closed")
    return _save(db, ev, data, app, inv.id, inv.email, _base(request), bg)