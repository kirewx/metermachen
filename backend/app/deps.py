from fastapi import Cookie, Depends, HTTPException
from sqlmodel import Session

from . import auth
from .db import engine
from .models import User


def get_session():
    with Session(engine) as session:
        yield session


def get_current_user(
    session: Session = Depends(get_session),
    session_cookie: str | None = Cookie(default=None, alias=auth.SESSION_COOKIE),
) -> User:
    if not session_cookie:
        raise HTTPException(status_code=401, detail="Nicht eingeloggt")
    user_id = auth.read_session_token(session_cookie)
    user = session.get(User, user_id) if user_id is not None else None
    if user is None:
        raise HTTPException(status_code=401, detail="Nicht eingeloggt")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Nur für Admins")
    return user
