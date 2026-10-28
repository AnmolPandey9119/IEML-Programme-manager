from datetime import date, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session as DB, selectinload

from ..models import Attendance, Group, GroupMember, Meeting, MeetingAttendance
from ..schemas import AttendanceRow, GroupDetail, GroupOut, MeetingOut, GroupMemberOut, ShareOut


def load_group(db: DB, event_id: int, group_id: int) -> Group:
    g = db.scalar(select(Group).where(Group.id == group_id, Group.event_id == event_id).options(
        selectinload(Group.members), selectinload(Group.meetings).selectinload(Meeting.attendance)
    ).execution_options(populate_existing=True))
    if not g:
        raise HTTPException(404, "Group not found")
    return g


def writable(g: Group) -> None:
    if g.archived:
        raise HTTPException(403, "This group is archived (read-only). Restore it to make changes.")


def end_of(m: Meeting):
    if m.start_time is None:
        return None
    total = m.start_time.hour * 60 + m.start_time.minute + m.duration_minutes
    return (datetime.combine(date.today(), m.start_time) + timedelta(minutes=m.duration_minutes)).time() if total < 24 * 60 else None


def meeting_out(g: Group, m: Meeting) -> MeetingOut:
    marks = {a.member_id: a.status for a in m.attendance}
    rows = [AttendanceRow(member_id=mem.id, name=mem.name, role_in_group=mem.role_in_group,
                          status=marks.get(mem.id, Attendance.unmarked)) for mem in g.members]
    return MeetingOut(id=m.id, title=m.title, meeting_date=m.meeting_date, start_time=m.start_time, end_time=end_of(m),
                      duration_minutes=m.duration_minutes, location=m.location, agenda=m.agenda, minutes=m.minutes,
                      status=m.status, attendance=rows)


def group_out(g: Group, with_token: bool) -> GroupOut:
    upcoming = [m.meeting_date for m in g.meetings if m.status.value == "Scheduled" and m.meeting_date >= date.today()]
    return GroupOut(id=g.id, name=g.name, group_type=g.group_type, archived=g.archived, member_count=len(g.members),
                    meeting_count=len(g.meetings), next_meeting=min(upcoming) if upcoming else None,
                    share=ShareOut(enabled=bool(g.share_token), token=g.share_token if with_token else None,
                                   include_contacts=g.share_include_contacts))


def group_detail(g: Group, with_token: bool) -> GroupDetail:
    base = group_out(g, with_token)
    meetings = sorted(g.meetings, key=lambda m: (m.meeting_date, m.start_time or datetime.min.time()))
    return GroupDetail(**base.model_dump(), members=[GroupMemberOut.model_validate(m, from_attributes=True) for m in g.members],
                       meetings=[meeting_out(g, m) for m in meetings])
