from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlmodel import Session, select

from .. import auth, config
from ..deps import get_current_user, get_session
from ..models import User

router = APIRouter(prefix="/api/auth", tags=["auth"])

_DUMMY_HASH = auth.hash_password("dummy-timing-constant")


class LoginIn(BaseModel):
    username: str
    password: str


class MeOut(BaseModel):
    id: int
    username: str
    display_name: str
    avatar: str
    is_admin: bool


@router.post("/login", response_model=MeOut)
def login(data: LoginIn, response: Response, session: Session = Depends(get_session)):
    user = session.exec(select(User).where(User.username == data.username)).first()
    password_hash = user.password_hash if user is not None else _DUMMY_HASH
    if user is None or not auth.verify_password(password_hash, data.password):
        raise HTTPException(status_code=401, detail="Benutzername oder Passwort falsch")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account ist deaktiviert")
    response.set_cookie(
        auth.SESSION_COOKIE,
        auth.create_session_token(user.id),
        max_age=auth.SESSION_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=config.SESSION_COOKIE_SECURE,
    )
    return user


@router.post("/logout")
def logout(response: Response):
    # Attribute müssen zum Setzen passen, damit der Browser das Cookie sicher löscht.
    response.delete_cookie(
        auth.SESSION_COOKIE,
        httponly=True,
        samesite="lax",
        secure=config.SESSION_COOKIE_SECURE,
    )
    return {"ok": True}


@router.get("/me", response_model=MeOut)
def me(user: User = Depends(get_current_user)):
    return user
