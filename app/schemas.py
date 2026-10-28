import re
from datetime import date, datetime, time
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, ConfigDict, EmailStr, Field

from .models import (Attendance, EventStatus, GroupType, MeetingStatus, NotificationType, PublishStatus, Role, SessionRole,
                     SessionType, SpeakerStatus)


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---- auth
class SetupIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    full_name: str = Field(min_length=1, max_length=200)


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(max_length=72)


class AcceptInviteIn(BaseModel):
    token: str
    password: str = Field(min_length=8, max_length=72)
    full_name: str = Field(default="", max_length=200)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(ORM):
    id: int
    email: str
    full_name: str


class InvitePreview(BaseModel):
    email: str
    event_name: str
    role: Role
    has_account: bool


# ---- events
class EventBase(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    edition: str = Field(default="", max_length=100)
    venue_name: str = Field(default="", max_length=255)
    venue_city: str = Field(default="", max_length=120)
    theme_line: str = Field(default="", max_length=500)
    website_url: str = Field(default="", max_length=500)


class EventCreate(EventBase):
    start_date: date | None = None
    end_date: date | None = None


class EventUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    edition: str | None = Field(default=None, max_length=100)
    venue_name: str | None = Field(default=None, max_length=255)
    venue_city: str | None = Field(default=None, max_length=120)
    theme_line: str | None = Field(default=None, max_length=500)
    website_url: str | None = Field(default=None, max_length=500)
    status: EventStatus | None = None


class DayIn(BaseModel):
    day_date: date
    label: str | None = Field(default=None, max_length=120)


class DayUpdate(BaseModel):
    day_date: date | None = None
    label: str | None = Field(default=None, min_length=1, max_length=120)


class DayOut(ORM):
    id: int
    day_date: date
    label: str


class HallIn(BaseModel):
    name: str = Field(min_length=1, max_length=150)


class HallOrder(BaseModel):
    ids: list[int]


class HallOut(ORM):
    id: int
    name: str
    position: int


class EventOut(EventBase, ORM):
    id: int
    status: EventStatus
    public_key: str
    days: list[DayOut]
    halls: list[HallOut]
    my_role: Role | None = None
    counts: dict[str, int] = {}


class EventSummary(BaseModel):
    id: int
    name: str
    edition: str
    venue_name: str = ""
    venue_city: str
    status: EventStatus
    my_role: Role
    start_date: date | None = None
    end_date: date | None = None


# ---- team
class MemberOut(BaseModel):
    id: int
    user_id: int
    email: str
    full_name: str
    role: Role
    receive_notifications: bool


class MemberUpdate(BaseModel):
    role: Role | None = None
    receive_notifications: bool | None = None


class InviteIn(BaseModel):
    email: EmailStr
    role: Role = Role.viewer


class InviteOut(BaseModel):
    id: int
    email: str
    role: Role
    expires_at: datetime
    link: str
    email_sent: bool = False


class NotifSettingOut(BaseModel):
    type: NotificationType
    enabled: bool


class NotifSettingIn(BaseModel):
    type: NotificationType
    enabled: bool


# ---- speakers
def _clean_url(v):
    v = (v or "").strip() if isinstance(v, str) else v
    if not v:
        return ""
    if not re.match(r"^https?://", v, re.I):
        v = "https://" + v
    if " " in v or "." not in v.split("//", 1)[1]:
        raise ValueError("Enter a valid web address")
    return v


def _clean_email(v):
    v = (v or "").strip() if isinstance(v, str) else v
    if not v:
        return ""
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", v):
        raise ValueError("Enter a valid email address")
    return v.lower()


Url = Annotated[str, BeforeValidator(_clean_url), Field(max_length=500)]
OptEmail = Annotated[str, BeforeValidator(_clean_email), Field(max_length=255)]


class SpeakerBase(BaseModel):
    full_name: str = Field(min_length=1, max_length=200)
    designation: str = Field(default="", max_length=255)
    organisation: str = Field(default="", max_length=255)
    bio: str = Field(default="", max_length=5000)
    email: OptEmail = ""
    phone: str = Field(default="", max_length=50)
    linkedin_url: Url = ""
    website_url: Url = ""
    status: SpeakerStatus = SpeakerStatus.invited
    status_remark: str = Field(default="", max_length=1000)
    internal_notes: str = Field(default="", max_length=5000)


class SpeakerCreate(SpeakerBase):
    pass


class SpeakerUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=200)
    designation: str | None = Field(default=None, max_length=255)
    organisation: str | None = Field(default=None, max_length=255)
    bio: str | None = Field(default=None, max_length=5000)
    email: OptEmail | None = None
    phone: str | None = Field(default=None, max_length=50)
    linkedin_url: Url | None = None
    website_url: Url | None = None
    status: SpeakerStatus | None = None
    status_remark: str | None = Field(default=None, max_length=1000)
    internal_notes: str | None = Field(default=None, max_length=5000)


class SpeakerSessionRef(BaseModel):
    session_id: int
    title: str
    session_type: str
    day_id: int
    day_label: str
    day_date: date
    start_time: time
    end_time: time
    hall: str
    role: str
    status: str


class SpeakerOut(BaseModel):
    id: int
    full_name: str
    designation: str
    organisation: str
    bio: str
    email: str
    phone: str
    linkedin_url: str
    website_url: str
    status: SpeakerStatus
    status_remark: str
    internal_notes: str
    photo_url: str
    sessions: list[SpeakerSessionRef]
    team_notified: int | None = None


# ---- sessions
class SessionPerson(BaseModel):
    speaker_id: int
    role: SessionRole = SessionRole.speaker


class SessionIn(BaseModel):
    day_id: int
    hall_id: int | None = None
    is_merged: bool = False
    title: str = Field(min_length=1, max_length=500)
    session_type: SessionType = SessionType.talk
    custom_type_label: str = Field(default="", max_length=120)
    writeup: str = Field(default="", max_length=8000)
    subtopics: list[str] = Field(default_factory=list, max_length=60)
    start_time: time
    end_time: time
    status: PublishStatus = PublishStatus.draft
    internal_notes: str = Field(default="", max_length=8000)
    people: list[SessionPerson] = Field(default_factory=list, max_length=60)
    # Only used by the dry-run check, to leave the session being edited out of its own comparison
    id: int | None = None


class Warning_(BaseModel):
    code: str
    level: str
    message: str
    session_ids: list[int] = []


class SessionPersonOut(BaseModel):
    speaker_id: int
    full_name: str
    designation: str
    organisation: str
    status: SpeakerStatus
    role: SessionRole
    photo_url: str


class SessionOut(BaseModel):
    id: int
    day_id: int
    day_label: str
    day_date: date
    hall_id: int | None
    hall_name: str
    is_merged: bool
    title: str
    session_type: SessionType
    custom_type_label: str
    type_label: str
    writeup: str
    subtopics: list[str]
    start_time: time
    end_time: time
    duration_minutes: int | None
    status: PublishStatus
    internal_notes: str
    people: list[SessionPersonOut]
    warnings: list[Warning_]
    updated_at: datetime | None = None


# ---- lists & meetings
class GroupIn(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    group_type: GroupType = GroupType.custom


class GroupUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    group_type: GroupType | None = None
    archived: bool | None = None


class MemberIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    designation: str = Field(default="", max_length=255)
    organisation: str = Field(default="", max_length=255)
    email: OptEmail = ""
    phone: str = Field(default="", max_length=50)
    role_in_group: str = Field(default="", max_length=150)
    notes: str = Field(default="", max_length=3000)


class GroupMemberOut(MemberIn):
    id: int
    position: int


class OrderIn(BaseModel):
    ids: list[int]


class MeetingIn(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    meeting_date: date
    start_time: time | None = None
    duration_minutes: int = Field(default=60, ge=5, le=720)
    location: str = Field(default="", max_length=300)
    agenda: str = Field(default="", max_length=10000)
    minutes: str = Field(default="", max_length=20000)
    status: MeetingStatus = MeetingStatus.scheduled


class AttendanceRow(BaseModel):
    member_id: int
    name: str
    role_in_group: str
    status: Attendance


class MeetingOut(BaseModel):
    id: int
    title: str
    meeting_date: date
    start_time: time | None
    end_time: time | None
    duration_minutes: int
    location: str
    agenda: str
    minutes: str
    status: MeetingStatus
    attendance: list[AttendanceRow]


class AttendanceIn(BaseModel):
    marks: dict[int, Attendance]


class ShareOut(BaseModel):
    enabled: bool
    token: str | None = None
    include_contacts: bool = False


class ShareIn(BaseModel):
    enabled: bool = True
    include_contacts: bool = False


class GroupOut(BaseModel):
    id: int
    name: str
    group_type: GroupType
    archived: bool
    member_count: int
    meeting_count: int
    next_meeting: date | None = None
    share: ShareOut


class GroupDetail(GroupOut):
    members: list[GroupMemberOut]
    meetings: list[MeetingOut]


class PersonSuggestion(BaseModel):
    name: str
    designation: str
    organisation: str
    email: str
    phone: str
    source: str


# ---- speaker invitations & applications
FORMAT_CHOICES = ["Keynote", "Panel Discussion", "Fireside Chat", "Talk / Address", "Workshop", "Roundtable", "Lightning Talk"]


class InviteeIn(BaseModel):
    name: str = Field(default="", max_length=200)
    email: OptEmail


class InvitesCreate(BaseModel):
    invitees: list[InviteeIn] = Field(min_length=1, max_length=100)
    message: str = Field(default="", max_length=2000)
    send_email: bool = True


class SpeakerInviteOut(BaseModel):
    id: int
    name: str
    email: str
    token: str
    link: str
    created_at: datetime
    last_sent_at: datetime | None
    email_sent: bool
    submitted: bool
    application_id: int | None
    application_status: str | None


class InvitesResult(BaseModel):
    invites: list[SpeakerInviteOut]
    emailed: int
    skipped: list[str] = []


class ApplicationFields(BaseModel):
    full_name: str = Field(min_length=1, max_length=200)
    designation: str = Field(default="", max_length=255)
    organisation: str = Field(default="", max_length=255)
    email: OptEmail = ""
    phone: str = Field(default="", max_length=50)
    city_country: str = Field(default="", max_length=200)
    bio: str = Field(default="", max_length=3000)
    linkedin_url: Url = ""
    website_url: Url = ""
    expertise: str = Field(default="", max_length=3000)
    topics: str = Field(default="", max_length=3000)
    proposed_title: str = Field(default="", max_length=500)
    abstract: str = Field(default="", max_length=4000)
    key_takeaways: str = Field(default="", max_length=3000)
    formats: list[str] = Field(default_factory=list, max_length=12)
    past_speaking: str = Field(default="", max_length=3000)
    availability: list[str] = Field(default_factory=list, max_length=30)
    requirements: str = Field(default="", max_length=3000)
    extra_notes: str = Field(default="", max_length=3000)


class PublicFormIn(ApplicationFields):
    consent: bool = False
    hp: str = ""  # honeypot: real people never fill this in


class PublicFormOut(BaseModel):
    event_name: str
    edition: str
    venue: str
    theme_line: str
    days: list[str]
    formats: list[str]
    invitee_name: str
    invitee_email: str
    message: str
    status: str            # "open" | "pending" | "approved" | "rejected" | "closed"
    values: dict | None = None


class ApplicationOut(BaseModel):
    id: int
    status: str
    full_name: str
    designation: str
    organisation: str
    email: str
    phone: str
    city_country: str
    bio: str
    linkedin_url: str
    website_url: str
    expertise: str
    topics: str
    proposed_title: str
    abstract: str
    key_takeaways: str
    formats: list[str]
    past_speaking: str
    availability: list[str]
    requirements: str
    extra_notes: str
    review_note: str
    submitted_at: datetime
    reviewed_at: datetime | None
    speaker_id: int | None
    invited: bool
    sessions: list[SpeakerSessionRef] = []
    speaker_status: str | None = None


class ApproveIn(BaseModel):
    speaker_status: SpeakerStatus = SpeakerStatus.tentative
    note: str = Field(default="", max_length=1000)
    session_id: int | None = None
    role: SessionRole = SessionRole.speaker


class RejectIn(BaseModel):
    note: str = Field(default="", max_length=1000)


class AssignIn(BaseModel):
    speaker_id: int
    role: SessionRole = SessionRole.speaker


class SpeakerLinkIn(BaseModel):
    enabled: bool


class SpeakerLinkOut(BaseModel):
    enabled: bool
    token: str | None = None
    link: str | None = None