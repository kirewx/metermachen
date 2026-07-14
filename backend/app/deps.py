from datetime import datetime, timezone

from fastapi import Cookie, Depends, HTTPException
from sqlmodel import Session, select

from . import auth
from .db import engine
from .models import AddOn, User


def get_session():
    with Session(engine) as session:
        yield session


def _as_utc(dt: datetime) -> datetime:
    # SQLite gibt Datetimes ohne tzinfo zurück — als UTC interpretieren.
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def addon_active(addon: AddOn, now: datetime) -> bool:
    """Schalter = Master, Fenster plant: aktiv = enabled UND (kein Fenster ODER jetzt drin)."""
    if not addon.enabled:
        return False
    if addon.active_from is not None and now < _as_utc(addon.active_from):
        return False
    if addon.active_until is not None and now >= _as_utc(addon.active_until):
        return False
    return True


def require_addon(key: str):
    """Dependency-Factory: 404, wenn das Add-on fehlt oder gerade nicht aktiv ist."""

    def dep(session: Session = Depends(get_session)) -> None:
        addon = session.exec(select(AddOn).where(AddOn.key == key)).first()
        if addon is None or not addon_active(addon, datetime.now(timezone.utc)):
            raise HTTPException(status_code=404, detail="Feature nicht verfügbar")

    return dep


def get_current_user(
    session: Session = Depends(get_session),
    session_cookie: str | None = Cookie(default=None, alias=auth.SESSION_COOKIE),
) -> User:
    if not session_cookie:
        raise HTTPException(status_code=401, detail="Nicht eingeloggt")
    user_id = auth.read_session_token(session_cookie)
    user = session.get(User, user_id) if user_id is not None else None
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="Nicht eingeloggt")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Nur für Admins")
    return user
