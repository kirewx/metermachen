from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from .. import auth
from ..deps import get_current_user, get_session, require_admin
from ..models import User
from .auth_router import MeOut

router = APIRouter(prefix="/api/users", tags=["users"])


class UserCreate(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=4)
    display_name: str = Field(min_length=1)
    avatar: str = "icon:laufen"
    is_admin: bool = False


class ProfilePatch(BaseModel):
    display_name: str | None = Field(default=None, min_length=1)
    avatar: str | None = None
    password: str | None = Field(default=None, min_length=4)


@router.post("", response_model=MeOut, status_code=201, dependencies=[Depends(require_admin)])
def create_user(data: UserCreate, session: Session = Depends(get_session)):
    if session.exec(select(User).where(User.username == data.username)).first():
        raise HTTPException(status_code=409, detail="Benutzername vergeben")
    user = User(
        username=data.username,
        password_hash=auth.hash_password(data.password),
        display_name=data.display_name,
        avatar=data.avatar,
        is_admin=data.is_admin,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@router.patch("/me", response_model=MeOut)
def patch_me(
    data: ProfilePatch,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    if data.display_name is not None:
        user.display_name = data.display_name
    if data.avatar is not None:
        user.avatar = data.avatar
    if data.password is not None:
        user.password_hash = auth.hash_password(data.password)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user
