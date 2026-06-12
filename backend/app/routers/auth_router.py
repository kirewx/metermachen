from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlmodel import Session, select

from .. import auth
from ..deps import get_current_user, get_session
from ..models import User

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginIn(BaseModel):
    username: str
    password: str


class MeOut(BaseModel):
    id: int
    username: str
    display_name: str
    avatar_emoji: str
    is_admin: bool


@router.post("/login", response_model=MeOut)
def login(data: LoginIn, response: Response, session: Session = Depends(get_session)):
    user = session.exec(select(User).where(User.username == data.username)).first()
    if user is None or not auth.verify_password(user.password_hash, data.password):
        raise HTTPException(status_code=401, detail="Benutzername oder Passwort falsch")
    response.set_cookie(
        auth.SESSION_COOKIE,
        auth.create_session_token(user.id),
        max_age=auth.SESSION_MAX_AGE,
        httponly=True,
        samesite="lax",
    )
    return user


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(auth.SESSION_COOKIE)
    return {"ok": True}


@router.get("/me", response_model=MeOut)
def me(user: User = Depends(get_current_user)):
    return user
