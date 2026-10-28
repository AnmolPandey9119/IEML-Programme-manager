import time

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session as DB

from ..database import get_db
from ..timeutil import utcnow
from ..deps import get_current_user
from ..models import Event, EventMember, Invitation, User
from ..schemas import (AcceptInviteIn, InvitePreview, LoginIn, SetupIn, TokenOut, UserOut)
from ..security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Basic brute-force protection: 8 failed log-ins per email within 10 minutes locks that email for the window.
_FAILS: dict[str, list[float]] = {}
_WINDOW, _MAX_FAILS = 600, 8


def _throttled(key: str) -> bool:
    now = time.time()
    hits = [t for t in _FAILS.get(key, []) if now - t < _WINDOW]
    _FAILS[key] = hits
    return len(hits) >= _MAX_FAILS


def _norm(email: str) -> str:
    return email.strip().lower()


@router.get("/setup-status")
def setup_status(db: DB = Depends(get_db)):
    return {"needs_setup": db.scalar(select(func.count(User.id))) == 0}


@router.post("/setup", response_model=TokenOut)
def first_time_setup(data: SetupIn, db: DB = Depends(get_db)):
    """Sirf tab chalta hai jab system mein koi user na ho (pehla admin). Self-registration nahi."""
    if db.scalar(select(func.count(User.id))) > 0:
        raise HTTPException(403, "Setup already completed. Ask an admin for an invitation.")
    user = User(email=_norm(data.email), full_name=data.full_name.strip(),
                password_hash=hash_password(data.password))
    db.add(user)
    db.commit()
    return TokenOut(access_token=create_access_token(user.id))


@router.post("/login", response_model=TokenOut)
def login(data: LoginIn, db: DB = Depends(get_db)):
    key = _norm(data.email)
    if _throttled(key):
        raise HTTPException(429, "Too many failed attempts. Please wait a few minutes and try again.")
    user = db.scalar(select(User).where(User.email == key))
    if not user or not user.is_active or not verify_password(data.password, user.password_hash):
        _FAILS.setdefault(key, []).append(time.time())
        raise HTTPException(401, "Incorrect email or password")
    _FAILS.pop(key, None)
    return TokenOut(access_token=create_access_token(user.id))


@router.get("/me")
def me(user: User = Depends(get_current_user), db: DB = Depends(get_db)):
    rows = db.execute(
        select(Event, EventMember.role)
        .join(EventMember, EventMember.event_id == Event.id)
        .where(EventMember.user_id == user.id)
    ).all()
    return {
        "user": UserOut.model_validate(user),
        "memberships": [{"event_id": e.id, "event_name": e.name, "role": r} for e, r in rows],
    }


def _valid_invite(db: DB, token: str) -> Invitation:
    inv = db.scalar(select(Invitation).where(Invitation.token == token))
    if not inv or inv.accepted_at or inv.expires_at < utcnow():
        raise HTTPException(404, "This invitation is invalid or has expired")
    return inv


@router.get("/invite/{token}", response_model=InvitePreview)
def invite_preview(token: str, db: DB = Depends(get_db)):
    inv = _valid_invite(db, token)
    event = db.get(Event, inv.event_id)
    has_account = db.scalar(select(User.id).where(User.email == inv.email)) is not None
    return InvitePreview(email=inv.email, event_name=event.name, role=inv.role, has_account=has_account)


@router.post("/accept-invite", response_model=TokenOut)
def accept_invite(data: AcceptInviteIn, db: DB = Depends(get_db)):
    inv = _valid_invite(db, data.token)
    user = db.scalar(select(User).where(User.email == inv.email))
    if user:
        if not user.is_active or not verify_password(data.password, user.password_hash):
            raise HTTPException(401, "Incorrect password for this existing account")
    else:
        if not data.full_name.strip():
            raise HTTPException(422, "Full name is required")
        user = User(email=inv.email, full_name=data.full_name.strip(),
                    password_hash=hash_password(data.password))
        db.add(user)
        db.flush()
    exists = db.scalar(select(EventMember.id).where(
        EventMember.event_id == inv.event_id, EventMember.user_id == user.id))
    if not exists:
        db.add(EventMember(event_id=inv.event_id, user_id=user.id, role=inv.role))
    inv.accepted_at = utcnow()
    db.commit()
    return TokenOut(access_token=create_access_token(user.id))
