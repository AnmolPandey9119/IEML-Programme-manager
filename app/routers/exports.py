"""Exports (Section 4.6, 5.3, 6.3). Read-only, so every role including Viewer may export."""
import re
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Response

from ..deps import EventCtx, event_ctx
from ..exports import data, excel, pdf_docs, word
from ..models import Role
from ..exports.data import AgendaOpts

router = APIRouter(prefix="/api/events/{event_id}/export", tags=["exports"])
viewer = event_ctx(Role.viewer)

PDF, DOCX, XLSX = ("application/pdf",
                   "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                   "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


def _slug(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-").lower() or "export"


def _send(body: bytes, mime: str, ev, what: str, ext: str) -> Response:
    name = f"{_slug(data.event_title(ev))}-{_slug(what)}.{ext}"
    return Response(body, media_type=mime, headers={
        "Content-Disposition": f"attachment; filename=\"{name}\"; filename*=UTF-8''{quote(name)}",
        "Cache-Control": "no-store"})


def _opts(writeups: bool, subtopics: bool, drafts: bool, notes: bool) -> AgendaOpts:
    return AgendaOpts(writeups=writeups, subtopics=subtopics, drafts=drafts, notes=notes)


# ---------------------------------------------------------------- sessions
@router.get("/agenda.pdf")
def agenda_pdf(writeups: bool = True, subtopics: bool = True, drafts: bool = False, notes: bool = False,
               ctx: EventCtx = Depends(viewer)):
    o = _opts(writeups, subtopics, drafts, notes)
    return _send(pdf_docs.agenda_pdf(ctx.event, data.agenda_data(ctx.db, ctx.event, o), o), PDF, ctx.event, "agenda", "pdf")


@router.get("/agenda.docx")
def agenda_docx(writeups: bool = True, subtopics: bool = True, drafts: bool = False, notes: bool = False,
                ctx: EventCtx = Depends(viewer)):
    o = _opts(writeups, subtopics, drafts, notes)
    return _send(word.agenda_docx(ctx.event, data.agenda_data(ctx.db, ctx.event, o), o), DOCX, ctx.event, "agenda", "docx")


@router.get("/runsheet.pdf")
def runsheet_pdf(drafts: bool = False, ctx: EventCtx = Depends(viewer)):
    days = data.agenda_data(ctx.db, ctx.event, AgendaOpts(writeups=False, subtopics=False, drafts=drafts, notes=False))
    return _send(pdf_docs.runsheet_pdf(ctx.event, days), PDF, ctx.event, "speaker-runsheet", "pdf")


# ---------------------------------------------------------------- speakers
@router.get("/speakers.pdf")
def speakers_pdf(confirmed_only: bool = False, ctx: EventCtx = Depends(viewer)):
    rows = [data.speaker_dict(s) for s in data.load_speakers(ctx.db, ctx.event, confirmed_only)]
    return _send(pdf_docs.speakers_pdf(ctx.event, rows, confirmed_only), PDF, ctx.event, "speakers", "pdf")


@router.get("/speakers.xlsx")
def speakers_xlsx(confirmed_only: bool = False, ctx: EventCtx = Depends(viewer)):
    rows = [data.speaker_dict(s, with_photo=False) for s in data.load_speakers(ctx.db, ctx.event, confirmed_only)]
    return _send(excel.speakers_xlsx(rows), XLSX, ctx.event, "speakers", "xlsx")


@router.get("/speakers/{speaker_id}.pdf")
def speaker_profile(speaker_id: int, ctx: EventCtx = Depends(viewer)):
    sp = next((s for s in data.load_speakers(ctx.db, ctx.event) if s.id == speaker_id), None)
    if not sp:
        raise HTTPException(404, "Speaker not found")
    return _send(pdf_docs.speaker_profile_pdf(ctx.event, data.speaker_dict(sp)), PDF, ctx.event, f"profile-{sp.full_name}", "pdf")


# ---------------------------------------------------------------- groups & meetings
def _group(ctx: EventCtx, gid: int):
    g = data.load_group_full(ctx.db, ctx.event, gid)
    if not g:
        raise HTTPException(404, "Group not found")
    return g


@router.get("/groups/{gid}/members.pdf")
def members_pdf(gid: int, ctx: EventCtx = Depends(viewer)):
    g = _group(ctx, gid)
    return _send(pdf_docs.members_pdf(ctx.event, g), PDF, ctx.event, f"{g.name}-members", "pdf")


@router.get("/groups/{gid}/members.xlsx")
def members_xlsx(gid: int, ctx: EventCtx = Depends(viewer)):
    g = _group(ctx, gid)
    return _send(excel.members_xlsx(g), XLSX, ctx.event, f"{g.name}-members", "xlsx")


@router.get("/groups/{gid}/schedule.pdf")
def schedule_pdf(gid: int, ctx: EventCtx = Depends(viewer)):
    g = _group(ctx, gid)
    return _send(pdf_docs.schedule_pdf(ctx.event, g), PDF, ctx.event, f"{g.name}-meeting-schedule", "pdf")


@router.get("/groups/{gid}/meetings/{mid}.pdf")
def meeting_record(gid: int, mid: int, ctx: EventCtx = Depends(viewer)):
    g = _group(ctx, gid)
    m = next((x for x in g.meetings if x.id == mid), None)
    if not m:
        raise HTTPException(404, "Meeting not found")
    return _send(pdf_docs.meeting_pdf(ctx.event, g, m), PDF, ctx.event, f"{g.name}-{m.title}-record", "pdf")
