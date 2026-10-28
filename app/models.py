import enum
import secrets
from datetime import date, datetime, time

from sqlalchemy import (
    Boolean, Date, DateTime, Enum, ForeignKey, Integer, LargeBinary, String, Text, Time,
    UniqueConstraint, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


# ---------------------------------------------------------------- enums
class Role(str, enum.Enum):
    admin = "admin"
    editor = "editor"
    viewer = "viewer"


class EventStatus(str, enum.Enum):
    draft = "draft"
    active = "active"
    archived = "archived"


class SessionType(str, enum.Enum):
    keynote = "Keynote"
    plenary = "Plenary"
    inaugural = "Inaugural"
    roundtable = "Roundtable"
    panel = "Panel Discussion"
    fireside = "Fireside Chat"
    talk = "Talk / Address"
    leadership = "Leadership Address"
    workshop = "Workshop"
    lightning = "Lightning Talk"
    networking = "Networking"
    break_ = "Break"
    custom = "Custom"


class PublishStatus(str, enum.Enum):
    draft = "draft"
    published = "published"


class SpeakerStatus(str, enum.Enum):
    invited = "Invited"
    confirmed = "Confirmed"
    tentative = "Tentative"
    declined = "Declined"


class SessionRole(str, enum.Enum):
    speaker = "speaker"
    panelist = "panelist"
    moderator = "moderator"


class GroupType(str, enum.Enum):
    oc = "OC"
    advisory = "Advisory Council"
    sub_committee = "Sub-committee"
    working_group = "Working Group"
    custom = "Custom"


class MeetingStatus(str, enum.Enum):
    scheduled = "Scheduled"
    completed = "Completed"
    cancelled = "Cancelled"


class Attendance(str, enum.Enum):
    unmarked = "unmarked"
    attended = "attended"
    absent = "absent"
    apologies = "apologies"


class NotificationType(str, enum.Enum):
    speaker_confirmed = "speaker_confirmed"
    late_change = "late_change"


def _token() -> str:
    return secrets.token_urlsafe(32)


# ---------------------------------------------------------------- auth / team
class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(200), default="")
    password_hash: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    memberships: Mapped[list["EventMember"]] = relationship(back_populates="user")


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    edition: Mapped[str] = mapped_column(String(100), default="")
    venue_name: Mapped[str] = mapped_column(String(255), default="")
    venue_city: Mapped[str] = mapped_column(String(120), default="")
    theme_line: Mapped[str] = mapped_column(String(500), default="")
    website_url: Mapped[str] = mapped_column(String(500), default="")
    status: Mapped[EventStatus] = mapped_column(Enum(EventStatus), default=EventStatus.draft)
    public_key: Mapped[str] = mapped_column(String(64), unique=True, default=_token)
    # Shared "invite by link" for the speaker form. None = switched off. Anyone with the link can apply.
    speaker_form_token: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    days: Mapped[list["EventDay"]] = relationship(
        back_populates="event", cascade="all, delete-orphan", order_by="EventDay.day_date"
    )
    halls: Mapped[list["Hall"]] = relationship(
        back_populates="event", cascade="all, delete-orphan", order_by="Hall.position"
    )
    members: Mapped[list["EventMember"]] = relationship(
        back_populates="event", cascade="all, delete-orphan"
    )
    # Event delete hone par saara related data saath jaye
    invitations: Mapped[list["Invitation"]] = relationship(cascade="all, delete-orphan")
    notification_settings: Mapped[list["EventNotificationSetting"]] = relationship(cascade="all, delete-orphan")
    sessions: Mapped[list["Session"]] = relationship(cascade="all, delete-orphan", viewonly=False)
    speakers: Mapped[list["Speaker"]] = relationship(cascade="all, delete-orphan")
    groups: Mapped[list["Group"]] = relationship(cascade="all, delete-orphan")
    speaker_invites: Mapped[list["SpeakerInvite"]] = relationship(cascade="all, delete-orphan")
    speaker_applications: Mapped[list["SpeakerApplication"]] = relationship(cascade="all, delete-orphan")


class EventMember(Base):
    """User <-> Event link with a role. Har query isi se event-scope hoti hai."""
    __tablename__ = "event_members"
    __table_args__ = (UniqueConstraint("event_id", "user_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    role: Mapped[Role] = mapped_column(Enum(Role), default=Role.viewer)
    # Per-person switch (Section 5.2: admin can turn off per person)
    receive_notifications: Mapped[bool] = mapped_column(Boolean, default=True)

    event: Mapped[Event] = relationship(back_populates="members")
    user: Mapped[User] = relationship(back_populates="memberships")


class Invitation(Base):
    """Invite-only join. Self-registration nahi."""
    __tablename__ = "invitations"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), index=True)
    email: Mapped[str] = mapped_column(String(255), index=True)
    role: Mapped[Role] = mapped_column(Enum(Role), default=Role.viewer)
    token: Mapped[str] = mapped_column(String(64), unique=True, default=_token)
    invited_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class EventNotificationSetting(Base):
    """Admin per event notification type on/off kar sakta hai (Section 8)."""
    __tablename__ = "event_notification_settings"
    __table_args__ = (UniqueConstraint("event_id", "type"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), index=True)
    type: Mapped[NotificationType] = mapped_column(Enum(NotificationType))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


# ---------------------------------------------------------------- event setup
class EventDay(Base):
    __tablename__ = "event_days"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), index=True)
    day_date: Mapped[date] = mapped_column(Date)
    label: Mapped[str] = mapped_column(String(120))  # e.g. "Day 1 — Monday, Feb 8"

    event: Mapped[Event] = relationship(back_populates="days")


class Hall(Base):
    __tablename__ = "halls"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(150))
    position: Mapped[int] = mapped_column(Integer, default=0)

    event: Mapped[Event] = relationship(back_populates="halls")


# ---------------------------------------------------------------- speakers
class Speaker(Base):
    __tablename__ = "speakers"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), index=True)
    full_name: Mapped[str] = mapped_column(String(200))
    designation: Mapped[str] = mapped_column(String(255), default="")
    organisation: Mapped[str] = mapped_column(String(255), default="")
    bio: Mapped[str] = mapped_column(Text, default="")
    # Column keeps its original name "photo_path" so existing databases stay valid; it now holds the
    # content fingerprint of the stored photo ("" = no photo). The image itself lives in the database,
    # so photos survive redeploys on hosts with an ephemeral disk.
    photo_hash: Mapped[str] = mapped_column("photo_path", String(500), default="")
    photo_data: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True, deferred=True)
    email: Mapped[str] = mapped_column(String(255), default="")  # internal only
    phone: Mapped[str] = mapped_column(String(50), default="")   # internal only
    linkedin_url: Mapped[str] = mapped_column(String(500), default="")
    website_url: Mapped[str] = mapped_column(String(500), default="")
    status: Mapped[SpeakerStatus] = mapped_column(Enum(SpeakerStatus), default=SpeakerStatus.invited)
    status_remark: Mapped[str] = mapped_column(Text, default="")
    internal_notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    session_links: Mapped[list["SessionSpeaker"]] = relationship(
        back_populates="speaker", cascade="all, delete-orphan"
    )


# ---------------------------------------------------------------- speaker invitations & applications
# Status columns below are plain strings (not DB enums) so a Postgres database never needs ALTER TYPE later.
APP_PENDING, APP_APPROVED, APP_REJECTED = "pending", "approved", "rejected"


class SpeakerInvite(Base):
    """One personal link per invited speaker. The link opens the public speaker form (no login)."""
    __tablename__ = "speaker_invites"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200), default="")
    email: Mapped[str] = mapped_column(String(255), default="")
    message: Mapped[str] = mapped_column(Text, default="")
    token: Mapped[str] = mapped_column(String(64), unique=True, default=_token)
    invited_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    last_sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    email_sent: Mapped[bool] = mapped_column(Boolean, default=False)


class SpeakerApplication(Base):
    """What a speaker filled in on the form. The team reviews it, then approves (-> Speaker) or rejects."""
    __tablename__ = "speaker_applications"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), index=True)
    invite_id: Mapped[int | None] = mapped_column(ForeignKey("speaker_invites.id", ondelete="SET NULL"), nullable=True, index=True)
    speaker_id: Mapped[int | None] = mapped_column(ForeignKey("speakers.id", ondelete="SET NULL"), nullable=True)

    full_name: Mapped[str] = mapped_column(String(200))
    designation: Mapped[str] = mapped_column(String(255), default="")
    organisation: Mapped[str] = mapped_column(String(255), default="")
    email: Mapped[str] = mapped_column(String(255), default="")
    phone: Mapped[str] = mapped_column(String(50), default="")
    city_country: Mapped[str] = mapped_column(String(200), default="")
    bio: Mapped[str] = mapped_column(Text, default="")
    linkedin_url: Mapped[str] = mapped_column(String(500), default="")
    website_url: Mapped[str] = mapped_column(String(500), default="")

    expertise: Mapped[str] = mapped_column(Text, default="")        # areas of expertise
    topics: Mapped[str] = mapped_column(Text, default="")           # what they want to speak about
    proposed_title: Mapped[str] = mapped_column(String(500), default="")
    abstract: Mapped[str] = mapped_column(Text, default="")
    key_takeaways: Mapped[str] = mapped_column(Text, default="")
    formats: Mapped[str] = mapped_column(String(500), default="")   # comma separated session formats
    past_speaking: Mapped[str] = mapped_column(Text, default="")
    availability: Mapped[str] = mapped_column(String(500), default="")  # comma separated event day labels
    requirements: Mapped[str] = mapped_column(Text, default="")     # AV, travel, accommodation, dietary ...
    extra_notes: Mapped[str] = mapped_column(Text, default="")

    status: Mapped[str] = mapped_column(String(20), default=APP_PENDING, index=True)
    review_note: Mapped[str] = mapped_column(Text, default="")
    reviewed_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


# ---------------------------------------------------------------- sessions
class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), index=True)
    day_id: Mapped[int] = mapped_column(ForeignKey("event_days.id"), index=True)
    # Merged plenary: is_merged=True aur hall_id=None (ek hi representation)
    hall_id: Mapped[int | None] = mapped_column(ForeignKey("halls.id", ondelete="SET NULL"), nullable=True)
    is_merged: Mapped[bool] = mapped_column(Boolean, default=False)

    title: Mapped[str] = mapped_column(String(500))
    session_type: Mapped[SessionType] = mapped_column(Enum(SessionType), default=SessionType.talk)
    custom_type_label: Mapped[str] = mapped_column(String(120), default="")
    writeup: Mapped[str] = mapped_column(Text, default="")
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)
    status: Mapped[PublishStatus] = mapped_column(Enum(PublishStatus), default=PublishStatus.draft)
    internal_notes: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    day: Mapped[EventDay] = relationship()
    hall: Mapped[Hall | None] = relationship()
    subtopics: Mapped[list["SessionSubtopic"]] = relationship(
        back_populates="session", cascade="all, delete-orphan", order_by="SessionSubtopic.position"
    )
    speaker_links: Mapped[list["SessionSpeaker"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )


class SessionSubtopic(Base):
    __tablename__ = "session_subtopics"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"), index=True)
    text: Mapped[str] = mapped_column(Text)
    position: Mapped[int] = mapped_column(Integer, default=0)

    session: Mapped[Session] = relationship(back_populates="subtopics")


class SessionSpeaker(Base):
    __tablename__ = "session_speakers"
    __table_args__ = (UniqueConstraint("session_id", "speaker_id", "role"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"), index=True)
    speaker_id: Mapped[int] = mapped_column(ForeignKey("speakers.id", ondelete="CASCADE"), index=True)
    role: Mapped[SessionRole] = mapped_column(Enum(SessionRole), default=SessionRole.speaker)
    position: Mapped[int] = mapped_column(Integer, default=0)

    session: Mapped[Session] = relationship(back_populates="speaker_links")
    speaker: Mapped[Speaker] = relationship(back_populates="session_links")


# ---------------------------------------------------------------- lists & meetings
class Group(Base):
    __tablename__ = "groups"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    group_type: Mapped[GroupType] = mapped_column(Enum(GroupType), default=GroupType.custom)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    # Read-only shareable link; None = link band hai (revocable)
    share_token: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    share_include_contacts: Mapped[bool] = mapped_column(Boolean, default=False)

    members: Mapped[list["GroupMember"]] = relationship(
        back_populates="group", cascade="all, delete-orphan", order_by="GroupMember.position"
    )
    meetings: Mapped[list["Meeting"]] = relationship(
        back_populates="group", cascade="all, delete-orphan", order_by="Meeting.meeting_date"
    )


class GroupMember(Base):
    __tablename__ = "group_members"

    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    designation: Mapped[str] = mapped_column(String(255), default="")
    organisation: Mapped[str] = mapped_column(String(255), default="")
    email: Mapped[str] = mapped_column(String(255), default="")
    phone: Mapped[str] = mapped_column(String(50), default="")
    role_in_group: Mapped[str] = mapped_column(String(150), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    position: Mapped[int] = mapped_column(Integer, default=0)

    group: Mapped[Group] = relationship(back_populates="members")


class Meeting(Base):
    __tablename__ = "meetings"

    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(300))
    meeting_date: Mapped[date] = mapped_column(Date)
    start_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=60)
    location: Mapped[str] = mapped_column(String(300), default="")  # plain text
    agenda: Mapped[str] = mapped_column(Text, default="")
    minutes: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[MeetingStatus] = mapped_column(Enum(MeetingStatus), default=MeetingStatus.scheduled)

    group: Mapped[Group] = relationship(back_populates="meetings")
    attendance: Mapped[list["MeetingAttendance"]] = relationship(
        back_populates="meeting", cascade="all, delete-orphan"
    )


class MeetingAttendance(Base):
    __tablename__ = "meeting_attendance"
    __table_args__ = (UniqueConstraint("meeting_id", "member_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    meeting_id: Mapped[int] = mapped_column(ForeignKey("meetings.id", ondelete="CASCADE"), index=True)
    member_id: Mapped[int] = mapped_column(ForeignKey("group_members.id", ondelete="CASCADE"))
    status: Mapped[Attendance] = mapped_column(Enum(Attendance), default=Attendance.unmarked)

    meeting: Mapped[Meeting] = relationship(back_populates="attendance")