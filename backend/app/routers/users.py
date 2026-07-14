from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from .. import auth
from ..deps import get_current_user, get_session, require_admin
from ..models import Activity, Category, Invite, StravaConnection, User
from ..schemas import ActivityOut
from .activities import _to_out
from .auth_router import MeOut

router = APIRouter(prefix="/api/users", tags=["users"])


class UserCreate(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=4)
    display_name: str = Field(min_length=1)
    avatar: str = "icon:laufen"
    is_admin: bool = False


class ProfilePatch(BaseModel):
    username: str | None = Field(default=None, min_length=1)
    display_name: str | None = Field(default=None, min_length=1)
    avatar: str | None = None
    password: str | None = Field(default=None, min_length=4)


class UserAdminOut(BaseModel):
    id: int
    username: str
    display_name: str
    avatar: str
    is_admin: bool
    is_active: bool
    km_factor: float
    created_at: datetime


class UserAdminPatch(BaseModel):
    is_active: bool | None = None
    km_factor: float | None = Field(default=None, gt=0)


def _username_taken(session: Session, username: str, ignore_id: int | None = None) -> bool:
    other = session.exec(select(User).where(User.username == username)).first()
    return other is not None and other.id != ignore_id


@router.post(
    "", response_model=MeOut, status_code=201, dependencies=[Depends(require_admin)]
)
def create_user(data: UserCreate, session: Session = Depends(get_session)):
    if _username_taken(session, data.username):
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


@router.get("", response_model=list[UserAdminOut], dependencies=[Depends(require_admin)])
def list_users(session: Session = Depends(get_session)):
    return session.exec(select(User).order_by(User.id)).all()


@router.get(
    "/{user_id}/activities",
    response_model=list[ActivityOut],
    dependencies=[Depends(get_current_user)],
)
def user_activities(
    user_id: int, year: int, session: Session = Depends(get_session)
) -> list[ActivityOut]:
    """Aktivitäten eines Mitglieds (neueste zuerst) für die Detailansicht im Vergleich.
    Nur aktive Accounts — deaktivierte tauchen wie im Ranking nicht auf."""
    user = session.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=404, detail="User nicht gefunden")
    rows = session.exec(
        select(Activity, Category)
        .join(Category, Activity.category_id == Category.id)
        .where(Activity.user_id == user_id)
        .order_by(Activity.date.desc(), Activity.id.desc())
    ).all()
    return [_to_out(a, c.factor) for a, c in rows if a.date.year == year]


@router.patch("/me", response_model=MeOut)
def patch_me(
    data: ProfilePatch,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    if data.username is not None and data.username != user.username:
        if _username_taken(session, data.username, ignore_id=user.id):
            raise HTTPException(status_code=409, detail="Benutzername vergeben")
        user.username = data.username
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


@router.patch("/{user_id}", response_model=UserAdminOut)
def patch_user(
    user_id: int,
    data: UserAdminPatch,
    admin: User = Depends(require_admin),
    session: Session = Depends(get_session),
):
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User nicht gefunden")
    if data.is_active is not None:
        if user.id == admin.id:
            raise HTTPException(
                status_code=409, detail="Den eigenen Account kannst du nicht deaktivieren"
            )
        user.is_active = data.is_active
    if data.km_factor is not None:
        user.km_factor = data.km_factor
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@router.delete("/{user_id}", status_code=204)
def delete_user(
    user_id: int,
    admin: User = Depends(require_admin),
    session: Session = Depends(get_session),
):
    user = session.get(User, user_id)
    if user is None:
        return
    if user.id == admin.id:
        raise HTTPException(
            status_code=409, detail="Den eigenen Account kannst du nicht löschen"
        )
    # Abhängige Daten mitnehmen — SQLite erzwingt die FKs hier nicht,
    # also explizit: Aktivitäten + Strava-Verbindung weg, Einladungen entkoppeln.
    for act in session.exec(select(Activity).where(Activity.user_id == user.id)).all():
        session.delete(act)
    conn = session.exec(
        select(StravaConnection).where(StravaConnection.user_id == user.id)
    ).first()
    if conn is not None:
        session.delete(conn)
    for inv in session.exec(select(Invite).where(Invite.created_by == user.id)).all():
        session.delete(inv)
    for inv in session.exec(
        select(Invite).where(Invite.used_by_user_id == user.id)
    ).all():
        inv.used_by_user_id = None
        session.add(inv)
    session.delete(user)
    session.commit()
