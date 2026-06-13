import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from .. import auth, config
from ..deps import get_session, require_admin
from ..models import Invite, User, utcnow
from .auth_router import MeOut

router = APIRouter(prefix="/api/invites", tags=["invites"])

INVITE_TTL = timedelta(days=7)


def _invite_url(token: str) -> str:
    base = config.PUBLIC_BASE_URL or ""
    return f"{base}/einladung/{token}"


def _is_expired(invite: Invite) -> bool:
    exp = invite.expires_at
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    return exp < datetime.now(timezone.utc)


class InviteCreate(BaseModel):
    display_name: str | None = None
    is_admin: bool = False


class InviteOut(BaseModel):
    id: int
    token: str
    url: str
    display_name: str | None
    is_admin: bool
    expires_at: datetime
    used_at: datetime | None


class InvitePublic(BaseModel):
    valid: bool
    display_name: str | None = None
    expired: bool = False
    used: bool = False


class InviteAccept(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=4)
    display_name: str = Field(min_length=1)
    avatar: str = "icon:laufen"


def _to_out(invite: Invite) -> InviteOut:
    return InviteOut(
        id=invite.id,
        token=invite.token,
        url=_invite_url(invite.token),
        display_name=invite.display_name,
        is_admin=invite.is_admin,
        expires_at=invite.expires_at,
        used_at=invite.used_at,
    )


@router.post("", response_model=InviteOut, status_code=201)
def create_invite(
    data: InviteCreate,
    admin: User = Depends(require_admin),
    session: Session = Depends(get_session),
):
    invite = Invite(
        token=secrets.token_urlsafe(16),
        created_by=admin.id,
        display_name=data.display_name,
        is_admin=data.is_admin,
        expires_at=utcnow() + INVITE_TTL,
    )
    session.add(invite)
    session.commit()
    session.refresh(invite)
    return _to_out(invite)


@router.get("", response_model=list[InviteOut], dependencies=[Depends(require_admin)])
def list_invites(session: Session = Depends(get_session)):
    invites = session.exec(select(Invite).order_by(Invite.created_at.desc())).all()
    return [_to_out(i) for i in invites]


@router.delete("/{invite_id}", status_code=204, dependencies=[Depends(require_admin)])
def delete_invite(invite_id: int, session: Session = Depends(get_session)):
    invite = session.get(Invite, invite_id)
    if invite is not None:
        session.delete(invite)
        session.commit()


@router.get("/{token}", response_model=InvitePublic)
def check_invite(token: str, session: Session = Depends(get_session)):
    invite = session.exec(select(Invite).where(Invite.token == token)).first()
    if invite is None:
        return InvitePublic(valid=False)
    used = invite.used_at is not None
    expired = _is_expired(invite)
    return InvitePublic(
        valid=not used and not expired,
        display_name=invite.display_name,
        expired=expired,
        used=used,
    )


@router.post("/{token}/accept", response_model=MeOut)
def accept_invite(
    token: str,
    data: InviteAccept,
    response: Response,
    session: Session = Depends(get_session),
):
    invite = session.exec(select(Invite).where(Invite.token == token)).first()
    if invite is None:
        raise HTTPException(status_code=404, detail="Einladung ungültig")
    if invite.used_at is not None:
        raise HTTPException(status_code=409, detail="Einladung bereits eingelöst")
    if _is_expired(invite):
        raise HTTPException(status_code=410, detail="Einladung abgelaufen")
    if session.exec(select(User).where(User.username == data.username)).first():
        raise HTTPException(status_code=409, detail="Benutzername vergeben")
    user = User(
        username=data.username,
        password_hash=auth.hash_password(data.password),
        display_name=data.display_name,
        avatar=data.avatar,
        is_admin=invite.is_admin,
    )
    session.add(user)
    session.flush()  # vergibt user.id, ohne schon zu committen
    invite.used_at = utcnow()
    invite.used_by_user_id = user.id
    session.add(invite)
    session.commit()  # User + Invite-Sperre atomar in einem Commit
    session.refresh(user)
    response.set_cookie(
        auth.SESSION_COOKIE,
        auth.create_session_token(user.id),
        max_age=auth.SESSION_MAX_AGE,
        httponly=True,
        samesite="lax",
    )
    return user
