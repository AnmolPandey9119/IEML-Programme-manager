"""Every PDF document: agenda, runsheet, speaker list / profile, group members, meeting record and schedule."""
from datetime import date

from ..models import Event, Group, Meeting
from ..timeutil import fmt_date_long, fmt_duration, fmt_time
from .data import event_subtitle, event_title
from .pdfkit import (A4, Paragraph, Table, TableStyle, CondPageBreak, HRFlowable, KeepTogether, LINE, MUTED, P, S, SOFT, Spacer, BRAND, GOLD, banner, build,
                     esc, grid, initials_flowable, mm, photo_flowable, rich)

W = A4[0] - 36 * mm
ROLE_SHORT = {"moderator": "Mod.", "speaker": "Spkr.", "panelist": "Panel"}


def _cover(ev: Event, heading: str, note: str = "") -> list:
    out = [P(event_title(ev), "title"), Spacer(1, 2)]
    if event_subtitle(ev):
        out.append(P(event_subtitle(ev), "sub"))
    out += [Spacer(1, 8), rich(f"<b>{esc(heading)}</b>", "h2")]
    if note:
        out.append(P(note, "small"))
    out.append(Spacer(1, 6))
    return out


def _person_line(p: dict, show_status: bool = True) -> str:
    sub = ", ".join(x for x in (p["designation"], p["organisation"]) if x)
    tag = f' <font color="#9a4d12">({esc(p["status"])})</font>' if show_status and p["status"] != "Confirmed" else ""
    return f"<b>{esc(p['name'])}</b>{(', ' + esc(sub)) if sub else ''}{tag}"


# ---------------------------------------------------------------- agenda
def agenda_pdf(ev: Event, days: list[dict], opts) -> bytes:
    inc = [x for x, on in (("writeups", opts.writeups), ("sub-topics", opts.subtopics), ("draft sessions", opts.drafts),
                           ("internal notes", opts.notes)) if on]
    story = _cover(ev, "Programme agenda", "Includes: " + (", ".join(inc) if inc else "titles, times and speakers only") + ".")
    if opts.notes:
        story.insert(len(story) - 1, rich('<font color="#a8392b"><b>Contains internal notes. Do not share outside the team.</b></font>', "small"))
    for d in days:
        story += [CondPageBreak(60 * mm), banner(f"{d['label']}", W), Spacer(1, 6)]
        if not d["sessions"]:
            story += [P("No sessions scheduled for this day.", "small"), Spacer(1, 10)]
            continue
        for s in d["sessions"]:
            head = [rich(f"{esc(s['start'])} – {esc(s['end'])}"
                         f"{(' · ' + esc(s['duration'])) if s['duration'] else ''}  |  {esc(s['hall'])}  |  "
                         f"{esc(s['type']).upper()}{'  |  DRAFT' if s['draft'] else ''}", "meta"),
                    Spacer(1, 2), P(s["title"], "h")]
            body = []
            if s["writeup"]:
                body += [Spacer(1, 3), P(s["writeup"])]
            if s["subtopics"]:
                body += [Spacer(1, 3)] + [Paragraph(esc(t), S["bullet"], bulletText="•") for t in s["subtopics"]]
            for p in s["people"]:
                body.append(rich(f"<font color='#1d3f91'><b>{esc(p['role']).title()}</b></font>  {_person_line(p)}", "cell"))
            if s["notes"]:
                body += [Spacer(1, 3), rich(f"<font color='#a8392b'><b>Internal note:</b> {esc(s['notes'])}</font>", "small")]
            story += [KeepTogether(head + body[:3]), *body[3:], Spacer(1, 5),
                      HRFlowable(width="100%", thickness=0.4, color=LINE), Spacer(1, 6)]
    return build(story, f"{event_title(ev)} · Agenda", event_title(ev), "Programme agenda")



# ---------------------------------------------------------------- runsheet
def runsheet_pdf(ev: Event, days: list[dict]) -> bytes:
    story = _cover(ev, "Speaker runsheet", "For the on-ground team. Times, halls and everyone attached to each session.")
    for d in days:
        story += [CondPageBreak(50 * mm), banner(d["label"], W), Spacer(1, 4)]
        if not d["sessions"]:
            story += [P("No sessions scheduled for this day.", "small"), Spacer(1, 8)]
            continue
        rows = [[P(h, "th") for h in ("Time", "Hall", "Session", "Speakers · designation")]]
        for s in d["sessions"]:
            people = "<br/>".join(
                f"<font color='#1d3f91'>{ROLE_SHORT[p['role']]}</font> {_person_line(p)}" for p in s["people"]) or "—"
            rows.append([rich(f"<b>{esc(s['start'])}</b><br/>{esc(s['end'])}", "cell"), P("All halls" if s["merged"] else s["hall"], "cell"),
                         rich(f"<b>{esc(s['title'])}</b><br/><font color='#5a647f'>{esc(s['type'])}</font>", "cell"),
                         rich(people, "cell")])
        story += [grid(rows, [20 * mm, 28 * mm, 52 * mm, W - 100 * mm]), Spacer(1, 12)]
    return build(story, f"{event_title(ev)} · Runsheet", event_title(ev), "Speaker runsheet")


# ---------------------------------------------------------------- speakers
def _speaker_block(sp: dict, wide: bool = False):
    ph = photo_flowable(sp["photo"], 24 * mm) or initials_flowable(sp["name"], 24 * mm)
    sub = ", ".join(x for x in (sp["designation"], sp["organisation"]) if x)
    txt = [rich(f"<b>{esc(sp['name'])}</b>", "h")]
    if sub:
        txt.append(P(sub, "small"))
    txt.append(rich(f"<font color='#1d3f91'><b>{esc(sp['status'])}</b></font>"
                    f"{(' · ' + esc(sp['remark'])) if sp['remark'] else ''}", "small"))
    if sp["bio"]:
        txt += [Spacer(1, 3), P(sp["bio"][:3000])]
    links = " · ".join(x for x in (sp["linkedin"], sp["website"]) if x)
    if links:
        txt += [Spacer(1, 2), P(links, "small")]
    if sp["sessions"]:
        txt.append(Spacer(1, 4))
        for r in sp["sessions"]:
            txt.append(rich(f"<font color='#1d3f91'>{esc(r['role']).title()}</font> · {esc(r['title'])} "
                            f"<font color='#5a647f'>({esc(r['day'])}, {esc(r['start'])}, {esc(r['hall'])})</font>", "small"))
    return ph, txt


def speakers_pdf(ev: Event, speakers: list[dict], confirmed_only: bool) -> bytes:
    story = _cover(ev, "Speakers", f"{len(speakers)} {'confirmed speakers' if confirmed_only else 'speakers, all statuses'}. "
                                    "Contact details are not included in this document.")
    for sp in speakers:
        ph, txt = _speaker_block(sp)
        cell_photo = ph or P(" ")
        t = Table([[cell_photo, txt]], colWidths=[30 * mm, W - 30 * mm])
        t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE),
                               ("BOTTOMPADDING", (0, 0), (-1, -1), 9), ("TOPPADDING", (0, 0), (-1, -1), 8),
                               ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
        story.append(t)
    if not speakers:
        story.append(P("No speakers match this selection.", "small"))
    return build(story, f"{event_title(ev)} · Speakers", event_title(ev), "Speaker directory")


def speaker_profile_pdf(ev: Event, sp: dict) -> bytes:
    ph = photo_flowable(sp["photo"], 42 * mm) or initials_flowable(sp["name"], 42 * mm)
    sub = ", ".join(x for x in (sp["designation"], sp["organisation"]) if x)
    head = [P(sp["name"], "title"), Spacer(1, 3)] + ([P(sub, "sub")] if sub else [])
    t = Table([[ph or P(" "), head]], colWidths=[48 * mm, W - 48 * mm])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
    story = [P(event_title(ev).upper(), "meta"), Spacer(1, 8), t, Spacer(1, 12), HRFlowable(width="100%", color=GOLD, thickness=1.2), Spacer(1, 10)]
    if sp["bio"]:
        story += [P("About", "h2"), P(sp["bio"][:3500])]
    if sp["sessions"]:
        story.append(P("At this event", "h2"))
        for r in sp["sessions"]:
            story += [rich(f"<b>{esc(r['title'])}</b>", "body"),
                      rich(f"{esc(r['role']).title()} · {esc(r['day'])}, {esc(r['start'])} to {esc(r['end'])} · {esc(r['hall'])}", "small"), Spacer(1, 5)]
    links = [x for x in (sp["linkedin"], sp["website"]) if x]
    if links:
        story += [P("Online", "h2")] + [P(x, "body") for x in links]
    return build(story, f"{sp['name']} · {event_title(ev)}", event_title(ev), "Speaker profile")


# ---------------------------------------------------------------- groups & meetings
def members_pdf(ev: Event, g: Group) -> bytes:
    story = _cover(ev, f"{g.name}", f"{g.group_type.value} · {len(g.members)} members")
    rows = [[P(h, "th") for h in ("#", "Name", "Designation", "Organisation", "Role", "Contact")]]
    for i, m in enumerate(g.members, 1):
        contact = "<br/>".join(esc(x) for x in (m.email, m.phone) if x) or "—"
        rows.append([P(str(i), "cell"), rich(f"<b>{esc(m.name)}</b>", "cell"), P(m.designation, "cell"), P(m.organisation, "cell"),
                     P(m.role_in_group, "cell"), rich(contact, "cell")])
    story.append(grid(rows, [8 * mm, 36 * mm, 34 * mm, 34 * mm, 26 * mm, W - 138 * mm]))
    if not g.members:
        story.append(P("No members have been added yet.", "small"))
    return build(story, f"{g.name} · Members", event_title(ev), "Internal. Not for publication")


def _when(m: Meeting) -> str:
    parts = [fmt_date_long(m.meeting_date)]
    if m.start_time:
        parts.append(fmt_time(m.start_time))
    if m.duration_minutes:
        parts.append(fmt_duration(m.duration_minutes))
    return " · ".join(parts)


def meeting_pdf(ev: Event, g: Group, m: Meeting) -> bytes:
    story = _cover(ev, m.title, f"{g.name} · {g.group_type.value}")
    facts = [[P("When", "cellb"), P(_when(m), "cell")], [P("Location", "cellb"), P(m.location or "Not recorded", "cell")],
             [P("Status", "cellb"), P(m.status.value, "cell")]]
    story += [grid(facts, [28 * mm, W - 28 * mm], head=False), Spacer(1, 6), P("Agenda", "h2"),
              P(m.agenda or "No agenda was recorded.", "body"), P("Attendance", "h2")]
    marks = {a.member_id: a.status.value for a in m.attendance}
    label = {"attended": "Attended", "absent": "Absent", "apologies": "Apologies", "unmarked": "Not marked"}
    rows = [[P(h, "th") for h in ("Member", "Role", "Attendance")]]
    for mem in g.members:
        rows.append([rich(f"<b>{esc(mem.name)}</b>", "cell"), P(mem.role_in_group, "cell"), P(label[marks.get(mem.id, "unmarked")], "cell")])
    story.append(grid(rows, [60 * mm, 60 * mm, W - 120 * mm]))
    n = {k: sum(1 for mem in g.members if marks.get(mem.id, "unmarked") == k) for k in label}
    story += [Spacer(1, 3), P(f"{n['attended']} attended · {n['absent']} absent · {n['apologies']} apologies · {n['unmarked']} not marked", "small"),
              P("Minutes", "h2"), P(m.minutes or "No minutes have been recorded yet.", "body")]
    return build(story, f"{m.title} · Meeting record", event_title(ev), "Internal. Not for publication")


def schedule_pdf(ev: Event, g: Group) -> bytes:
    story = _cover(ev, f"{g.name}: meeting schedule", f"{len(g.meetings)} meetings")
    rows = [[P(h, "th") for h in ("Date", "Time", "Meeting", "Location", "Status")]]
    for m in sorted(g.meetings, key=lambda x: (x.meeting_date, x.start_time or fmt_min())):
        rows.append([P(m.meeting_date.strftime("%a, %d %b %Y"), "cell"),
                     P(f"{fmt_time(m.start_time)} ({fmt_duration(m.duration_minutes)})" if m.start_time else "To be confirmed", "cell"),
                     rich(f"<b>{esc(m.title)}</b>", "cell"), P(m.location, "cell"), P(m.status.value, "cell")])
    story.append(grid(rows, [30 * mm, 30 * mm, 50 * mm, 38 * mm, W - 148 * mm]))
    if not g.meetings:
        story.append(P("No meetings have been scheduled.", "small"))
    return build(story, f"{g.name} · Schedule", event_title(ev), "Internal. Not for publication")


def fmt_min():
    from datetime import time
    return time(0, 0)