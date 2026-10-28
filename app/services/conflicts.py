"""Schedule conflict engine (Section 4.5).

Pure functions: no database access, so they are easy to test. Every rule only *warns*. Nothing here ever
blocks a save; the organiser decides what to do.

Times are minutes after midnight. A "slot" is the working view of one session.
"""
from dataclasses import dataclass, field
from datetime import time

from ..timeutil import fmt_duration, fmt_time

MIN_MINUTES, MAX_MINUTES, TIGHT_GAP = 5, 240, 5
NO_CHANGEOVER_TYPES = {"Break", "Networking"}  # a gap before or after these is never a changeover problem


@dataclass
class Slot:
    id: int | None
    day_id: int
    hall_id: int | None
    hall_name: str
    is_merged: bool
    title: str
    session_type: str
    start: time
    end: time
    speakers: dict[int, str] = field(default_factory=dict)  # speaker_id -> name (any role)

    @property
    def s(self) -> int:
        return self.start.hour * 60 + self.start.minute

    @property
    def e_raw(self) -> int:
        return self.end.hour * 60 + self.end.minute

    @property
    def crosses_midnight(self) -> bool:
        # 11:00 PM -> 1:00 AM reads as an overnight session; 3:00 PM -> 2:00 PM is simply end-before-start.
        return self.e_raw < self.s and self.s >= 12 * 60 and self.e_raw < 12 * 60

    @property
    def e(self) -> int | None:
        """Usable end for overlap maths, or None when the range is not meaningful."""
        if self.crosses_midnight:
            return 24 * 60
        return self.e_raw if self.e_raw > self.s else None

    @property
    def where(self) -> str:
        return "all halls" if self.is_merged else (self.hall_name or "a hall to be confirmed")

    @property
    def span(self) -> str:
        return f"{fmt_time(self.start)} to {fmt_time(self.end)}"


def _overlap(a: Slot, b: Slot) -> bool:
    if a.e is None or b.e is None:
        return False
    return a.s < b.e and b.s < a.e  # touching times (one ends as the other starts) are not an overlap


def warn(code: str, level: str, message: str, others: list[int] | None = None) -> dict:
    return {"code": code, "level": level, "message": message, "session_ids": others or []}


def check_slot(cand: Slot, others: list[Slot]) -> list[dict]:
    """All warnings for `cand` against the other sessions of the event."""
    out: list[dict] = []
    # ---- the session on its own
    if cand.crosses_midnight:
        out.append(warn("past_midnight", "warning",
                        f"This session ends at {fmt_time(cand.end)}, after midnight. Please check the end time."))
    elif cand.e_raw < cand.s:
        out.append(warn("end_before_start", "warning",
                        f"The end time ({fmt_time(cand.end)}) is earlier than the start time ({fmt_time(cand.start)})."))
    else:
        dur = cand.e_raw - cand.s
        if dur < MIN_MINUTES:
            out.append(warn("unusual_duration", "warning",
                            f"This session is only {fmt_duration(dur) or '0 min'} long. Sessions are normally at least {MIN_MINUTES} minutes."))
        elif dur > MAX_MINUTES:
            out.append(warn("unusual_duration", "warning",
                            f"This session is {fmt_duration(dur)} long. Sessions are normally no longer than 4 hours."))

    # ---- against the rest of the day
    same_day = [o for o in others if o.day_id == cand.day_id and o.id != cand.id]
    for o in same_day:
        if not _overlap(cand, o):
            continue
        ref = f"\"{o.title}\" ({o.span}, {o.where})"
        if cand.is_merged or o.is_merged:
            if cand.is_merged:
                msg = f"This all-halls session overlaps with {ref}. No parallel session can run while all halls are merged."
            else:
                msg = f"This session overlaps with the all-halls session {ref}."
            out.append(warn("merged_conflict", "warning", msg, [o.id]))
        elif cand.hall_id is not None and cand.hall_id == o.hall_id:
            out.append(warn("hall_overlap", "warning", f"This session overlaps with {ref} in the same hall.", [o.id]))
        for sid, name in cand.speakers.items():
            if sid in o.speakers:
                out.append(warn("speaker_double_booked", "warning",
                                f"{name} is also in {ref} at the same time.", [o.id]))

    # ---- changeover time (soft)
    if cand.session_type not in NO_CHANGEOVER_TYPES and cand.e is not None:
        for o in same_day:
            if o.session_type in NO_CHANGEOVER_TYPES or o.e is None or _overlap(cand, o):
                continue
            share_hall = cand.is_merged or o.is_merged or (cand.hall_id is not None and cand.hall_id == o.hall_id)
            if not share_hall:
                continue
            gap = o.s - cand.e if o.s >= cand.e else (cand.s - o.e if cand.s >= o.e else None)
            if gap is not None and 0 <= gap < TIGHT_GAP:
                side = "follows" if o.s >= cand.e else "precedes"
                ref = f"\"{o.title}\" ({o.span}, {o.where})"
                if gap == 0:
                    msg = f"This session runs straight into {ref}, which {side} it, with no time for changeover."
                else:
                    msg = f"Only {gap} minute{'s' if gap != 1 else ''} between this session and {ref}, which {side} it. Allow time for changeover."
                out.append(warn("tight_turnaround", "notice", msg, [o.id]))
    return out


def all_conflicts(slots: list[Slot]) -> dict[int, list[dict]]:
    """Warnings for every saved session, keyed by session id."""
    return {s.id: check_slot(s, [o for o in slots if o.id != s.id]) for s in slots}
