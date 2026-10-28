import hashlib
import io

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Response, UploadFile
from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import select
from sqlalchemy.orm import Session as DB, selectinload

from ..config import settings
from ..database import get_db
from ..deps import EventCtx, event_ctx
from ..models import NotificationType, Role, Session, SessionSpeaker, Speaker, SpeakerStatus
from ..notify import send_team_email, team_recipients
from ..schemas import SpeakerCreate, SpeakerOut, SpeakerUpdate
from ..security import photo_signature
from ..services.speakers import sort_name, speaker_out, speaker_sessions
from ..timeutil import fmt_time

router = APIRouter(prefix="/api/events/{event_id}/speakers", tags=["speakers"])
media = APIRouter(prefix="/api/media", tags=["media"])
editor_write = event_ctx(Role.editor, write=True)
admin_write = event_ctx(Role.admin, write=True)

_EAGER = (selectinload(Speaker.session_links).selectinload(SessionSpeaker.session).selectinload(Session.day),
          selectinload(Speaker.session_links).selectinload(SessionSpeaker.session).selectinload(Session.hall))


def _get(ctx: EventCtx, speaker_id: int) -> Speaker:
    sp = ctx.db.scalar(select(Speaker).options(*_EAGER).where(
        Speaker.id == speaker_id, Speaker.event_id == ctx.event.id))
    if not sp:
        raise HTTPException(404, "Speaker not found")
    return sp


@router.get("", response_model=list[SpeakerOut])
def list_speakers(q: str = "", status: SpeakerStatus | None = None,
                  ctx: EventCtx = Depends(event_ctx(Role.viewer))):
    stmt = select(Speaker).options(*_EAGER).where(Speaker.event_id == ctx.event.id)
    if status:
        stmt = stmt.where(Speaker.status == status)
    rows = ctx.db.scalars(stmt).all()
    if q.strip():
        needle = q.strip().lower()
        rows = [s for s in rows if needle in f"{s.full_name} {s.organisation} {s.designation}".lower()]
    return [speaker_out(s) for s in sorted(rows, key=lambda s: sort_name(s.full_name))]


def _confirmation_email(ctx: EventCtx, sp: Speaker, bg: BackgroundTasks) -> int:
    """Section 5.2: the moment a speaker becomes Confirmed, the whole team is told."""
    recipients = team_recipients(ctx.db, ctx.event.id, NotificationType.speaker_confirmed)
    if not recipients:
        return 0
    who = sp.full_name + (f", {sp.designation}" if sp.designation else "") + (f" at {sp.organisation}" if sp.organisation else "")
    lines = [f"{who} has confirmed participation."]
    refs = speaker_sessions(sp)
    if refs:
        for r in refs:
            lines.append(f"{r.role.title()} in \"{r.title}\" on {r.day_label}, {fmt_time(r.start_time)} to "
                         f"{fmt_time(r.end_time)} ({r.hall}).")
    else:
        lines.append("This speaker is not assigned to a session yet.")
    lines.append(f"Status changed by {ctx.user.full_name or ctx.user.email}.")
    bg.add_task(send_team_email, recipients, ctx.event.name, f"{sp.full_name} confirmed",
                "Speaker confirmed", lines)
    return len(recipients)


@router.post("", response_model=SpeakerOut, status_code=201)
def create_speaker(data: SpeakerCreate, bg: BackgroundTasks, ctx: EventCtx = Depends(editor_write)):
    fields = data.model_dump()
    fields["full_name"] = fields["full_name"].strip()
    sp = Speaker(event_id=ctx.event.id, **fields)
    ctx.db.add(sp)
    ctx.db.commit()
    sp = _get(ctx, sp.id)
    notified = _confirmation_email(ctx, sp, bg) if sp.status == SpeakerStatus.confirmed else None
    return speaker_out(sp, notified)


@router.get("/{speaker_id}", response_model=SpeakerOut)
def get_speaker(speaker_id: int, ctx: EventCtx = Depends(event_ctx(Role.viewer))):
    return speaker_out(_get(ctx, speaker_id))


@router.patch("/{speaker_id}", response_model=SpeakerOut)
def update_speaker(speaker_id: int, data: SpeakerUpdate, bg: BackgroundTasks,
                   ctx: EventCtx = Depends(editor_write)):
    sp = _get(ctx, speaker_id)
    before = sp.status
    changes = data.model_dump(exclude_unset=True)
    if "full_name" in changes:
        changes["full_name"] = (changes["full_name"] or "").strip()
        if not changes["full_name"]:
            raise HTTPException(422, "Full name is required")
    for k, v in changes.items():
        if v is not None:
            setattr(sp, k, v)
    ctx.db.commit()
    ctx.db.refresh(sp)
    notified = None
    if before != SpeakerStatus.confirmed and sp.status == SpeakerStatus.confirmed:
        notified = _confirmation_email(ctx, sp, bg)
    return speaker_out(sp, notified)


@router.delete("/{speaker_id}", status_code=204)
def delete_speaker(speaker_id: int, ctx: EventCtx = Depends(admin_write)):
    sp = _get(ctx, speaker_id)
    ctx.db.delete(sp)
    ctx.db.commit()


# ---------------------------------------------------------------- photo
MAX_SIDE = 800


def _process_photo(raw: bytes) -> bytes:
    Image.MAX_IMAGE_PIXELS = 40_000_000
    try:
        img = Image.open(io.BytesIO(raw))
        if img.format not in ("JPEG", "PNG"):
            raise HTTPException(415, "Please upload a JPG or PNG image")
        img = ImageOps.exif_transpose(img)
        if img.mode in ("RGBA", "LA", "P"):
            img = img.convert("RGBA")
            bg = Image.new("RGB", img.size, (255, 255, 255))
            bg.paste(img, mask=img.split()[-1])
            img = bg
        else:
            img = img.convert("RGB")
    except HTTPException:
        raise
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError):
        raise HTTPException(415, "This file is not a readable JPG or PNG image")
    img.thumbnail((MAX_SIDE, MAX_SIDE))
    out = io.BytesIO()
    img.save(out, "JPEG", quality=88, optimize=True)
    return out.getvalue()


@router.post("/{speaker_id}/photo", response_model=SpeakerOut)
async def upload_photo(speaker_id: int, file: UploadFile = File(...), ctx: EventCtx = Depends(editor_write)):
    sp = _get(ctx, speaker_id)
    limit = settings.MAX_PHOTO_MB * 1024 * 1024
    raw = await file.read(limit + 1)
    if len(raw) > limit:
        raise HTTPException(413, f"The photo is larger than {settings.MAX_PHOTO_MB} MB")
    data = _process_photo(raw)
    sp.photo_data = data
    sp.photo_hash = hashlib.sha1(data).hexdigest()[:16]
    ctx.db.commit()
    ctx.db.refresh(sp)
    return speaker_out(sp)


@router.delete("/{speaker_id}/photo", response_model=SpeakerOut)
def remove_photo(speaker_id: int, ctx: EventCtx = Depends(editor_write)):
    sp = _get(ctx, speaker_id)
    sp.photo_data = None
    sp.photo_hash = ""
    ctx.db.commit()
    ctx.db.refresh(sp)
    return speaker_out(sp)


@media.get("/speaker/{speaker_id}/{photo_hash}/{sig}")
def serve_photo(speaker_id: int, photo_hash: str, sig: str, db: DB = Depends(get_db)):
    if sig != photo_signature(speaker_id, photo_hash):
        raise HTTPException(404, "Not found")
    sp = db.get(Speaker, speaker_id)
    if not sp or sp.photo_hash != photo_hash or not sp.photo_data:
        raise HTTPException(404, "Not found")
    return Response(sp.photo_data, media_type="image/jpeg",
                    headers={"Cache-Control": "public, max-age=31536000, immutable"})
