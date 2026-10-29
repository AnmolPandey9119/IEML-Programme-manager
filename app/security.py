from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from jose import JWTError, jwt
from passlib.context import CryptContext

from .config import settings

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
ALGO = "HS256"


def hash_password(password: str) -> str:
    return _pwd.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return _pwd.verify(password, hashed)


def create_access_token(user_id: int) -> str:
    exp = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode({"sub": str(user_id), "exp": exp}, settings.SECRET_KEY, algorithm=ALGO)


def decode_access_token(token: str) -> int | None:
    try:
        return int(jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGO])["sub"])
    except (JWTError, KeyError, ValueError):
        return None


# ---- signed media links: <img> tags cannot send an Authorization header, so photo URLs carry a signature
import hashlib
import hmac


def photo_signature(speaker_id: int, photo_hash: str) -> str:
    msg = f"speaker-photo:{speaker_id}:{photo_hash}".encode()
    return hmac.new(settings.SECRET_KEY.encode(), msg, hashlib.sha256).hexdigest()[:24]


def photo_url(speaker_id: int, photo_hash: str) -> str:
    if not photo_hash:
        return ""
    return f"/api/media/speaker/{speaker_id}/{photo_hash}/{photo_signature(speaker_id, photo_hash)}"


def require_internal_email(email: str) -> None:
    """Internal IEML tool: when ALLOWED_EMAIL_DOMAINS is set, only addresses from those domains are accepted."""
    domains = [d.strip().lower().lstrip("@") for d in settings.ALLOWED_EMAIL_DOMAINS.split(",") if d.strip()]
    if domains and email.strip().lower().rsplit("@", 1)[-1] not in domains:
        raise HTTPException(403, "This is an internal IEML tool. Please use your IEML email address ("
                                 + ", ".join("@" + d for d in domains) + ").")