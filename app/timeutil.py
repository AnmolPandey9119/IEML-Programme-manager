"""Small time helpers shared by routers and services."""
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from .config import settings


def utcnow() -> datetime:
    """Naive UTC 'now' (the database stores naive UTC datetimes)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def event_tz() -> ZoneInfo:
    try:
        return ZoneInfo(settings.EVENT_TIMEZONE)
    except Exception:  # unknown zone name -> fall back safely
        return ZoneInfo("Asia/Kolkata")


def local_now() -> datetime:
    return datetime.now(event_tz())


def fmt_time(t: time | None) -> str:
    """12-hour clock with AM/PM, e.g. 9:05 AM."""
    if t is None:
        return ""
    h = t.hour % 12 or 12
    return f"{h}:{t.minute:02d} {'AM' if t.hour < 12 else 'PM'}"


def minutes(t: time) -> int:
    return t.hour * 60 + t.minute


def fmt_duration(mins: int) -> str:
    if mins <= 0:
        return ""
    h, m = divmod(mins, 60)
    if h and m:
        return f"{h} h {m} min"
    return f"{h} h" if h else f"{m} min"


def fmt_date_long(d: date) -> str:
    return f"{d.strftime('%A')}, {d.day} {d.strftime('%B %Y')}"


def hours_until_day_start(d: date) -> float:
    start = datetime.combine(d, time(0, 0), tzinfo=event_tz())
    return (start - local_now()).total_seconds() / 3600


def day_is_over(d: date) -> bool:
    end = datetime.combine(d + timedelta(days=1), time(0, 0), tzinfo=event_tz())
    return local_now() >= end
