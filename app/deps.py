from dataclasses import dataclass

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session as DB

from .database import get_db
from .models import Event, EventMember, EventStatus, Role, User
from .security import decode_access_token

_bearer = HTTPBearer(auto_error=False)
ROLE_RANK = {Role.viewer: 1, Role.editor: 2, Role.admin: 3}


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: DB = Depends(get_db),
) -> User:
    uid = decode_access_token(creds.credentials) if creds else None
    user = db.get(User, uid) if uid else None
    if not user or not user.is_active:
        raise HTTPException(401, "Not authenticated")
    return user


@dataclass
class EventCtx:
    event: Event
    member: EventMember
    user: User
    db: DB


def event_ctx(min_role: Role = Role.viewer, write: bool = False):
    """Har event-scoped route isi se guzarta hai:
    - membership nahi -> 404 (event ka existence leak nahi hota => multi-event isolation)
    - role kam -> 403
    - write=True aur event Archived -> 403 (read-only)
    """
    def dep(event_id: int, user: User = Depends(get_current_user), db: DB = Depends(get_db)) -> EventCtx:
        row = db.execute(
            select(EventMember, Event).join(Event, Event.id == EventMember.event_id)
            .where(EventMember.event_id == event_id, EventMember.user_id == user.id)
        ).first()
        member, event = (row[0], row[1]) if row else (None, None)
        if not member or not event:
            raise HTTPException(404, "Event not found")
        if ROLE_RANK[member.role] < ROLE_RANK[min_role]:
            raise HTTPException(403, f"{min_role.value.title()} access required")
        if write and event.status == EventStatus.archived:
            raise HTTPException(403, "This event is archived (read-only)")
        return EventCtx(event, member, user, db)
    return dep