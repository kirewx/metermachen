from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from ..deps import get_current_user, get_session
from ..models import Activity, Category, User
from ..schemas import ActivityCreate, ActivityOut, ActivityPatch
from ..models import utcnow

router = APIRouter(prefix="/api/activities", tags=["activities"])


def _validate_category(session: Session, category_id: int) -> Category:
    cat = session.get(Category, category_id)
    if cat is None or not cat.is_active:
        raise HTTPException(status_code=422, detail="Kategorie unbekannt oder inaktiv")
    return cat


def _to_out(activity: Activity, factor: float) -> ActivityOut:
    return ActivityOut(
        id=activity.id,
        category_id=activity.category_id,
        date=activity.date,
        distance_km=activity.distance_km,
        duration_min=activity.duration_min,
        note=activity.note,
        scaled_km=round(activity.distance_km * factor, 2),
        edited=activity.updated_at is not None,
    )


def _own_activity(session: Session, user: User, activity_id: int) -> Activity:
    act = session.get(Activity, activity_id)
    if act is None or act.user_id != user.id:
        raise HTTPException(status_code=404)
    return act


@router.get("", response_model=list[ActivityOut])
def list_my_activities(
    year: int,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    acts = session.exec(
        select(Activity, Category)
        .join(Category, Activity.category_id == Category.id)
        .where(Activity.user_id == user.id)
        .order_by(Activity.date.desc(), Activity.id.desc())
    ).all()
    return [_to_out(a, c.factor) for a, c in acts if a.date.year == year]


@router.post("", response_model=ActivityOut, status_code=201)
def create_activity(
    data: ActivityCreate,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    cat = _validate_category(session, data.category_id)
    act = Activity(user_id=user.id, **data.model_dump())
    session.add(act)
    session.commit()
    session.refresh(act)
    return _to_out(act, cat.factor)


@router.patch("/{activity_id}", response_model=ActivityOut)
def patch_activity(
    activity_id: int,
    data: ActivityPatch,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    act = _own_activity(session, user, activity_id)
    changes = {
        key: value
        for key, value in data.model_dump(exclude_unset=True).items()
        if value is not None or key in ("note", "duration_min")
    }
    if "category_id" in changes:
        _validate_category(session, changes["category_id"])
    for key, value in changes.items():
        setattr(act, key, value)
    act.updated_at = utcnow()
    session.add(act)
    session.commit()
    session.refresh(act)
    cat = session.get(Category, act.category_id)
    return _to_out(act, cat.factor)


@router.delete("/{activity_id}", status_code=204)
def delete_activity(
    activity_id: int,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    act = _own_activity(session, user, activity_id)
    session.delete(act)
    session.commit()
